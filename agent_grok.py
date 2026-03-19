"""Agent: Grok 4.2 — Structured JSON diagnostic/analysis."""
import json
import httpx
from prompts import mechanic_grok_system, quote_check_grok_system
from worker_config import (
    GROK_KEY, GROK_MODEL, log, log_event, truncate,
    estimate_tokens, retry_async,
)


def _token_budget_check(texts, max_tokens, label):
    total = sum(len(t)//4 for t in texts)
    if total <= max_tokens:
        return texts
    ratio = max_tokens / max(total, 1)
    return [truncate(t, int(len(t) * ratio * 0.9)) for t in texts]


def grok_failed(analysis) -> bool:
    """Detect if Grok returned garbage. Works for both JSON dict and string."""
    if isinstance(analysis, dict):
        return len(analysis.get("components", [])) == 0
    if isinstance(analysis, str):
        if len(analysis) < 50:
            return True
        markers = ["offline", "unavailable", "error", "timed out", "unexpected"]
        return any(m in analysis.lower() for m in markers)
    return True



async def run_grok_inner(junk_desc: str, project_type: str,
                          detail_level: str, conception_context: str,
                          mode: str = "blueprint") -> dict:
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
            f"WHAT I ACTUALLY HAVE:\n{truncate(junk_desc, 3000)}\n\n"
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
                log_event("grok_json_fallback", reason="invalid JSON from Grok")
                return {"analysis": content, "tokens": tokens}

        # Any non-200 raises so the retry wrapper can handle it
        raise Exception(f"Grok API returned HTTP {resp.status_code}")

    except httpx.TimeoutException:
        raise Exception(f"Grok timeout at {detail_level}")


async def run_grok(junk_desc: str, project_type: str,
                    detail_level: str, conception_context: str,
                    mode: str = "blueprint") -> dict:
    """Grok with retry wrapper."""
    try:
        return await retry_async(
            run_grok_inner, junk_desc, project_type, detail_level, conception_context, mode,
            max_attempts=2, base_delay=5.0, label="Grok"
        )
    except Exception as e:
        log.error("Grok failed after retries: %s", e)
        return {"analysis": f"Grok unavailable: {e}", "tokens": 0}

def format_grok_for_claude(grok_analysis) -> str:
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


def format_grok_for_mechanic(grok_analysis) -> str:
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
