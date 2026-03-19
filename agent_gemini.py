"""Agent: Gemini 2.5 Flash — Web research + quality review."""
import json
import asyncio
from worker_config import (
    GEMINI_KEY, GEMINI_MODEL, GENAI_AVAILABLE, log, log_event,
)

try:
    import google.generativeai as genai
except ImportError:
    pass


async def run_gemini_research(project_type: str, mode: str = "blueprint") -> dict:
    """Gemini searches the web for real-world data relevant to the build/repair."""
    _empty = {"research": {}, "tokens": 0}
    if not GEMINI_KEY or not GENAI_AVAILABLE:
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
        log_event("gemini_research_complete", mode=mode, keys=list(research.keys()))
        return {"research": research, "tokens": 0}
    except json.JSONDecodeError:
        log_event("gemini_research_json_error", mode=mode)
        return _empty
    except Exception as e:
        log_event("gemini_research_failed", error=str(e)[:200])
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
            log_event("gemini_research_fallback_failed", error=str(e2)[:200])
            return _empty


def format_research_for_claude(research: dict, mode: str = "blueprint") -> str:
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

GEMINI_OFFLINE = {
    "review_notes": "Gemini offline.", "inventory_usage_score": 0,
    "safety_flags": [], "innovations": [], "difficulty_rating": "Unknown",
    "estimated_build_time": "Unknown", "estimated_cost_usd": "Unknown",
    "tags": [], "conception_ready": False,
}


async def run_gemini_inner(blueprint: str, project_type: str,
                             conception_context: str) -> dict:
    if not GEMINI_KEY or not GENAI_AVAILABLE:
        return {"notes": GEMINI_OFFLINE, "tokens": 0}

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


async def run_gemini(blueprint: str, project_type: str,
                      conception_context: str) -> dict:
    try:
        return await _retry_async(
            run_gemini_inner, blueprint, project_type, conception_context,
            max_attempts=2, base_delay=4.0, label="Gemini"
        )
    except json.JSONDecodeError:
        log_event("gemini_json_error")
        return {"notes": {**GEMINI_OFFLINE, "review_notes": "Gemini returned invalid JSON."}, "tokens": 0}
    except Exception as e:
        log.error("Gemini failed: %s", e)
        return {"notes": {**GEMINI_OFFLINE, "review_notes": f"Gemini error: {e}"}, "tokens": 0}
