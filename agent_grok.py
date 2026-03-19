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

def _token_budget_check(texts, max_tokens, label):
    """Proportional truncation with safety margin and logging."""
    total = sum(estimate_tokens(t) for t in texts)
    if total <= max_tokens:
        return texts
    safety_ratio = 0.85
    ratio = (max_tokens / max(total, 1)) * safety_ratio
    log_event("token_budget_truncated", label=label,
              estimated=total, budget=max_tokens, ratio=round(ratio, 3))
    return [truncate(t, int(len(t) * ratio)) for t in texts]


# ── JSON Extraction ───────────────────────────────────────────────────────────

def safe_json_extract(content):
    """Multi-strategy JSON extraction from Grok response."""
    content = content.strip()

    # Strategy 1: Direct parse
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Strip markdown fences
    for prefix in ["```json", "```"]:
        if content.startswith(prefix):
            content = content[len(prefix):].strip()
            break
    if content.endswith("```"):
        content = content[:-3].strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Strategy 3: Find largest JSON object in string
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(content[start:end])
    except json.JSONDecodeError:
        pass

    # Strategy 4: Return raw text
    log_event("grok_json_fallback", reason="could not parse JSON after all strategies")
    return content


# ── Failure Detection ─────────────────────────────────────────────────────────

def grok_failed(analysis):
    """Detect if Grok returned garbage. Works for dict and string."""
    if isinstance(analysis, dict):
        # Blueprint mode has components, mechanic mode has diagnosis
        has_components = len(analysis.get("components", [])) > 0
        has_diagnosis = bool(analysis.get("diagnosis"))
        return not has_components and not has_diagnosis
    if isinstance(analysis, str):
        if len(analysis) < 50:
            return True
        markers = ["offline", "unavailable", "error", "timed out", "unexpected", "sorry"]
        return any(m in analysis.lower() for m in markers)
    return True


# ── Core Runner ───────────────────────────────────────────────────────────────

async def run_grok_inner(junk_desc, project_type, detail_level,
                         conception_context, mode="blueprint"):
    request_id = str(uuid.uuid4())[:8]
    log_event("grok_call_start", request_id=request_id, mode=mode, detail=detail_level)

    if not GROK_KEY:
        return {"analysis": {"components": [], "feasibility_score": 0,
                "analysis_summary": "Grok offline."}, "tokens": 0}

    timeouts = {"Standard": 60.0, "Industrial": 90.0, "Experimental": 120.0}
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
            f"DESIGN ORIGINALITY RULE: You MUST generate original, creative engineering designs. "
            f"NEVER copy, replicate, or closely imitate any existing commercial product.\n\n"
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
            f"WHAT I ACTUALLY HAVE:\n{truncate(junk_desc, 3000)}\n\n"
            f"Analyze every item. Return ONLY the JSON structure."
        )

    texts = _token_budget_check([system, user_msg],
                                max_toks.get(detail_level, 2000) * 2, "grok_input")

    try:
        async with httpx.AsyncClient(timeout=timeouts.get(detail_level, 40.0)) as client:
            resp = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROK_KEY}",
                         "Content-Type": "application/json"},
                json={
                    "model": GROK_MODEL,
                    "messages": [
                        {"role": "system", "content": texts[0]},
                        {"role": "user", "content": texts[1]},
                    ],
                    "max_tokens": max_toks.get(detail_level, 2000),
                    "temperature": GROK_TEMPERATURE,
                },
            )

        if resp.status_code == 200:
            d = resp.json()
            try:
                content = d["choices"][0]["message"]["content"]
            except (KeyError, IndexError):
                return {"analysis": "Grok returned unexpected format.", "tokens": 0}

            tokens = d.get("usage", {}).get("total_tokens", 0)
            analysis = safe_json_extract(content)

            log_event("grok_call_success", request_id=request_id,
                      tokens=tokens, parsed_as_dict=isinstance(analysis, dict))
            return {"analysis": analysis, "tokens": tokens}

        raise Exception(f"Grok HTTP {resp.status_code}")

    except httpx.TimeoutException:
        raise Exception(f"Grok timeout at {detail_level}")
    except Exception as e:
        log_event("grok_call_error", request_id=request_id, error=str(e)[:200])
        raise


# ── Public Entrypoint ─────────────────────────────────────────────────────────

async def run_grok(junk_desc, project_type, detail_level,
                   conception_context, mode="blueprint"):
    """Grok with retry wrapper."""
    try:
        return await retry_async(
            run_grok_inner, junk_desc, project_type, detail_level,
            conception_context, mode,
            max_attempts=2, base_delay=5.0, label="Grok"
        )
    except Exception as e:
        log.error("Grok failed after retries: %s", e)
        return {"analysis": f"Grok unavailable: {e}", "tokens": 0}


# ── Formatters ────────────────────────────────────────────────────────────────

def format_grok_for_claude(grok_analysis):
    """Convert Grok's structured JSON to readable text for Claude's prompt."""
    if isinstance(grok_analysis, str):
        return grok_analysis
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


def format_grok_for_mechanic(grok_analysis):
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
