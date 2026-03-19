"""Agent: Gemini 2.5 Flash — Web research + quality review."""
import json
import asyncio

from worker_config import (
    GEMINI_KEY, GEMINI_MODEL, GENAI_AVAILABLE,
    log, log_event, truncate, retry_async,
)

try:
    import google.generativeai as genai
except ImportError:
    pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_tokens(resp):
    """Safely extract total token usage from a Gemini response."""
    try:
        if hasattr(resp, "usage_metadata") and resp.usage_metadata:
            return resp.usage_metadata.total_token_count
    except Exception:
        pass
    return 0


def _parse_json_safely(text):
    """Parse JSON, stripping markdown fences if Gemini slips them in."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
    if text.endswith("```"):
        text = text.rsplit("\n", 1)[0]
    return json.loads(text.strip())


# ══════════════════════════════════════════════════════════════════════════════
# WEB RESEARCH (runs parallel with Grok)
# ══════════════════════════════════════════════════════════════════════════════

async def run_gemini_research(project_type, mode="blueprint"):
    """Gemini searches the web for real-world data relevant to the build/repair."""
    _empty = {"research": {}, "tokens": 0}
    if not GEMINI_KEY or not GENAI_AVAILABLE:
        return _empty

    model = genai.GenerativeModel(
        GEMINI_MODEL,
        system_instruction="You are an expert technical researcher. Always return strictly valid JSON.",
        generation_config={"response_mime_type": "application/json", "temperature": 0.2},
    )

    if mode in ("mechanic", "quote_check"):
        schema = {
            "forum_fixes": [{"source": "...", "url": "...", "summary": "what fixed it", "verified": True}],
            "tsbs": [{"number": "...", "title": "...", "summary": "...", "source_url": "..."}],
            "nhtsa_complaints": {"count": 0, "top_complaint": "...", "investigation_id": "..."},
            "recalls": [{"number": "...", "description": "...", "remedy": "..."}],
            "extended_warranties": [{"campaign": "...", "description": "...", "coverage": "..."}],
            "parts_pricing": [{"part": "...", "part_numbers": ["..."],
                              "prices": [{"source": "...", "price": "...", "url": "..."}]}],
            "youtube_videos": [{"title": "...", "url": "...", "duration": "..."}],
            "schematics": [{"description": "...", "source_url": "..."}],
            "research_summary": "2-paragraph summary",
        }
        prompt = (
            f"Search the web for real-world repair information about this problem.\n\n"
            f"PROJECT: {project_type}\n\n"
            f"Search for:\n"
            f"1. Forum threads from mechanics who fixed this exact problem "
            f"(iBoats, CumminsForum, TheDieselStop, FixYa, JustAnswer, etc.)\n"
            f"2. Technical Service Bulletins (TSBs) related to this symptom\n"
            f"3. NHTSA complaints and recalls for this vehicle/engine\n"
            f"4. Extended warranty or special service campaigns\n"
            f"5. Replacement parts with real pricing and part numbers "
            f"(RockAuto, Amazon, dealer sites, MarinePartsSource)\n"
            f"6. YouTube repair walkthrough videos for this specific repair\n"
            f"7. Wiring diagrams or schematics relevant to this repair\n\n"
            f"Return JSON strictly following this schema:\n"
            f"{json.dumps(schema, indent=2)}"
        )
    else:
        schema = {
            "similar_projects": [{"title": "...", "source": "Instructables", "url": "...", "key_insight": "..."}],
            "youtube_builds": [{"title": "...", "url": "...", "duration": "...", "relevance": "..."}],
            "gap_parts_pricing": [{"part": "...", "source": "Harbor Freight", "price": "...", "url": "..."}],
            "printable_parts": [{"part": "...", "source": "Thingiverse", "url": "..."}],
            "safety_notes": ["..."],
            "research_summary": "2-paragraph summary",
        }
        prompt = (
            f"Search the web for real-world maker projects and parts related to this build.\n\n"
            f"PROJECT: {project_type}\n\n"
            f"Search for:\n"
            f"1. Similar maker projects on Instructables, Hackaday, or maker blogs\n"
            f"2. YouTube build videos for similar projects\n"
            f"3. Gap-filler parts pricing from Harbor Freight, Amazon, eBay\n"
            f"4. 3D printable parts on Thingiverse that could help\n"
            f"5. Safety considerations specific to this type of build\n\n"
            f"Return JSON strictly following this schema:\n"
            f"{json.dumps(schema, indent=2)}"
        )

    async def _fetch(use_grounding):
        kwargs = {"tools": "google_search_retrieval"} if use_grounding else {}
        resp = await model.generate_content_async(prompt, **kwargs)
        return _parse_json_safely(resp.text), _get_tokens(resp)

    try:
        research, tokens = await _fetch(use_grounding=True)
        log_event("gemini_research_complete", mode=mode, keys=list(research.keys()))
        return {"research": research, "tokens": tokens}
    except json.JSONDecodeError:
        log_event("gemini_research_json_error", mode=mode)
        return _empty
    except Exception as e:
        log_event("gemini_research_failed", error=str(e)[:200])
        try:
            research, tokens = await _fetch(use_grounding=False)
            log_event("gemini_research_fallback_complete", mode=mode)
            return {"research": research, "tokens": tokens}
        except Exception as e2:
            log_event("gemini_research_fallback_failed", error=str(e2)[:200])
            return _empty


# ══════════════════════════════════════════════════════════════════════════════
# RESEARCH FORMATTER
# ══════════════════════════════════════════════════════════════════════════════

def format_research_for_claude(research, mode="blueprint"):
    """Convert Gemini's web research JSON into readable text for Claude."""
    if not research:
        return ""

    lines = ["WEB RESEARCH (from Gemini):"]

    if mode in ("mechanic", "quote_check"):
        for fix in (research.get("forum_fixes") or [])[:5]:
            lines.append(f"\nFORUM FIX ({fix.get('source', 'Unknown')}):")
            lines.append(f"  {fix.get('summary', 'N/A')}")
            if fix.get("url"):
                lines.append(f"  URL: {fix['url']}")

        for tsb in (research.get("tsbs") or [])[:3]:
            lines.append(f"\nTSB {tsb.get('number', 'Unknown')}: {tsb.get('title', 'N/A')}")
            lines.append(f"  {tsb.get('summary', 'N/A')}")

        nhtsa = research.get("nhtsa_complaints") or {}
        if nhtsa.get("count"):
            lines.append(f"\nNHTSA: {nhtsa['count']} complaints filed")
            lines.append(f"  Top complaint: {nhtsa.get('top_complaint', 'N/A')}")

        for recall in (research.get("recalls") or [])[:3]:
            lines.append(f"\nRECALL {recall.get('number', 'Unknown')}: {recall.get('description', 'N/A')}")
            lines.append(f"  Remedy: {recall.get('remedy', 'N/A')}")

        for ew in (research.get("extended_warranties") or [])[:2]:
            lines.append(f"\nEXTENDED WARRANTY: {ew.get('campaign', 'Unknown')}")
            lines.append(f"  {ew.get('description', 'N/A')}")

        for part in (research.get("parts_pricing") or [])[:5]:
            pns = part.get("part_numbers") or []
            lines.append(f"\nPART: {part.get('part', 'Unknown')} — PN: {', '.join(pns) or 'N/A'}")
            for p in (part.get("prices") or [])[:3]:
                lines.append(f"  {p.get('source', 'Unknown')}: {p.get('price', 'N/A')}")

        for vid in (research.get("youtube_videos") or [])[:3]:
            lines.append(f"\nVIDEO: {vid.get('title', 'Unknown')} ({vid.get('duration', 'N/A')})")
            lines.append(f"  {vid.get('url', 'N/A')}")

    else:
        for proj in (research.get("similar_projects") or [])[:3]:
            lines.append(f"\nSIMILAR PROJECT ({proj.get('source', 'Unknown')}): {proj.get('title', 'N/A')}")
            lines.append(f"  Insight: {proj.get('key_insight', 'N/A')}")
            if proj.get("url"):
                lines.append(f"  URL: {proj['url']}")

        for vid in (research.get("youtube_builds") or [])[:3]:
            lines.append(f"\nYOUTUBE: {vid.get('title', 'Unknown')} ({vid.get('duration', 'N/A')})")
            lines.append(f"  {vid.get('url', 'N/A')}")

        for part in (research.get("gap_parts_pricing") or [])[:5]:
            lines.append(f"\nPART: {part.get('part', 'Unknown')} — "
                         f"{part.get('source', 'Unknown')}: {part.get('price', 'N/A')}")

        for note in (research.get("safety_notes") or [])[:3]:
            lines.append(f"\nSAFETY: {note}")

    summary = research.get("research_summary")
    if summary:
        lines.append(f"\nRESEARCH SUMMARY:\n{summary}")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# QUALITY REVIEW
# ══════════════════════════════════════════════════════════════════════════════

GEMINI_OFFLINE = {
    "review_notes": "Gemini offline.", "inventory_usage_score": 0,
    "safety_flags": [], "innovations": [], "difficulty_rating": "Unknown",
    "estimated_build_time": "Unknown", "estimated_cost_usd": "Unknown",
    "tags": [], "conception_ready": False,
}


async def run_gemini_inner(blueprint, project_type, conception_context):
    if not GEMINI_KEY or not GENAI_AVAILABLE:
        return {"notes": GEMINI_OFFLINE, "tokens": 0}

    model = genai.GenerativeModel(
        GEMINI_MODEL,
        generation_config={"response_mime_type": "application/json", "temperature": 0.1},
    )

    schema = {
        "review_notes": "...",
        "inventory_usage_score": 85,
        "safety_flags": [],
        "innovations": [],
        "difficulty_rating": "Beginner|Intermediate|Advanced|Expert",
        "estimated_build_time": "...",
        "estimated_cost_usd": "...",
        "tags": [],
        "conception_ready": True,
    }

    prompt = (
        f"Review this engineering blueprint. Return JSON matching this exact structure:\n"
        f"{json.dumps(schema, indent=2)}\n\n"
    )
    if conception_context:
        prompt += f"CONTEXT: {conception_context}\n"
    prompt += f"BLUEPRINT:\n{truncate(blueprint, 3000)}\n\nPROJECT: {project_type}"

    resp = await model.generate_content_async(prompt)
    notes = _parse_json_safely(resp.text)
    return {"notes": notes, "tokens": _get_tokens(resp)}


async def run_gemini(blueprint, project_type, conception_context):
    """Gemini review with retry wrapper."""
    try:
        return await retry_async(
            run_gemini_inner, blueprint, project_type, conception_context,
            max_attempts=2, base_delay=4.0, label="Gemini"
        )
    except json.JSONDecodeError:
        log_event("gemini_json_error")
        return {"notes": {**GEMINI_OFFLINE, "review_notes": "Gemini returned invalid JSON."}, "tokens": 0}
    except Exception as e:
        log.error("Gemini failed: %s", e)
        return {"notes": {**GEMINI_OFFLINE, "review_notes": f"Gemini error: {e}"}, "tokens": 0}
