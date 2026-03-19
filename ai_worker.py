"""
AI WORKER v3 — CELERY TASK RUNNER
====================================
Pipeline: GROK-4.2 (JSON) -> CLAUDE (markdown) -> (GEMINI + SCHEMATIC parallel) -> Save

v3 improvements:
  - Grok returns structured JSON (components, specs, feasibility, creative ideas)
  - Retry with exponential backoff on all LLM calls (handles 429s, transient failures)
  - Token budget estimation before each call (auto-truncate if too high)
  - Structured JSON logging for observability
  - Heartbeat updates every 10s during long agent calls
  - asyncio.to_thread for all sync SDK calls (Claude, schematic)
  - Gemini + Schematic run in parallel (saves 15-30s)
  - Grok failure detection with Claude self-analysis fallback
  - Schematic retry with shorter excerpt on failure
"""

import os
import json
import logging
import asyncio
import time as _time
from typing import Optional

import httpx
import psycopg2.pool
from celery import Celery
from celery.signals import worker_process_init
from contextlib import contextmanager
from anthropic import Anthropic

try:
    import google.generativeai as genai
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False

# ── LOGGING ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ai_worker")


def _log_event(event: str, **kwargs):
    """Structured JSON log line for easy parsing."""
    kwargs["event"] = event
    kwargs["ts"] = _time.time()
    log.info(json.dumps(kwargs, default=str))


# ── CELERY + DB ───────────────────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
celery_app = Celery("ai_worker", broker=REDIS_URL, backend=REDIS_URL)
celery = celery_app  # Alias — Celery's -A flag looks for 'celery' by default
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=3600,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

_db_url = os.getenv("DATABASE_URL")
if not _db_url:
    raise RuntimeError("DATABASE_URL is not set.")

# Pool created AFTER Celery forks — prevents shared-socket crashes
pool = None


@worker_process_init.connect
def _init_worker_db(**kwargs):
    """Create a fresh DB pool in each Celery child process."""
    global pool
    pool = psycopg2.pool.ThreadedConnectionPool(1, 5, _db_url)
    log.info("DB pool created in worker process (pid=%d)", os.getpid())


@contextmanager
def get_db():
    if pool is None:
        raise RuntimeError("Database pool not initialized — worker_process_init hasn't fired.")
    conn = pool.getconn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


# ── ENVIRONMENT ───────────────────────────────────────────────────────────────
CONCEPTION_URL = os.getenv("CONCEPTION_SERVICE_URL", "http://builder-conception:10000")
INT_KEY        = os.getenv("INTERNAL_API_KEY", "")
ANTHROPIC_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_KEY     = os.getenv("GEMINI_API_KEY", "")
GROK_KEY       = os.getenv("GROK_API_KEY", "")
GMAIL_ADDRESS  = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PW   = os.getenv("GMAIL_APP_PW", "")

_anthropic_client: Optional[Anthropic] = None


def _get_anthropic() -> Anthropic:
    global _anthropic_client
    if _anthropic_client is None and ANTHROPIC_KEY:
        _anthropic_client = Anthropic(api_key=ANTHROPIC_KEY)
    return _anthropic_client


if _GENAI_AVAILABLE and GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)


def _h() -> dict:
    return {"x-internal-key": INT_KEY}


# ── COST ESTIMATION ($ per 1K tokens, approximate) ───────────────────────────
# Update these when pricing changes. Used for logging only, not billing.
_COST_PER_1K = {
    "grok_input":     0.0002,  # Grok 4.2 ($0.20/M tokens)
    "grok_output":    0.0005,  # Grok 4.2 ($0.50/M tokens)
    "claude_input":   0.003,   # Claude Sonnet
    "claude_output":  0.015,
    "gemini_input":   0.0001,  # Gemini 2.5 Flash
    "gemini_output":  0.0004,
}


def _estimate_cost(agent: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for an agent call."""
    in_cost = (input_tokens / 1000) * _COST_PER_1K.get(f"{agent}_input", 0)
    out_cost = (output_tokens / 1000) * _COST_PER_1K.get(f"{agent}_output", 0)
    return round(in_cost + out_cost, 4)


# ── EMAIL DELIVERY ────────────────────────────────────────────────────────────

def _send_blueprint_email(user_email: str, project_type: str,
                           blueprint: str, build_id, notes: dict) -> bool:
    """Email the completed blueprint to the user. Non-critical — never crashes the pipeline."""
    if not GMAIL_ADDRESS or not GMAIL_APP_PW or not user_email:
        return False
    if user_email in ("admin", "anonymous"):
        return False

    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    difficulty = notes.get("difficulty_rating", "Unknown")
    build_time = notes.get("estimated_build_time", "Unknown")
    feasibility = "See blueprint"

    # Extract feasibility from blueprint text
    for line in blueprint.split("\n"):
        if "FEASIBILITY RATING:" in line.upper() or "FEASIBILITY:" in line.upper():
            feasibility = line.strip()[:80]
            break

    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;background:#0A0E17;color:#E2E8F0;padding:30px;border-radius:12px;">
        <div style="text-align:center;margin-bottom:20px;">
            <h1 style="color:#FF4500;font-size:28px;margin:0;">YOUR BLUEPRINT IS READY</h1>
            <p style="color:#94A3B8;font-size:14px;">The Builder Foundry — AoC3P0 Systems</p>
        </div>

        <div style="background:#1E293B;padding:20px;border-radius:8px;border-left:4px solid #FF4500;margin-bottom:20px;">
            <div style="color:#F97316;font-size:12px;letter-spacing:2px;">PROJECT</div>
            <div style="color:white;font-size:20px;font-weight:bold;margin-top:4px;">{project_type}</div>
        </div>

        <div style="display:flex;gap:12px;margin-bottom:20px;">
            <div style="background:#1E293B;padding:12px;border-radius:6px;flex:1;text-align:center;">
                <div style="color:#94A3B8;font-size:10px;">DIFFICULTY</div>
                <div style="color:white;font-weight:bold;">{difficulty}</div>
            </div>
            <div style="background:#1E293B;padding:12px;border-radius:6px;flex:1;text-align:center;">
                <div style="color:#94A3B8;font-size:10px;">BUILD TIME</div>
                <div style="color:white;font-weight:bold;">{build_time}</div>
            </div>
        </div>

        <div style="background:#1E293B;padding:20px;border-radius:8px;margin-bottom:20px;">
            <div style="color:#FF4500;font-size:12px;letter-spacing:2px;margin-bottom:12px;">BLUEPRINT PREVIEW</div>
            <pre style="color:#CBD5E1;font-size:12px;line-height:1.6;white-space:pre-wrap;font-family:monospace;">{blueprint[:2000]}...</pre>
        </div>

        <div style="text-align:center;margin-bottom:20px;">
            <a href="https://bobtherobotbuilder.com" style="display:inline-block;background:#FF4500;color:white;padding:14px 40px;border-radius:8px;text-decoration:none;font-weight:bold;font-size:16px;">VIEW FULL BLUEPRINT</a>
        </div>

        <div style="color:#64748B;font-size:11px;text-align:center;border-top:1px solid #2A3A52;padding-top:16px;">
            {feasibility}<br><br>
            Log in with your license key to see the full blueprint, download files, and forge more builds.<br><br>
            <strong style="color:#FF4500;">Want more builds?</strong> Upgrade at bobtherobotbuilder.com<br><br>
            AoC3P0 Systems | The Builder Foundry | Conception DNA Architecture
        </div>
    </div>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Your Blueprint is Ready: {project_type}"
        msg["From"]    = f"Builder Foundry <{GMAIL_ADDRESS}>"
        msg["To"]      = user_email
        msg.attach(MIMEText(f"Your blueprint for {project_type} is ready. Log in at bobtherobotbuilder.com to view it.", "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PW)
            server.send_message(msg)

        _log_event("blueprint_email_sent", user=user_email, project=project_type[:30])
        return True
    except Exception as e:
        _log_event("blueprint_email_failed", user=user_email, error=str(e)[:100])
        return False


# ── UTILITIES ─────────────────────────────────────────────────────────────────

def _truncate(text: str, max_chars: int = 5000) -> str:
    """Truncate at paragraph/sentence boundary."""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    for sep in ["\n\n", ".\n", ". ", "\n"]:
        idx = cut.rfind(sep)
        if idx > max_chars * 0.7:
            return cut[:idx + 1]
    return cut


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4


def _token_budget_check(texts: list, max_tokens: int, label: str) -> list:
    """
    Check if combined input texts would exceed token budget.
    If too high, truncate the longest text proportionally.
    Returns the (possibly truncated) list.
    """
    total = sum(_estimate_tokens(t) for t in texts)
    if total <= max_tokens:
        return texts

    ratio = max_tokens / max(total, 1)
    _log_event("token_budget_exceeded", label=label,
               estimated=total, budget=max_tokens, ratio=round(ratio, 2))

    # Truncate each text proportionally
    result = []
    for t in texts:
        new_len = int(len(t) * ratio * 0.9)  # 10% safety margin
        result.append(_truncate(t, max_len) if (max_len := new_len) < len(t) else t)
    return result


class _Timer:
    """Context manager for timing agent execution."""
    def __init__(self, name: str):
        self.name = name
        self.elapsed = 0.0
    def __enter__(self):
        self._start = _time.time()
        return self
    def __exit__(self, *args):
        self.elapsed = round(_time.time() - self._start, 1)
        _log_event("agent_timing", agent=self.name, elapsed_s=self.elapsed)


async def _retry_async(coro_fn, *args, max_attempts: int = 3,
                       base_delay: float = 4.0, label: str = "LLM"):
    """
    Retry an async function with exponential backoff.
    Handles 429s and transient failures without tenacity dependency.
    """
    last_err = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await coro_fn(*args)
        except Exception as e:
            last_err = e
            err_str = str(e).lower()
            is_retryable = any(k in err_str for k in ["429", "rate", "timeout", "overloaded", "503"])
            if not is_retryable or attempt == max_attempts:
                _log_event("retry_exhausted", label=label, attempt=attempt, error=str(e)[:200])
                raise
            delay = base_delay * (2 ** (attempt - 1))
            _log_event("retry_backoff", label=label, attempt=attempt, delay_s=delay, error=str(e)[:100])
            await asyncio.sleep(delay)
    raise last_err


# ══════════════════════════════════════════════════════════════════════════════
# CONCEPTION MEMORY HOOKS
# ══════════════════════════════════════════════════════════════════════════════

async def _recall_conception_memory(user_email: str, junk_desc: str,
                                    project_type: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                f"{CONCEPTION_URL}/conception/recall",
                json={"user_email": user_email, "context": f"{project_type}: {junk_desc[:500]}",
                       "inventory": junk_desc[:500], "project_type": project_type},
                headers=_h(),
            )
        if resp.status_code == 200:
            ctx = resp.json().get("context_string") or resp.json().get("context", "")
            return ctx
    except Exception as e:
        log.warning("Conception recall skipped: %s", e)
    return ""


async def _absorb_into_conception(user_email: str, junk_desc: str,
                                   project_type: str, blueprint: str,
                                   grok_notes: str, claude_notes: str,
                                   build_id: int, tokens_used: int) -> None:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{CONCEPTION_URL}/conception/absorb",
                json={"build_id": build_id, "user_email": user_email,
                       "junk_desc": junk_desc[:2000], "project_type": project_type,
                       "blueprint": blueprint[:5000], "grok_notes": grok_notes[:2000],
                       "claude_notes": claude_notes[:1000], "tokens_used": tokens_used},
                headers=_h(),
            )
        if resp.status_code == 200:
            data = resp.json()
            _log_event("conception_absorb", build_id=build_id,
                       domain=data.get("domain", "?"), patterns=data.get("patterns_extracted", 0))
    except Exception as e:
        log.warning("Conception absorb failed: %s", e)


# ══════════════════════════════════════════════════════════════════════════════
# GROK FAILURE DETECTION
# ══════════════════════════════════════════════════════════════════════════════

def _grok_failed(analysis) -> bool:
    """Detect if Grok returned garbage. Works for both JSON dict and string."""
    if isinstance(analysis, dict):
        return len(analysis.get("components", [])) == 0
    if isinstance(analysis, str):
        if len(analysis) < 50:
            return True
        markers = ["offline", "unavailable", "error", "timed out", "unexpected"]
        return any(m in analysis.lower() for m in markers)
    return True


# ══════════════════════════════════════════════════════════════════════════════
# AGENT 1: GROK-4.2 — STRUCTURED JSON OUTPUT
# ══════════════════════════════════════════════════════════════════════════════

async def _run_grok_inner(junk_desc: str, project_type: str,
                          detail_level: str, conception_context: str,
                          mode: str = "blueprint") -> dict:
    if not GROK_KEY:
        return {"analysis": {"components": [], "feasibility_score": 0,
                "analysis_summary": "Grok offline."}, "tokens": 0}

    timeouts = {"Standard": 40.0, "Industrial": 60.0, "Experimental": 80.0}
    max_toks = {"Standard": 2000, "Industrial": 3000, "Experimental": 4000}

    if mode == "mechanic":
        system = _mechanic_grok_system(detail_level, conception_context)
        user_msg = (
            f"{project_type}\n\n"
            f"AVAILABLE TOOLS & PARTS:\n{_truncate(junk_desc, 3000)}\n\n"
            f"Diagnose the issue. Return ONLY the JSON structure."
        )
    elif mode == "quote_check":
        system = _quote_check_grok_system(conception_context)
        user_msg = (
            f"{project_type}\n\n"
            f"Analyze what this repair should cost. Return ONLY the JSON structure."
        )
    else:
        detail_instructions = {
            "Standard": "Identify major harvestable components from each item.",
            "Industrial": (
                "For each component: specify exact voltages, current ratings, "
                "torque values, dimensions, weight, material grade. "
                "Calculate mechanical advantage of gear/belt systems."
            ),
            "Experimental": (
                "Maximum depth. Exact electrical specs, mechanical specs, thermal specs, "
                "dimensional specs. Identify hidden value: capacitors, rare earth magnets, "
                "precision surfaces, high-quality bearings. Estimate remaining life span."
            ),
        }
        system = (
            f"You are GROK-4.2, a junkyard engineering genius on AoC3P0 Builder Foundry.\n\n"
            f"RULES:\n"
            f"- PROJECT GOAL = what the user wants to BUILD (they don't have it yet)\n"
            f"- INVENTORY = physical items the user ALREADY OWNS\n"
            f"- Analyze each inventory item for harvestable components\n"
            f"- Mark specs as [KNOWN] or [EST]\n\n"
            f"CREATIVE ENGINEERING: suggest UNEXPECTED uses for each component. "
            f"Think about what makes each item UNIQUE.\n\n"
            f"Detail level: {detail_level}. {detail_instructions.get(detail_level, '')}\n\n"
            f"Return ONLY valid JSON with this exact structure:\n"
            f'{{\n'
            f'  "components": [\n'
            f'    {{\n'
            f'      "item_source": "name of inventory item",\n'
            f'      "harvested_parts": [\n'
            f'        {{\n'
            f'          "part": "component name",\n'
            f'          "specs": "voltage, torque, dimensions etc with [KNOWN]/[EST] tags",\n'
            f'          "project_use": "how this part serves the project goal",\n'
            f'          "confidence": "high|medium|low"\n'
            f'        }}\n'
            f'      ]\n'
            f'    }}\n'
            f'  ],\n'
            f'  "feasibility_score": 0-100,\n'
            f'  "critical_gaps": ["list of missing essentials"],\n'
            f'  "honest_limitations": ["what this build cannot do"],\n'
            f'  "creative_possibilities": [\n'
            f'    {{"idea": "description", "why_unique": "why this inventory enables it"}}\n'
            f'  ],\n'
            f'  "analysis_summary": "2-3 paragraph prose summary"\n'
            f'}}\n'
            + (f"\nCONCEPTION BRIEF:\n{conception_context}" if conception_context else "")
        )
        user_msg = (
            f"WHAT I WANT TO BUILD:\n{project_type}\n\n"
            f"WHAT I ACTUALLY HAVE:\n{_truncate(junk_desc, 3000)}\n\n"
            f"Analyze every item. Return ONLY the JSON structure."
        )

    # Token budget check
    texts = [system, user_msg]
    texts = _token_budget_check(texts, max_toks.get(detail_level, 2000) * 2, "grok_input")

    try:
        async with httpx.AsyncClient(timeout=timeouts.get(detail_level, 40.0)) as client:
            resp = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROK_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "grok-4.20-beta-0309-reasoning",
                    "messages": [
                        {"role": "system", "content": texts[0]},
                        {"role": "user", "content": texts[1]},
                    ],
                    "max_tokens": max_toks.get(detail_level, 2000),
                    "temperature": 0.3,
                },
            )

        if resp.status_code == 200:
            d = resp.json()
            try:
                content = d["choices"][0]["message"]["content"]
            except (KeyError, IndexError):
                return {"analysis": "Grok returned unexpected format.", "tokens": 0}

            tokens = d.get("usage", {}).get("total_tokens", 0)

            # Try to parse as JSON
            try:
                clean = content.strip()
                if clean.startswith("```"):
                    clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
                if clean.endswith("```"):
                    clean = clean[:-3].strip()
                parsed = json.loads(clean)
                return {"analysis": parsed, "tokens": tokens}
            except json.JSONDecodeError:
                # Grok didn't return valid JSON — fall back to raw text
                _log_event("grok_json_fallback", reason="invalid JSON from Grok")
                return {"analysis": content, "tokens": tokens}

        # Any non-200 raises so the retry wrapper can handle it
        raise Exception(f"Grok API returned HTTP {resp.status_code}")

    except httpx.TimeoutException:
        raise Exception(f"Grok timeout at {detail_level}")


async def _run_grok(junk_desc: str, project_type: str,
                    detail_level: str, conception_context: str,
                    mode: str = "blueprint") -> dict:
    """Grok with retry wrapper."""
    try:
        return await _retry_async(
            _run_grok_inner, junk_desc, project_type, detail_level, conception_context, mode,
            max_attempts=2, base_delay=5.0, label="Grok"
        )
    except Exception as e:
        log.error("Grok failed after retries: %s", e)
        return {"analysis": f"Grok unavailable: {e}", "tokens": 0}


def _format_grok_for_claude(grok_analysis) -> str:
    """Convert Grok's structured JSON back to readable text for Claude's prompt."""
    if isinstance(grok_analysis, str):
        return grok_analysis  # Already text (fallback mode)

    if not isinstance(grok_analysis, dict):
        return "No Grok analysis available."

    lines = []
    lines.append(f"FEASIBILITY SCORE: {grok_analysis.get('feasibility_score', '?')}/100\n")

    for item in grok_analysis.get("components", []):
        lines.append(f"FROM: {item.get('item_source', '?')}")
        for part in item.get("harvested_parts", []):
            lines.append(f"  - {part.get('part', '?')}: {part.get('specs', '?')}")
            lines.append(f"    Use: {part.get('project_use', '?')} [{part.get('confidence', '?')}]")
        lines.append("")

    gaps = grok_analysis.get("critical_gaps", [])
    if gaps:
        lines.append("CRITICAL GAPS: " + ", ".join(gaps))

    limits = grok_analysis.get("honest_limitations", [])
    if limits:
        lines.append("LIMITATIONS: " + ", ".join(limits))

    for idea in grok_analysis.get("creative_possibilities", []):
        lines.append(f"CREATIVE IDEA: {idea.get('idea', '?')} — {idea.get('why_unique', '')}")

    summary = grok_analysis.get("analysis_summary", "")
    if summary:
        lines.append(f"\nSUMMARY:\n{summary}")

    return "\n".join(lines)


def _format_grok_for_mechanic(grok_analysis) -> str:
    """Convert mechanic-mode Grok JSON to readable text for Claude."""
    if isinstance(grok_analysis, str):
        return grok_analysis

    if not isinstance(grok_analysis, dict):
        return "No diagnostic analysis available."

    lines = []
    lines.append(f"FIELD FIX CONFIDENCE: {grok_analysis.get('field_fix_confidence', '?')}/100")
    lines.append(f"CAN FIX IN FIELD: {grok_analysis.get('can_fix_in_field', '?')}\n")

    for d in grok_analysis.get("diagnosis", []):
        lines.append(f"LIKELY CAUSE [{d.get('probability', '?')}]: {d.get('likely_cause', '?')}")
        lines.append(f"  Verify: {d.get('how_to_verify', '?')}")
        lines.append(f"  Symptoms: {d.get('symptoms_match', '?')}")
        lines.append("")

    ruled = grok_analysis.get("ruled_out", [])
    if ruled:
        lines.append(f"ALREADY RULED OUT: {', '.join(ruled)}\n")

    specs = grok_analysis.get("engine_specs", {})
    if specs:
        lines.append("ENGINE SPECS:")
        skip_keys = {"common_issues", "common_issues_at_this_mileage"}
        for k, v in specs.items():
            if k not in skip_keys:
                lines.append(f"  {k}: {v}")
        issues = specs.get("common_issues_at_this_mileage") or specs.get("common_issues", [])
        if issues:
            lines.append(f"  COMMON ISSUES AT THIS MILEAGE: {', '.join(issues)}")
        lines.append("")

    warning = grok_analysis.get("critical_warning", "")
    if warning:
        lines.append(f"CRITICAL WARNING: {warning}\n")

    summary = grok_analysis.get("diagnostic_summary", "")
    if summary:
        lines.append(f"SUMMARY:\n{summary}")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# AGENT 2: CLAUDE — BLUEPRINT (markdown output, structured input)
# ══════════════════════════════════════════════════════════════════════════════

def _run_claude_sync(junk_desc: str, project_type: str,
                     grok_analysis, detail_level: str,
                     conception_context: str, grok_ok: bool,
                     mode: str = "blueprint", research_text: str = "") -> dict:
    if not ANTHROPIC_KEY:
        return {"blueprint": "Claude offline.", "tokens": 0}

    token_limit = {"Standard": 4000, "Industrial": 6000, "Experimental": 8000}
    max_out = token_limit.get(detail_level, 4000)

    if mode == "mechanic":
        system = _mechanic_claude_system(detail_level, conception_context, grok_ok)
        grok_text = _format_grok_for_mechanic(grok_analysis)
        grok_text = _truncate(grok_text, 4000)
        tools_text = _truncate(junk_desc, 3000)

        user_content = (
            f"GROK-4.2 DIAGNOSTIC ANALYSIS:\n{grok_text}\n\n"
            + (f"{research_text}\n\n" if research_text else "")
            + f"REPAIR REQUEST:\n{project_type}\n\n"
            f"AVAILABLE TOOLS & PARTS:\n{tools_text}\n\n"
            f"Write the complete field repair procedure. Use ONLY available tools. "
            f"Include the emergency jury-rig option. DO NOT suggest anything "
            f"listed under ALREADY TRIED. "
            f"Reference real forum fixes, TSB numbers, and part prices from the "
            f"web research when available. Include a REFERENCES section with links."
        )
    elif mode == "quote_check":
        system = _quote_check_claude_system(conception_context)
        grok_text = (json.dumps(grok_analysis, indent=2) if isinstance(grok_analysis, dict)
                     else str(grok_analysis))
        grok_text = _truncate(grok_text, 4000)

        user_content = (
            f"GROK-4.2 COST ANALYSIS:\n{grok_text}\n\n"
            + (f"{research_text}\n\n" if research_text else "")
            + f"QUOTE TO CHECK:\n{project_type}\n\n"
            f"Write the complete quote analysis. Be honest — if the quote is fair, "
            f"say so. Include real part prices from web research. Check for recalls "
            f"and extended warranties. Give the vehicle owner a clear action plan."
        )
    else:
        detail_map = {
            "Standard": (
                "Complete blueprint with 10 sections. "
                "Include specific measurements and dimensions."
            ),
            "Industrial": (
                "Industrial-grade. 10 standard sections PLUS: "
                "POWER BUDGET, TORQUE CALCULATIONS, WEIGHT DISTRIBUTION, "
                "WIRING DIAGRAM, BILL OF MATERIALS, TOLERANCES."
            ),
            "Experimental": (
                "Research-grade. Everything in Industrial PLUS: "
                "FAILURE MODE ANALYSIS, THERMAL ANALYSIS, FATIGUE LIFE, "
                "CONTROL SYSTEM with PID, ALTERNATIVE DESIGNS, "
                "PERFORMANCE ENVELOPE, UPGRADE PATH."
            ),
        }

        grok_warning = ""
        if not grok_ok:
            grok_warning = (
                "\n\nWARNING: Grok's inventory analysis failed. You MUST analyze "
                "the raw inventory yourself. Do NOT rely on the Grok section below.\n"
            )

        system = (
            "You are CLAUDE-SONNET, a senior mechanical engineer on AoC3P0 Builder Foundry.\n\n"
            "CRITICAL: PROJECT GOAL is what user wants to BUILD. INVENTORY is what they OWN.\n\n"
            "DESIGN ORIGINALITY: Do NOT copy commercial designs. INVENT a novel mechanism "
            "based on what the inventory provides. Propose 2+ approaches in the overview.\n\n"
            "MATERIALS: Every part must trace to a specific inventory item.\n"
            "Exception: basic consumables (fasteners, wires, adhesives).\n\n"
            "HONESTY: Carry [EST] tags forward. Section 9: HONEST ASSESSMENT & GAPS. "
            "Section 10: BUDGET GAP-FILLER SHOPPING LIST (Harbor Freight, salvage first).\n\n"
            "10 SECTIONS: 1-Overview, 2-Materials Manifest, 3-Tools, 4-Assembly Sequence, "
            "5-Technical Specs, 6-Safety, 7-Testing, 8-Modifications, "
            "9-Honest Assessment, 10-Budget Gap-Filler.\n\n"
            + detail_map.get(detail_level, detail_map["Standard"])
            + grok_warning
            + (f"\nCONCEPTION BRIEF:\n{conception_context}" if conception_context else "")
        )

        grok_text = _format_grok_for_claude(grok_analysis)
        grok_text = _truncate(grok_text, 4000)
        inventory_text = _truncate(junk_desc, 3000)

        user_content = (
            f"GROK-4.2 INVENTORY ANALYSIS:\n{grok_text}\n\n"
            + (f"{research_text}\n\n" if research_text else "")
            + f"PROJECT GOAL:\n{project_type}\n\n"
            f"RAW INVENTORY:\n{inventory_text}\n\n"
            f"Generate the complete blueprint. Every material must reference "
            f"which inventory item it came from. Reference real maker projects, "
            f"part prices, and build videos from the web research when available. "
            f"Include a REFERENCES section with links."
        )

    # Token budget check on input
    input_estimate = _estimate_tokens(system + user_content)
    if input_estimate > 12000:
        _log_event("claude_input_truncated", estimated_tokens=input_estimate)
        user_content = _truncate(user_content, 8000)

    try:
        client = _get_anthropic()
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_out,
            temperature=0.1,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        )
        return {
            "blueprint": resp.content[0].text,
            "tokens": resp.usage.input_tokens + resp.usage.output_tokens,
        }
    except Exception as e:
        log.error("Claude failed: %s", e)
        return {"blueprint": f"Claude unavailable: {e}", "tokens": 0}


async def _run_claude(junk_desc: str, project_type: str,
                      grok_analysis, detail_level: str,
                      conception_context: str, grok_ok: bool = True,
                      mode: str = "blueprint", research_text: str = "") -> dict:
    return await asyncio.to_thread(
        _run_claude_sync, junk_desc, project_type,
        grok_analysis, detail_level, conception_context, grok_ok, mode,
        research_text
    )


# ══════════════════════════════════════════════════════════════════════════════
# GEMINI — WEB RESEARCH AGENT (runs parallel with Grok)
# ══════════════════════════════════════════════════════════════════════════════

async def _run_gemini_research(project_type: str, mode: str = "blueprint") -> dict:
    """Gemini searches the web for real-world data relevant to the build/repair."""
    _empty = {"research": {}, "tokens": 0}
    if not GEMINI_KEY or not _GENAI_AVAILABLE:
        return _empty

    model = genai.GenerativeModel("gemini-2.5-flash")

    if mode == "mechanic" or mode == "quote_check":
        prompt = (
            f"Search the web for real-world repair information about this problem.\n\n"
            f"{project_type}\n\n"
            f"Search for:\n"
            f"1. Forum threads from mechanics who fixed this exact problem (iBoats, "
            f"CumminsForum, TheDieselStop, FixYa, JustAnswer, etc.)\n"
            f"2. Technical Service Bulletins (TSBs) related to this symptom\n"
            f"3. NHTSA complaints and recalls for this vehicle/engine\n"
            f"4. Extended warranty or special service campaigns\n"
            f"5. Replacement parts with real pricing and part numbers "
            f"(RockAuto, Amazon, dealer sites, MarinePartsSource)\n"
            f"6. YouTube repair walkthrough videos for this specific repair\n"
            f"7. Wiring diagrams or schematics relevant to this repair\n\n"
            f"Return JSON only — no markdown, no preamble:\n"
            f'{{\n'
            f'  "forum_fixes": [{{"source":"...","url":"...","summary":"what fixed it","verified":true}}],\n'
            f'  "tsbs": [{{"number":"...","title":"...","summary":"...","source_url":"..."}}],\n'
            f'  "nhtsa_complaints": {{"count":0,"top_complaint":"...","investigation_id":"..."}},\n'
            f'  "recalls": [{{"number":"...","description":"...","remedy":"..."}}],\n'
            f'  "extended_warranties": [{{"campaign":"...","description":"...","coverage":"..."}}],\n'
            f'  "parts_pricing": [{{"part":"...","part_numbers":["..."],"prices":[{{"source":"...","price":"...","url":"..."}}]}}],\n'
            f'  "youtube_videos": [{{"title":"...","url":"...","duration":"..."}}],\n'
            f'  "schematics": [{{"description":"...","source_url":"..."}}],\n'
            f'  "research_summary": "2-paragraph summary"\n'
            f'}}\n'
        )
    else:
        # Forge / blueprint mode
        prompt = (
            f"Search the web for real-world maker projects and parts related to this build.\n\n"
            f"PROJECT: {project_type}\n\n"
            f"Search for:\n"
            f"1. Similar maker projects on Instructables, Hackaday, or maker blogs\n"
            f"2. YouTube build videos for similar projects\n"
            f"3. Gap-filler parts pricing from Harbor Freight, Amazon, eBay\n"
            f"4. 3D printable parts on Thingiverse that could help\n"
            f"5. Safety considerations specific to this type of build\n\n"
            f"Return JSON only — no markdown, no preamble:\n"
            f'{{\n'
            f'  "similar_projects": [{{"title":"...","source":"Instructables","url":"...","key_insight":"..."}}],\n'
            f'  "youtube_builds": [{{"title":"...","url":"...","duration":"...","relevance":"..."}}],\n'
            f'  "gap_parts_pricing": [{{"part":"...","source":"Harbor Freight","price":"...","url":"..."}}],\n'
            f'  "printable_parts": [{{"part":"...","source":"Thingiverse","url":"..."}}],\n'
            f'  "safety_notes": ["..."],\n'
            f'  "research_summary": "2-paragraph summary"\n'
            f'}}\n'
        )

    try:
        # Use Google Search grounding
        from google.generativeai.types import content_types
        resp = await model.generate_content_async(
            prompt,
            tools="google_search_retrieval",
        )
        text = resp.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3].strip()
        research = json.loads(text)
        _log_event("gemini_research_complete", mode=mode, keys=list(research.keys()))
        return {"research": research, "tokens": 0}
    except json.JSONDecodeError:
        _log_event("gemini_research_json_error", mode=mode)
        return _empty
    except Exception as e:
        _log_event("gemini_research_failed", error=str(e)[:200])
        # Fallback — try without grounding tool
        try:
            resp = await model.generate_content_async(prompt)
            text = resp.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3].strip()
            research = json.loads(text)
            return {"research": research, "tokens": 0}
        except Exception as e2:
            _log_event("gemini_research_fallback_failed", error=str(e2)[:200])
            return _empty


def _format_research_for_claude(research: dict, mode: str = "blueprint") -> str:
    """Convert Gemini's web research JSON into readable text for Claude."""
    if not research:
        return ""

    lines = ["WEB RESEARCH (from Gemini):"]

    if mode in ("mechanic", "quote_check"):
        for fix in research.get("forum_fixes", [])[:5]:
            lines.append(f"\nFORUM FIX ({fix.get('source', '?')}):")
            lines.append(f"  {fix.get('summary', '?')}")
            if fix.get('url'):
                lines.append(f"  URL: {fix['url']}")

        for tsb in research.get("tsbs", [])[:3]:
            lines.append(f"\nTSB {tsb.get('number', '?')}: {tsb.get('title', '?')}")
            lines.append(f"  {tsb.get('summary', '?')}")

        nhtsa = research.get("nhtsa_complaints", {})
        if nhtsa.get("count"):
            lines.append(f"\nNHTSA: {nhtsa['count']} complaints filed")
            lines.append(f"  Top complaint: {nhtsa.get('top_complaint', '?')}")

        for recall in research.get("recalls", [])[:3]:
            lines.append(f"\nRECALL {recall.get('number', '?')}: {recall.get('description', '?')}")
            lines.append(f"  Remedy: {recall.get('remedy', '?')}")

        for ew in research.get("extended_warranties", [])[:2]:
            lines.append(f"\nEXTENDED WARRANTY: {ew.get('campaign', '?')}")
            lines.append(f"  {ew.get('description', '?')}")

        for part in research.get("parts_pricing", [])[:5]:
            lines.append(f"\nPART: {part.get('part', '?')} — PN: {', '.join(part.get('part_numbers', []))}")
            for p in part.get("prices", [])[:3]:
                lines.append(f"  {p.get('source', '?')}: {p.get('price', '?')}")

        for vid in research.get("youtube_videos", [])[:3]:
            lines.append(f"\nVIDEO: {vid.get('title', '?')} ({vid.get('duration', '?')})")
            lines.append(f"  {vid.get('url', '?')}")

    else:
        for proj in research.get("similar_projects", [])[:3]:
            lines.append(f"\nSIMILAR PROJECT ({proj.get('source', '?')}): {proj.get('title', '?')}")
            lines.append(f"  Insight: {proj.get('key_insight', '?')}")
            if proj.get('url'):
                lines.append(f"  URL: {proj['url']}")

        for vid in research.get("youtube_builds", [])[:3]:
            lines.append(f"\nYOUTUBE: {vid.get('title', '?')} ({vid.get('duration', '?')})")
            lines.append(f"  {vid.get('url', '?')}")

        for part in research.get("gap_parts_pricing", [])[:5]:
            lines.append(f"\nPART: {part.get('part', '?')} — {part.get('source', '?')}: {part.get('price', '?')}")

        for note in research.get("safety_notes", [])[:3]:
            lines.append(f"\nSAFETY: {note}")

    summary = research.get("research_summary", "")
    if summary:
        lines.append(f"\nRESEARCH SUMMARY:\n{summary}")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# AGENT 3: GEMINI — QUALITY REVIEW (with retry)
# ══════════════════════════════════════════════════════════════════════════════

_GEMINI_OFFLINE = {
    "review_notes": "Gemini offline.", "inventory_usage_score": 0,
    "safety_flags": [], "innovations": [], "difficulty_rating": "Unknown",
    "estimated_build_time": "Unknown", "estimated_cost_usd": "Unknown",
    "tags": [], "conception_ready": False,
}


async def _run_gemini_inner(blueprint: str, project_type: str,
                             conception_context: str) -> dict:
    if not GEMINI_KEY or not _GENAI_AVAILABLE:
        return {"notes": _GEMINI_OFFLINE, "tokens": 0}

    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        generation_config={"response_mime_type": "application/json", "temperature": 0.1},
    )

    prompt = (
        "Review this engineering blueprint. Return JSON only:\n"
        '{"review_notes":"...", "inventory_usage_score":0-100, '
        '"safety_flags":[], "innovations":[], '
        '"difficulty_rating":"Beginner|Intermediate|Advanced|Expert", '
        '"estimated_build_time":"...", "estimated_cost_usd":"...", '
        '"tags":[], "conception_ready":true/false}\n'
        + (f"CONTEXT: {conception_context}\n" if conception_context else "")
        + f"BLUEPRINT:\n{_truncate(blueprint, 3000)}\nPROJECT: {project_type}"
    )

    resp = await model.generate_content_async(prompt)
    text = resp.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3].strip()
    notes = json.loads(text)
    return {"notes": notes, "tokens": 0}


async def _run_gemini(blueprint: str, project_type: str,
                      conception_context: str) -> dict:
    try:
        return await _retry_async(
            _run_gemini_inner, blueprint, project_type, conception_context,
            max_attempts=2, base_delay=4.0, label="Gemini"
        )
    except json.JSONDecodeError:
        _log_event("gemini_json_error")
        return {"notes": {**_GEMINI_OFFLINE, "review_notes": "Gemini returned invalid JSON."}, "tokens": 0}
    except Exception as e:
        log.error("Gemini failed: %s", e)
        return {"notes": {**_GEMINI_OFFLINE, "review_notes": f"Gemini error: {e}"}, "tokens": 0}


# ══════════════════════════════════════════════════════════════════════════════
# AGENT 4: CLAUDE — SVG SCHEMATIC (with retry)
# ══════════════════════════════════════════════════════════════════════════════

def _generate_schematic_sync(blueprint: str, project_type: str,
                              junk_desc: str, max_excerpt: int = 2000) -> str:
    if not ANTHROPIC_KEY:
        return ""

    system = (
        "You are a technical illustrator. Return ONLY valid SVG code.\n\n"
        "RULES: output starts with <svg ends with </svg>. Nothing else.\n"
        "Allowed: svg, rect, text, line, g, circle, ellipse, polygon, path.\n"
        "No foreignObject/image/style/script/defs. Inline styling only.\n"
        "font-family='Arial, sans-serif'. viewBox='0 0 800 550'.\n\n"
        "DRAW the project as it would LOOK assembled. Side-view.\n"
        "Use shapes for real form, not labeled rectangles.\n\n"
        "LABELS: leader lines to left/right sides. Bold 10px name + 8px gray source.\n"
        "COLORS: Structure=#2563EB, Motors=#DC2626, Electronics=#16A34A, "
        "Sensors=#9333EA, Belts=#D97706. All opacity=0.2.\n"
        "Title top-left, dimension lines, color legend bottom-right."
    )

    try:
        client = _get_anthropic()
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            temperature=0.0,
            system=system,
            messages=[{
                "role": "user",
                "content": (
                    f"Draw: {project_type}\n"
                    f"Inventory: {_truncate(junk_desc, 500)}\n"
                    f"Blueprint:\n{_truncate(blueprint, max_excerpt)}\n"
                    f"Output ONLY <svg>...</svg>."
                ),
            }],
        )
        svg = resp.content[0].text.strip()
        start = svg.find("<svg")
        end = svg.rfind("</svg>")
        if start == -1 or end == -1:
            return ""
        svg = svg[start:end + 6].replace("```", "").replace("`", "")
        if len(svg) > 20000:
            return ""
        return svg
    except Exception as e:
        log.error("Schematic failed: %s", e)
        return ""


async def _generate_schematic(blueprint: str, project_type: str,
                               junk_desc: str) -> str:
    # Smart excerpt sizing: shorter blueprints get more context, huge ones get trimmed
    bp_tokens = _estimate_tokens(blueprint)
    if bp_tokens < 2000:
        first_try = min(len(blueprint), 2500)
    elif bp_tokens < 4000:
        first_try = 2000
    else:
        first_try = 1500  # Experimental blueprints are huge — keep excerpt short

    svg = await asyncio.to_thread(
        _generate_schematic_sync, blueprint, project_type, junk_desc, first_try
    )
    if svg:
        return svg

    # Retry with half the excerpt
    retry_len = max(first_try // 2, 500)
    _log_event("schematic_retry", first_try=first_try, retry_len=retry_len)
    return await asyncio.to_thread(
        _generate_schematic_sync, blueprint, project_type, junk_desc, retry_len
    )


# ══════════════════════════════════════════════════════════════════════════════
# MECHANIC MODE — FIELD REPAIR PROMPTS
# ══════════════════════════════════════════════════════════════════════════════

def _mechanic_grok_system(detail_level: str, conception_context: str) -> str:
    """Grok system prompt for mechanic/field repair mode."""
    return (
        "You are GROK-4.2, a master diesel, marine, and automotive mechanic on AoC3P0 Builder Foundry.\n\n"
        "The user is a FIELD MECHANIC — they may be on a boat in the ocean, at a remote "
        "job site, or stranded with limited tools. They need PRACTICAL answers they can "
        "act on RIGHT NOW with what they have.\n\n"
        "INPUTS (you will receive all of these):\n"
        "- VEHICLE: Year, make, model (car, boat, equipment, etc.)\n"
        "- ENGINE: Specific engine model if known\n"
        "- MILEAGE/HOURS: How much use the vehicle/equipment has\n"
        "- ENVIRONMENT: Marine, automotive, heavy equipment, agricultural, etc.\n"
        "- SYMPTOM/FAULT: What's wrong — symptoms, fault codes, or observed behavior\n"
        "- ALREADY TRIED: What the mechanic has already done — DO NOT suggest these again\n"
        "- AVAILABLE TOOLS/PARTS: What they physically have RIGHT NOW\n\n"
        "CRITICAL RULES:\n"
        "- Use the MILEAGE/HOURS to inform your diagnosis — a 3000-hour diesel has "
        "different likely failures than a 300-hour diesel\n"
        "- NEVER suggest something the mechanic already tried — acknowledge it and move past it\n"
        "- Be SPECIFIC to the exact vehicle and engine, not generic\n"
        "- If the vehicle is a boat, consider marine-specific issues (raw water, corrosion, "
        "zincs, sea strainers, heat exchangers)\n\n"
        "YOUR JOB — DIAGNOSTIC ANALYSIS:\n"
        "Return ONLY valid JSON with this structure:\n"
        '{\n'
        '  "diagnosis": [\n'
        '    {\n'
        '      "likely_cause": "description",\n'
        '      "probability": "high|medium|low",\n'
        '      "how_to_verify": "specific test using AVAILABLE tools",\n'
        '      "symptoms_match": "which reported symptoms point to this cause"\n'
        '    }\n'
        '  ],\n'
        '  "ruled_out": ["things already tried that eliminate certain causes"],\n'
        '  "engine_specs": {\n'
        '    "displacement": "...", "power": "...", "torque": "...",\n'
        '    "oil_capacity": "...", "oil_type": "...",\n'
        '    "coolant_capacity": "...", "fuel_system": "...",\n'
        '    "common_issues_at_this_mileage": ["known problems at this age/hours"]\n'
        '  },\n'
        '  "critical_warning": "anything that could make it WORSE",\n'
        '  "can_fix_in_field": true/false,\n'
        '  "field_fix_confidence": 0-100,\n'
        '  "diagnostic_summary": "2-paragraph summary"\n'
        '}\n\n'
        "HONESTY: If you're not sure about a spec, mark it [EST]. If the engine is "
        "unfamiliar, say so. A wrong spec on a marine diesel can sink a boat.\n"
        + (f"\nCONCEPTION BRIEF:\n{conception_context}" if conception_context else "")
    )


def _mechanic_claude_system(detail_level: str, conception_context: str,
                             grok_ok: bool) -> str:
    """Claude system prompt for mechanic/field repair mode."""
    grok_warning = ""
    if not grok_ok:
        grok_warning = (
            "\n\nWARNING: The diagnostic agent failed. You MUST diagnose from the "
            "raw symptom description yourself.\n"
        )

    detail_extra = {
        "Standard": "Complete repair procedure with 8 sections.",
        "Industrial": (
            "Industrial-depth procedure. Include: TORQUE SPECS TABLE, "
            "FLUID SPECIFICATIONS, CLEARANCE MEASUREMENTS, WIRING DIAGRAM DESCRIPTION."
        ),
        "Experimental": (
            "Maximum depth. Everything in Industrial PLUS: "
            "ROOT CAUSE ANALYSIS, RELATED SYSTEM CHECKS, "
            "PREVENTIVE MAINTENANCE SCHEDULE, REBUILD SPECS IF APPLICABLE, "
            "ELECTRICAL SYSTEM DIAGNOSTICS."
        ),
    }

    return (
        "You are CLAUDE-SONNET, a senior marine, diesel, and automotive mechanic engineer "
        "on AoC3P0 Builder Foundry.\n\n"
        "The user is a FIELD MECHANIC working in tough conditions — possibly "
        "on a boat at sea, at a remote site, or under time pressure. They need "
        "CLEAR, STEP-BY-STEP instructions they can follow with LIMITED TOOLS.\n\n"
        "YOU WILL RECEIVE:\n"
        "- Vehicle year/make/model and engine\n"
        "- Mileage or hours (use this to inform your diagnosis)\n"
        "- Symptoms and fault codes\n"
        "- What they have ALREADY TRIED — DO NOT repeat these suggestions\n"
        "- Available tools and parts\n\n"
        "WRITE THE REPAIR PROCEDURE WITH THESE SECTIONS:\n"
        "1. QUICK DIAGNOSIS SUMMARY — What's most likely wrong, in plain language\n"
        "2. SAFETY FIRST — What to shut down/disconnect before starting\n"
        "3. DIAGNOSTIC STEPS — Systematic checks to confirm root cause "
        "(skip anything they already tried — acknowledge it was ruled out)\n"
        "4. FIELD REPAIR PROCEDURE — Step-by-step using ONLY available tools/parts\n"
        "5. TORQUE SPECS & MEASUREMENTS — Every bolt, every spec, every tolerance\n"
        "6. EMERGENCY JURY-RIG — If proper repair isn't possible, what's the safe "
        "temporary fix to get them home/to port? What are the RISKS of the temp fix?\n"
        "7. DO NOT DO THIS — Common mistakes that make this problem WORSE\n"
        "8. PARTS NEEDED AT PORT — What to order/buy when they reach civilization\n\n"
        "CRITICAL RULES:\n"
        "- Be SPECIFIC to the vehicle and engine model\n"
        "- Consider MILEAGE/HOURS — high-mileage failures differ from low-mileage ones\n"
        "- NEVER suggest something they already tried — acknowledge it and move on\n"
        "- Torque specs MUST be for the actual engine, marked [KNOWN] or [EST]\n"
        "- If a field fix could cause MORE damage, say so clearly\n"
        "- Always include the 'get home safe' option even if it's imperfect\n"
        "- Use PLAIN MECHANIC LANGUAGE — no academic engineering jargon\n\n"
        + detail_extra.get(detail_level, detail_extra["Standard"])
        + grok_warning
        + (f"\nCONCEPTION BRIEF:\n{conception_context}" if conception_context else "")
    )


# ══════════════════════════════════════════════════════════════════════════════
# QUOTE CHECK MODE — CONSUMER PROTECTION PROMPTS
# ══════════════════════════════════════════════════════════════════════════════

def _quote_check_grok_system(conception_context: str) -> str:
    return (
        "You are GROK-4.2, an expert automotive cost analyst on AoC3P0 Builder Foundry.\n\n"
        "A vehicle owner received a repair quote and wants to know if it's fair.\n\n"
        "Return ONLY valid JSON:\n"
        '{\n'
        '  "repair_analysis": {\n'
        '    "description": "what this repair involves",\n'
        '    "parts_needed": [{"part":"...","fair_price_range":"$X-$Y"}],\n'
        '    "labor_hours_fair": "X-Y hours",\n'
        '    "fair_total_range": "$X-$Y",\n'
        '    "common_upsells": ["unnecessary extras shops add"]\n'
        '  },\n'
        '  "vehicle_context": {\n'
        '    "known_issues": ["common problems at this mileage"],\n'
        '    "recalls_possible": true/false,\n'
        '    "extended_warranty_possible": true/false\n'
        '  },\n'
        '  "quote_assessment": "high|fair|low",\n'
        '  "analysis_summary": "2-paragraph summary"\n'
        '}\n'
        + (f"\nCONCEPTION DATA:\n{conception_context}" if conception_context else "")
    )


def _quote_check_claude_system(conception_context: str) -> str:
    return (
        "You are CLAUDE-SONNET, a consumer advocate and automotive repair expert "
        "on AoC3P0 Builder Foundry.\n\n"
        "A vehicle owner received a repair quote. Write in PLAIN ENGLISH.\n\n"
        "SECTIONS:\n"
        "1. QUOTE VERDICT — FAIR, HIGH, VERY HIGH, or RED FLAG with fair range\n"
        "2. WARRANTY & RECALL CHECK — any coverage that makes this FREE?\n"
        "3. FAIR COST BREAKDOWN — parts + labor table with fair prices\n"
        "4. WHY THE QUOTE MIGHT BE HIGH — dealer markup, padded labor, extras\n"
        "5. WHAT TO DO — step-by-step action plan with what to say\n"
        "6. COMMUNITY DATA — how many others had this, what they paid\n"
        "7. REFERENCES — links, recall databases, parts pricing\n\n"
        "Be HONEST. If the quote IS fair, say so clearly.\n"
        + (f"\nCONCEPTION DATA:\n{conception_context}" if conception_context else "")
    )


# ══════════════════════════════════════════════════════════════════════════════
# FORGE PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

async def _forge_pipeline(user_email: str, junk_desc: str,
                           project_type: str, detail_level: str,
                           mode: str = "blueprint", task=None) -> dict:
    timings = {}
    _heartbeat_active = True
    is_mechanic = (mode in ("mechanic", "quote_check"))

    def _update(msg: str):
        if task:
            task.update_state(state="PROGRESS", meta={"message": msg})

    async def _heartbeat():
        """Send periodic updates so frontend knows we're alive."""
        tick = 0
        while _heartbeat_active:
            await asyncio.sleep(10)
            tick += 1
            if task and _heartbeat_active:
                task.update_state(state="PROGRESS",
                    meta={"message": f"Round Table deliberating... ({tick * 10}s elapsed)"})

    # Start heartbeat
    heartbeat_task = asyncio.ensure_future(_heartbeat())

    try:
        # 0 — Conception memory
        _update("Scanning Conception memory banks...")
        with _Timer("Conception Recall") as t:
            ctx = await _recall_conception_memory(user_email, junk_desc, project_type)
        timings["recall"] = t.elapsed

        # 1 — Grok + Gemini Research IN PARALLEL
        if is_mechanic:
            _update("GROK-4.2 diagnosing engine + GEMINI searching web for real fixes...")
        else:
            _update("GROK-4.2 analyzing inventory + GEMINI searching maker projects...")
        with _Timer("Grok + Gemini Research") as t:
            grok_r, research_r = await asyncio.gather(
                _run_grok(junk_desc, project_type, detail_level, ctx, mode=mode),
                _run_gemini_research(project_type, mode=mode),
            )
        timings["grok_and_research"] = t.elapsed
        grok_analysis = grok_r["analysis"]
        grok_ok = not _grok_failed(grok_analysis)
        web_research = research_r.get("research", {})

        if not grok_ok:
            if is_mechanic:
                _update("GROK-4.2 incomplete — CLAUDE diagnosing from symptoms directly")
            else:
                _update("GROK-4.2 incomplete — CLAUDE analyzing inventory directly")

        # Format research for Claude
        research_text = _format_research_for_claude(web_research, mode=mode)

        # 2 — Claude (gets Grok analysis + Gemini research)
        if is_mechanic:
            _update("CLAUDE writing field repair procedure with real-world data...")
        else:
            _update("CLAUDE drafting engineering blueprint with maker research...")
        with _Timer("Claude Blueprint") as t:
            claude_r = await _run_claude(junk_desc, project_type, grok_analysis,
                                         detail_level, ctx, grok_ok, mode=mode,
                                         research_text=research_text)
        timings["claude"] = t.elapsed
        blueprint = claude_r["blueprint"]

        # 3 + 4 — Gemini Review + Schematic PARALLEL (skip schematic in mechanic mode)
        if is_mechanic:
            _update("GEMINI verifying repair procedure...")
            with _Timer("Gemini Review") as t:
                gemini_r = await _run_gemini(blueprint, project_type, ctx)
            timings["review"] = t.elapsed
            schematic_svg = ""
        else:
            _update("GEMINI reviewing + rendering schematic...")
            with _Timer("Gemini + Schematic") as t:
                gemini_r, schematic_svg = await asyncio.gather(
                    _run_gemini(blueprint, project_type, ctx),
                    _generate_schematic(blueprint, project_type, junk_desc),
                )
            timings["review"] = t.elapsed

    finally:
        _heartbeat_active = False
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

    notes = gemini_r["notes"] if isinstance(gemini_r["notes"], dict) else {}
    total_tokens = grok_r["tokens"] + claude_r["tokens"]

    # ── Cost estimation per agent ──
    costs = {}
    # Grok: we have total tokens, estimate 40% input / 60% output
    grok_tok = grok_r["tokens"]
    costs["grok"] = _estimate_cost("grok", int(grok_tok * 0.4), int(grok_tok * 0.6))
    # Claude: we have exact split from usage
    claude_tok = claude_r["tokens"]
    costs["claude_blueprint"] = _estimate_cost("claude", int(claude_tok * 0.5), int(claude_tok * 0.5))
    # Schematic: estimate ~1K input, ~3K output
    costs["claude_schematic"] = _estimate_cost("claude", 1000, 3000) if schematic_svg else 0
    # Gemini: minimal cost
    costs["gemini"] = _estimate_cost("gemini", 3000, 500)
    costs["total"] = round(sum(costs.values()), 4)

    # 5 — Save to database (async — won't block event loop)
    _update("Archiving to Conception DNA Vault...")
    build_id = None

    def _db_save():
        grok_text = (json.dumps(grok_analysis, indent=2) if isinstance(grok_analysis, dict)
                     else str(grok_analysis))
        research_json = json.dumps(web_research) if web_research else None
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO builds
                        (user_email, junk_desc, project_type, blueprint,
                         grok_notes, claude_notes, tokens_used, conception_ready,
                         mode, web_research)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                    (user_email, junk_desc[:5000], project_type, blueprint,
                     grok_text[:5000], notes.get("review_notes", "")[:2000],
                     total_tokens, notes.get("conception_ready", False),
                     mode, research_json),
                )
                bid = cur.fetchone()[0]
                conn.commit()
        return bid

    try:
        build_id = await asyncio.to_thread(_db_save)
        _log_event("db_save", build_id=build_id)
    except Exception as e:
        log.error("DB save failed: %s", e)

    # 6 — Conception learning
    grok_text_for_absorb = (json.dumps(grok_analysis)[:2000] if isinstance(grok_analysis, dict)
                            else str(grok_analysis)[:2000])
    if build_id:
        await _absorb_into_conception(
            user_email, junk_desc, project_type, blueprint,
            grok_text_for_absorb, notes.get("review_notes", ""),
            build_id, total_tokens,
        )

    # 7 — Email blueprint to user (non-blocking)
    email_sent = await asyncio.to_thread(
        _send_blueprint_email, user_email, project_type, blueprint, build_id, notes
    )

    # Final structured log
    _log_event("forge_complete",
        user=user_email, project=project_type[:30], depth=detail_level,
        total_s=round(sum(timings.values()), 1), timings=timings,
        tokens=total_tokens, costs=costs,
        grok_ok=grok_ok, has_schematic=bool(schematic_svg),
        build_id=build_id, email_sent=email_sent, success=build_id is not None)

    return {
        "status":           "complete",
        "build_id":         build_id,
        "user_email":       user_email,
        "project_type":     project_type,
        "detail_level":     detail_level,
        "content":          blueprint,
        "schematic_svg":    schematic_svg,
        "grok_analysis":    _format_grok_for_claude(grok_analysis) if isinstance(grok_analysis, dict) else grok_analysis,
        "review_notes":     notes.get("review_notes", ""),
        "safety_flags":     notes.get("safety_flags", []),
        "innovations":      notes.get("innovations", []),
        "difficulty":       notes.get("difficulty_rating", "Unknown"),
        "build_time":       notes.get("estimated_build_time", "Unknown"),
        "cost_estimate":    notes.get("estimated_cost_usd", "Unknown"),
        "tags":             notes.get("tags", []),
        "conception_ready": notes.get("conception_ready", False),
        "tokens_used":      total_tokens,
        "agents_used":      ["GROK-4.2", "CLAUDE-SONNET", "GEMINI-2.5-FLASH"],
        "timings":          timings,
        "costs":            costs,
        "grok_ok":          grok_ok,
        "grok_structured":  isinstance(grok_analysis, dict),
        "mode":             mode,
        "web_research":     web_research,
        "conception_context_used": bool(ctx),
        "email_sent":       email_sent,
    }


# ══════════════════════════════════════════════════════════════════════════════
# CELERY TASK
# ══════════════════════════════════════════════════════════════════════════════

@celery_app.task(
    bind=True,
    name="ai_worker.forge_blueprint_task",
    max_retries=2,
    soft_time_limit=300,
    time_limit=330,
)
def forge_blueprint_task(self, user_email: str, junk_desc: str,
                          project_type: str, detail_level: str = "Standard",
                          mode: str = "blueprint"):
    _log_event("forge_started", user=user_email,
               project=project_type[:50], depth=detail_level, mode=mode)
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            _forge_pipeline(user_email, junk_desc, project_type, detail_level,
                           mode=mode, task=self)
        )
    except Exception as e:
        _log_event("forge_failed", user=user_email, error=str(e)[:200],
                   retry=self.request.retries)
        countdown = 10 if self.request.retries == 0 else 30
        raise self.retry(exc=e, countdown=countdown)
    finally:
        loop.close()
