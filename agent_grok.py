"""Agent: Grok 4.2 — Structured JSON diagnostic/analysis."""
import json
import uuid
import httpx
from prompts import mechanic_grok_system, quote_check_grok_system
from worker_config import (
    GROK_KEY, GROK_MODEL, GROK_TEMPERATURE, log, log_event,
    truncate, estimate_tokens, retry_async,
)


# ── Token Budget ──────────────────────────────────────────────────────────────
def _token_budget_check(texts: list[str], max_tokens: int, label: str) -> list[str]:
    """Proportional truncation using real token estimation + 15% safety margin."""
    total = sum(estimate_tokens(t) for t in texts)
    if total <= max_tokens:
        return texts

    safety_ratio = 0.85
    ratio = (max_tokens / max(total, 1)) * safety_ratio

    log_event("token_budget_truncated",
              label=label,
              estimated_tokens=total,
              budget=max_tokens,
              ratio=round(ratio, 3),
              truncated_texts=len([t for t in texts if len(t) > 100]))

    return [truncate(t, int(len(t) * ratio)) for t in texts]


# ── Ultra-Robust JSON Extraction ──────────────────────────────────────────────
def safe_json_extract(content: str) -> dict | str:
    """Multi-strategy JSON extraction — handles every common Grok failure mode."""
    content = content.strip()

    # Strategy 1: Direct JSON
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Strip markdown fences (including ```json)
    for prefix in ["```json", "```"]:
        if content.startswith(prefix):
            content = content[len(prefix):].strip()
            break
    if content.endswith("```"):
        content = content[:-3].strip()

    # Strategy 3: Remove common prefixes Grok sometimes adds
    for bad_prefix in ["Here is the JSON:", "```json\n", "JSON:\n"]:
        if content.startswith(bad_prefix):
            content = content[len(bad_prefix):].strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Strategy 4: Extract largest JSON object anywhere in the response
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start != -1 and end > start + 10:  # at least a tiny object
            candidate = content[start:end]
            return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # Strategy 5: Last resort — return raw text
    log_event("grok_json_fallback", reason="all parsing strategies failed")
    return content


# ── Failure Detection ─────────────────────────────────────────────────────────
def grok_failed(analysis) -> bool:
    """Detect garbage output. Works for both JSON dict and string."""
    if isinstance(analysis, dict):
        # Blueprint mode uses "components", mechanic mode uses "diagnosis"
        has_components = len(analysis.get("components", [])) > 0
        has_diagnosis = bool(analysis.get("diagnosis"))
        return not (has_components or has_diagnosis)

    if isinstance(analysis, str):
        if len(analysis) < 50:
            return True
        markers = ["offline", "unavailable", "error", "timed out", "unexpected", "sorry", "cannot"]
        return any(m in analysis.lower() for m in markers)

    return True


# ── Core Runner ───────────────────────────────────────────────────────────────
async def run_grok_inner(junk_desc: str, project_type: str,
                         detail_level: str, conception_context: str,
                         mode: str = "blueprint") -> dict:
    request_id = str(uuid.uuid4())[:8]
    log_event("grok_call_start", request_id=request_id, mode=mode, detail=detail_level)

    if not GROK_KEY:
        return {"analysis": {"components": [], "feasibility_score": 0,
                "analysis_summary": "Grok offline."}, "tokens": 0}

    timeouts = {"Standard": 40.0, "Industrial": 60.0, "Experimental": 80.0}
    max_toks = {"Standard": 2000, "Industrial": 3000, "Experimental": 4000}

    if mode == "mechanic":
        system = mechanic_grok_system(detail_level, conception_context)
        user_msg = (
            f"{project_type}\n\n"
            f"AVAILABLE TOOLS & PARTS:\n{truncate(junk_desc, 3000)}\n\n"
            f"Diagnose the issue. Return ONLY the JSON structure."
        )
    elif mode == "quote_check":
        system = quote_check_grok_system(conception_context)
        user_msg = (
            f"{project_type}\n\n"
            f"Analyze what this repair should cost. Return ONLY the JSON structure."
        )
    else:
        # Blueprint mode — strengthened originality rule
        detail_instructions = { ... }  # keep your existing dict
        system = (
            f"You are GROK-4.2, a junkyard engineering genius on AoC3P0 Builder Foundry.\n\n"
            f"RULES:\n"
            f"- PROJECT GOAL = what the user wants to BUILD (they don't have it yet)\n"
            f"- INVENTORY = physical items the user ALREADY OWNS\n"
            f"- Analyze each inventory item for harvestable components\n"
            f"- Mark specs as [KNOWN] or [EST]\n\n"
            f"DESIGN ORIGINALITY RULE: You MUST generate original, creative engineering designs. "
            f"NEVER copy, replicate, or closely imitate any existing commercial product. "
            f"Think like a mad inventor in a scrapyard — invent new mechanisms.\n\n"
            f"CREATIVE ENGINEERING: suggest UNEXPECTED uses for each component.\n\n"
            f"Detail level: {detail_level}. {detail_instructions.get(detail_level, '')}\n\n"
            f"Return ONLY valid JSON with this exact structure:\n"
            f'{{\n'
            f'  "components": [ ... ],\n'
            f'  "feasibility_score": 0-100,\n'
            f'  "critical_gaps": [...],\n'
            f'  "honest_limitations": [...],\n'
            f'  "creative_possibilities": [...],\n'
            f'  "analysis_summary": "2-3 paragraph prose summary"\n'
            f'}}\n'
            + (f"\nCONCEPTION BRIEF:\n{conception_context}" if conception_context else "")
        )
        user_msg = (
            f"WHAT I WANT TO BUILD:\n{project_type}\n\n"
            f"WHAT I ACTUALLY HAVE:\n{truncate(junk_desc, 3000)}\n\n"
            f"Analyze every item. Return ONLY the JSON structure."
        )

    # Budget check
    texts = _token_budget_check([system, user_msg], max_toks.get(detail_level, 2000) * 2, "grok_input")

    try:
        async with httpx.AsyncClient(timeout=timeouts.get(detail_level, 40.0)) as client:
            resp = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROK_KEY}", "Content-Type": "application/json"},
                json={
                    "model": GROK_MODEL,
                    "messages": [{"role": "system", "content": texts[0]},
                                 {"role": "user",   "content": texts[1]}],
                    "max_tokens": max_toks.get(detail_level, 2000),
                    "temperature": GROK_TEMPERATURE,
                },
            )

        if resp.status_code == 200:
            d = resp.json()
            content = d["choices"][0]["message"]["content"]
            usage = d.get("usage", {})
            tokens = usage.get("total_tokens", 0)

            analysis = safe_json_extract(content)

            log_event("grok_call_success",
                      request_id=request_id,
                      input_tokens=usage.get("prompt_tokens", 0),
                      output_tokens=usage.get("completion_tokens", 0),
                      total_tokens=tokens,
                      parsed_as_dict=isinstance(analysis, dict))

            return {"analysis": analysis, "tokens": tokens}

        raise Exception(f"Grok HTTP {resp.status_code}")

    except httpx.TimeoutException:
        raise Exception(f"Grok timeout at {detail_level}")
    except Exception as e:
        log_event("grok_call_error", request_id=request_id, error=str(e)[:200])
        raise


# ── Public Entrypoint ─────────────────────────────────────────────────────────
async def run_grok(junk_desc: str, project_type: str,
                   detail_level: str, conception_context: str,
                   mode: str = "blueprint") -> dict:
    """Public entrypoint with retry wrapper."""
    try:
        return await retry_async(
            run_grok_inner, junk_desc, project_type, detail_level,
            conception_context, mode,
            max_attempts=2, base_delay=5.0, label="Grok"
        )
    except Exception as e:
        log.error("Grok failed after retries: %s", e)
        return {"analysis": f"Grok unavailable: {e}", "tokens": 0}


# ── Formatters (unchanged — already excellent) ───────────────────────────────
def format_grok_for_claude(grok_analysis):
    # ... your existing function (kept exactly as-is)
    ...

def format_grok_for_mechanic(grok_analysis):
    # ... your existing function
    ...
