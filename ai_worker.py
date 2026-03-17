"""
AI WORKER — CELERY TASK RUNNER
================================
Runs the 4-step forge pipeline:
  1. GROK-3    → Inventory analysis (junkyard genius)
  2. CLAUDE    → Engineering blueprint (inventory-first design)
  3. GEMINI    → Quality review and scoring
  4. CLAUDE    → Technical schematic (SVG illustration)

Conception memory hooks (recall + absorb) bookend the pipeline.

Features:
  - Inventory-first prompts: every part traces to a specific inventory item
  - Design originality: AI invents novel mechanisms, doesn't copy commercial products
  - Honesty layer: feasibility scores, [KNOWN]/[EST] tags, gap analysis
  - Budget shopping list: cheapest parts to fill gaps (Harbor Freight, NAPA, salvage)
  - Creative engineering: suggests unexpected uses for inventory components
  - Three detail levels: Standard (4K tokens), Industrial (6K), Experimental (8K)
  - Content safety: weapons/harmful builds blocked at ai_service gate (not here)
  - Real-time progress: Celery task.update_state() for live UI messages
  - SVG schematic: illustration-style drawing of the assembled project
"""

import os
import json
import logging
import asyncio
from typing import Optional

import httpx
import psycopg2.pool
from celery import Celery
from contextlib import contextmanager
from anthropic import Anthropic

# Gemini import — using deprecated package for now (google.genai migration planned)
try:
    import google.generativeai as genai
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False

# ── LOGGING ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ai_worker")

# ── CELERY + DB SETUP ─────────────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
celery_app = Celery("ai_worker", broker=REDIS_URL, backend=REDIS_URL)
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

pool = psycopg2.pool.ThreadedConnectionPool(2, 8, _db_url)


@contextmanager
def get_db():
    """Get a database connection from the pool. Auto-rollback on error."""
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

# Reusable Anthropic client (avoids creating a new one per call)
_anthropic_client: Optional[Anthropic] = None


def _get_anthropic() -> Anthropic:
    """Singleton Anthropic client."""
    global _anthropic_client
    if _anthropic_client is None and ANTHROPIC_KEY:
        _anthropic_client = Anthropic(api_key=ANTHROPIC_KEY)
    return _anthropic_client


def _h() -> dict:
    """Internal API auth header."""
    return {"x-internal-key": INT_KEY}


def _truncate(text: str, max_chars: int = 5000) -> str:
    """Safely truncate text at a sentence boundary."""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    # Try to cut at last sentence ending
    for sep in [". ", ".\n", "\n\n", "\n"]:
        idx = cut.rfind(sep)
        if idx > max_chars * 0.7:
            return cut[:idx + 1]
    return cut


# ══════════════════════════════════════════════════════════════════════════════
# CONCEPTION MEMORY HOOKS
# ══════════════════════════════════════════════════════════════════════════════

async def _recall_conception_memory(user_email: str,
                                    junk_desc: str,
                                    project_type: str) -> str:
    """
    Pull Conception's accumulated memory before running AI agents.
    Returns context string for agent prompts. Non-critical — returns "" on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                f"{CONCEPTION_URL}/conception/recall",
                json={
                    "user_email":   user_email,
                    "context":      f"{project_type}: {junk_desc[:500]}",
                    "inventory":    junk_desc[:500],
                    "project_type": project_type,
                },
                headers=_h(),
            )
        if resp.status_code == 200:
            data = resp.json()
            ctx = data.get("context_string") or data.get("context", "")
            if ctx:
                log.info("Conception recalled %d chars for %s", len(ctx), user_email)
            return ctx
    except Exception as e:
        log.warning("Conception recall skipped: %s", e)
    return ""


async def _absorb_into_conception(user_email: str,
                                   junk_desc: str,
                                   project_type: str,
                                   blueprint: str,
                                   grok_notes: str,
                                   claude_notes: str,
                                   build_id: int,
                                   tokens_used: int) -> None:
    """
    Feed finished blueprint into Conception for deep learning.
    Awaited directly with own timeout. Non-critical — won't crash the task.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{CONCEPTION_URL}/conception/absorb",
                json={
                    "build_id":     build_id,
                    "user_email":   user_email,
                    "junk_desc":    junk_desc[:2000],
                    "project_type": project_type,
                    "blueprint":    blueprint[:5000],
                    "grok_notes":   grok_notes[:2000],
                    "claude_notes": claude_notes[:1000],
                    "tokens_used":  tokens_used,
                },
                headers=_h(),
            )
        if resp.status_code == 200:
            data = resp.json()
            log.info(
                "Conception absorbed build %d — domain: %s | patterns: %d",
                build_id,
                data.get("domain", "?"),
                data.get("patterns_extracted", 0),
            )
        else:
            log.warning("Conception absorb HTTP %d for build %d",
                        resp.status_code, build_id)
    except Exception as e:
        log.warning("Conception absorb failed: %s", e)


# ══════════════════════════════════════════════════════════════════════════════
# AGENT 1: GROK-3 — JUNKYARD ANALYST
# ══════════════════════════════════════════════════════════════════════════════

async def _run_grok(junk_desc: str,
                    project_type: str,
                    detail_level: str,
                    conception_context: str) -> dict:
    """Analyze inventory items for harvestable components."""
    if not GROK_KEY:
        log.warning("GROK_API_KEY not set — Grok offline.")
        return {"analysis": "Grok offline — no API key configured.", "tokens": 0}

    # Detail-level scaling
    timeouts  = {"Standard": 40.0, "Industrial": 60.0, "Experimental": 80.0}
    max_toks  = {"Standard": 1500, "Industrial": 2500, "Experimental": 3500}
    detail_instructions = {
        "Standard": "Identify major harvestable components from each item.",
        "Industrial": (
            "For each component: specify exact voltages, current ratings, "
            "torque values, dimensions, weight, and material grade where possible. "
            "Calculate mechanical advantage of any gear/belt systems. "
            "Identify wire gauges and connector types."
        ),
        "Experimental": (
            "Maximum analysis depth. For each component: exact electrical specs "
            "(voltage, current, impedance), mechanical specs (torque, RPM, gear ratio, "
            "material tensile strength), thermal specs (max operating temp, thermal "
            "conductivity of housings), and dimensional specs (shaft diameter, bearing "
            "bore, frame wall thickness). Identify hidden value — capacitors, rare earth "
            "magnets in motors, precision machined surfaces, high-quality bearings, "
            "specialized alloys. Estimate component remaining life span based on age "
            "and typical duty cycles."
        ),
    }

    system = (
        f"You are GROK-3, a junkyard engineering genius on AoC3P0 Builder Foundry.\n\n"
        f"CRITICAL DISTINCTION:\n"
        f"- PROJECT GOAL = the thing the user wants to BUILD. They do NOT have this yet.\n"
        f"- INVENTORY = the physical items the user ALREADY OWNS. Analyze THESE.\n"
        f"- NEVER treat the project goal as an inventory item.\n\n"
        f"ABSOLUTE RULE: The user is building ONLY from the inventory they listed below. "
        f"They are NOT buying new parts. Your job is to analyze EACH SPECIFIC ITEM in "
        f"their inventory and explain exactly how it can be repurposed to build the project goal.\n\n"
        f"For EVERY item in the inventory:\n"
        f"1. Identify what useful components it contains (motors, frames, wiring, sensors, etc.)\n"
        f"2. Explain the engineering properties of those components\n"
        f"3. Describe exactly how each component maps to the project goal\n"
        f"4. Flag any items that genuinely cannot be used and explain why\n\n"
        f"HONESTY REQUIREMENTS:\n"
        f"- When you list specs (voltage, torque, dimensions), clearly mark whether each "
        f"value is KNOWN (from the product model/specs) or ESTIMATED (your best guess for "
        f"this type of equipment). Use [KNOWN] or [EST] tags.\n"
        f"- At the END of your analysis, include a FEASIBILITY ASSESSMENT section:\n"
        f"  - FEASIBILITY SCORE: 0-100 (can this project realistically be built from this inventory?)\n"
        f"  - CRITICAL GAPS: List anything essential for the project that the inventory CANNOT provide\n"
        f"  - HONEST LIMITATIONS: What will this build NOT be able to do, even if assembled perfectly?\n"
        f"  - ADDITIONAL ITEMS NEEDED: If the project genuinely requires things not in the inventory, say so\n"
        f"- If the project is fundamentally impossible with this inventory, SAY SO clearly. "
        f"Do not invent capabilities that don't exist. It's better to say 'this inventory "
        f"cannot build X because Y is missing' than to produce a fantasy blueprint.\n\n"
        f"Think like a resourceful engineer who builds from what's available — not a "
        f"catalog shopper. If someone lists a treadmill, you see a DC motor, a steel frame, "
        f"a belt drive, an incline actuator, a control board, and wiring. If they list a "
        f"computer, you see fans, power supply, heat sinks, a processing brain, and a metal chassis.\n\n"
        f"CREATIVE ENGINEERING:\n"
        f"Don't just list what components can be harvested — suggest UNEXPECTED uses. "
        f"Think about what makes each item's components UNIQUE and how those unique "
        f"properties could solve the project in a way nobody has tried before.\n"
        f"- A treadmill belt is not just a belt — it's a flat, wide, flexible surface "
        f"that could be a conveyor, a sifting screen, a track, a vibration dampener, or a seal.\n"
        f"- A computer's PSU is not just power — it's a precision multi-voltage source "
        f"that could drive sensors, logic, and low-power actuators independently.\n"
        f"- A mower's blade motor isn't just rotation — it's high-torque, weatherproof, "
        f"and designed for impacts, making it ideal for harsh-environment actuation.\n"
        f"- At the END of your component analysis, include a 'CREATIVE POSSIBILITIES' "
        f"section suggesting 2-3 novel mechanical approaches that the inventory uniquely enables. "
        f"These should NOT be copies of commercial products — they should be designs you'd "
        f"ONLY arrive at because of these specific parts.\n\n"
        f"Detail level: {detail_level}.\n"
        f"{detail_instructions.get(detail_level, '')}\n"
        + (f"\nCONCEPTION BRIEF:\n{conception_context}" if conception_context else "")
    )

    inventory_text = _truncate(junk_desc, 3000)

    try:
        async with httpx.AsyncClient(timeout=timeouts.get(detail_level, 40.0)) as client:
            resp = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROK_KEY}",
                    "Content-Type":  "application/json",
                },
                json={
                    "model": "grok-3",
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": (
                            f"WHAT I WANT TO BUILD (this is my goal — I do NOT already have this):\n"
                            f"{project_type}\n\n"
                            f"WHAT I ACTUALLY HAVE (these are the physical items I own — build from THESE):\n"
                            f"{inventory_text}\n\n"
                            f"IMPORTANT: The project goal above is what I want to CREATE. "
                            f"The inventory is what I have to BUILD IT FROM. "
                            f"Do NOT treat the project goal as an inventory item.\n\n"
                            f"Break down every item in my inventory and tell me exactly "
                            f"what useful parts I can harvest from each one to build the project goal."
                        )},
                    ],
                    "max_tokens":  max_toks.get(detail_level, 1500),
                    "temperature": 0.3,
                },
            )

        if resp.status_code == 200:
            d = resp.json()
            try:
                content = d["choices"][0]["message"]["content"]
            except (KeyError, IndexError):
                log.error("Grok response missing expected fields: %s", str(d)[:200])
                content = "Grok returned an unexpected response format."
            return {
                "analysis": content,
                "tokens":   d.get("usage", {}).get("total_tokens", 0),
            }

        log.error("Grok returned HTTP %d: %s", resp.status_code, resp.text[:200])
        return {"analysis": f"Grok error {resp.status_code}", "tokens": 0}

    except httpx.TimeoutException:
        log.error("Grok timed out at %s depth", detail_level)
        return {"analysis": "Grok timed out — try Standard depth.", "tokens": 0}
    except Exception as e:
        log.error("Grok failed: %s", e)
        return {"analysis": f"Grok unavailable: {e}", "tokens": 0}


# ══════════════════════════════════════════════════════════════════════════════
# AGENT 2: CLAUDE SONNET — BLUEPRINT ENGINEER
# ══════════════════════════════════════════════════════════════════════════════

async def _run_claude(junk_desc: str,
                      project_type: str,
                      grok_analysis: str,
                      detail_level: str,
                      conception_context: str) -> dict:
    """Generate full engineering blueprint from Grok's inventory analysis."""
    if not ANTHROPIC_KEY:
        log.warning("ANTHROPIC_API_KEY not set — Claude offline.")
        return {"blueprint": "Claude offline — no API key configured.", "tokens": 0}

    detail_map = {
        "Standard": (
            "Complete blueprint with 10 sections: overview, materials manifest, "
            "tools, assembly sequence, technical specs, safety, testing, modifications, "
            "honest assessment, and budget gap-filler list. "
            "Include specific measurements and dimensions for all structural components."
        ),
        "Industrial": (
            "Industrial-grade engineering document. All 10 standard sections PLUS:\n"
            "- POWER BUDGET: Calculate total wattage for every motor, controller, "
            "and sensor. Show voltage/current per rail.\n"
            "- TORQUE CALCULATIONS: For every joint or driven mechanism, calculate "
            "required torque (load x distance) and verify the harvested motor can deliver it.\n"
            "- WEIGHT DISTRIBUTION: Estimate weight of each major subassembly and "
            "verify the frame can support it. Show center of gravity.\n"
            "- WIRING DIAGRAM: Describe every electrical connection — which wire "
            "goes from which component to which pin/terminal. Include wire gauge.\n"
            "- BILL OF MATERIALS TABLE: Every single part with: name, source "
            "(which inventory item), quantity, weight, and function.\n"
            "- TOLERANCES: Specify fit tolerances for all critical joints (e.g. "
            "bearing fits, shaft clearances, alignment requirements).\n"
            "Be extremely specific. Use exact numbers, not ranges."
        ),
        "Experimental": (
            "Maximum-depth research-grade engineering document. Everything in "
            "Industrial PLUS:\n"
            "- FAILURE MODE ANALYSIS: For each critical component, describe what "
            "happens if it fails, how to detect the failure, and the backup plan.\n"
            "- THERMAL ANALYSIS: Identify every heat source (motors, electronics, "
            "friction points) and calculate thermal dissipation requirements.\n"
            "- FATIGUE LIFE ESTIMATES: For structural members under cyclic load, "
            "estimate cycles to failure and recommend inspection intervals.\n"
            "- CONTROL SYSTEM ARCHITECTURE: Describe the software control loop — "
            "sensor inputs, processing logic, actuator outputs, timing constraints, "
            "and PID parameters where applicable.\n"
            "- ALTERNATIVE DESIGNS: For each major subsystem, describe one alternative "
            "approach using the same inventory and explain why you chose the primary design.\n"
            "- PERFORMANCE ENVELOPE: Define the operating limits — max speed, max load, "
            "max continuous runtime, environmental limits — with the physics behind each.\n"
            "- UPGRADE PATH: Describe what additional components (from future salvage) "
            "would unlock the next level of capability.\n"
            "This should read like a senior engineering thesis. Every claim backed by "
            "a calculation or a specification from the harvested components."
        ),
    }

    system = (
        "You are CLAUDE-SONNET, a senior robotics and mechanical engineer "
        "on AoC3P0 Builder Foundry.\n\n"
        "CRITICAL DISTINCTION:\n"
        "- PROJECT GOAL = the thing the user wants to BUILD. They do NOT have this yet.\n"
        "- INVENTORY = the physical items the user ALREADY OWNS. Build from THESE.\n"
        "- NEVER treat the project goal as an inventory item. NEVER harvest parts from it.\n\n"
        "DESIGN ORIGINALITY RULE:\n"
        "Do NOT look up how commercial versions of the project work and copy them. "
        "Instead, INVENT a novel mechanism based on what the inventory actually provides. "
        "Let the inventory DICTATE the design — not the other way around.\n"
        "- If the inventory has a conveyor belt, design a conveyor-based system — "
        "don't force it into a rotating drum just because that's how a commercial product works.\n"
        "- If the inventory has hydraulic cylinders, design a hydraulic solution — "
        "don't ignore them to copy an electric motor design you've seen before.\n"
        "- If the inventory has a riding mower, think about what a riding mower's "
        "unique components make possible — don't just strip it for generic motors.\n"
        "- Ask yourself: 'What design would I ONLY arrive at because I have THESE specific parts?' "
        "That's the design you should build.\n"
        "- Propose at least 2 different mechanical approaches in the Project Overview, "
        "explain why you chose the primary one based on the inventory's strengths, "
        "and note the alternative in Optional Modifications.\n\n"
        "ABSOLUTE RULE: The Materials Manifest section must be built ENTIRELY from "
        "components harvested from the user's inventory items. Do NOT list generic parts "
        "to buy. Instead, for each material needed, specify which inventory item it "
        "comes from. Example: 'Drive Motor: Harvested from treadmill (2.5HP DC motor, "
        "model X)' or 'Structural Frame: Repurposed from treadmill steel base.'\n\n"
        "The ONLY exception is basic consumables (fasteners, wires, adhesives, lubricant) "
        "which you may list separately under 'Additional Consumables Needed.'\n\n"
        "HONESTY REQUIREMENTS:\n"
        "- When Grok's analysis tags specs as [EST] (estimated), carry that uncertainty "
        "forward. Say 'approximately' or 'estimated' — do NOT present guesses as facts.\n"
        "- Include a section called 'HONEST ASSESSMENT & GAPS' near the end that covers:\n"
        "  * What this build CAN realistically achieve with this inventory\n"
        "  * What this build CANNOT achieve (be specific about limitations)\n"
        "  * MISSING COMPONENTS: Things the project genuinely needs that aren't in the inventory\n"
        "  * FEASIBILITY RATING: Percentage chance this build works as described\n"
        "- If the inventory is genuinely insufficient for the project, say so in the "
        "Project Overview. Still provide the best possible blueprint, but be clear about "
        "what's missing and what the user would need to find/buy to complete it.\n"
        "- Never claim DARPA-quality, military-grade, or professional-grade performance "
        "unless the components can actually deliver it. Be ambitious but honest.\n\n"
        "- Include a section called 'BUDGET GAP-FILLER SHOPPING LIST' after the gaps section:\n"
        "  * For each missing component, suggest the CHEAPEST specific part that fills the gap\n"
        "  * Suggest parts from common stores: Home Depot, Harbor Freight, NAPA Auto Parts, "
        "Amazon, Walmart, or local auto salvage yards\n"
        "  * Format each item as: Part Name | Store | Approx Price | Why It Works\n"
        "  * Prioritize junkyard/salvage options first (cheapest), then budget retail\n"
        "  * Include a TOTAL ESTIMATED COST to fill all gaps\n"
        "  * If the gap can be filled by finding more free junk (e.g. 'any old printer "
        "has stepper motors'), suggest that FIRST before a store purchase\n"
        "  * Always suggest the budget option — Harbor Freight over Snap-On, used over new\n\n"
        "Using GROK-3's structural analysis of the inventory, produce a complete "
        "engineering blueprint with these sections:\n"
        "1-Project Overview (must explain the creative repurposing strategy),\n"
        "2-Materials Manifest (ONLY from inventory — say where each part comes from),\n"
        "3-Tools Required,\n"
        "4-Assembly Sequence (include disassembly/harvesting steps first),\n"
        "5-Technical Specifications,\n"
        "6-Safety Notes,\n"
        "7-Testing Procedure,\n"
        "8-Optional Modifications,\n"
        "9-HONEST ASSESSMENT & GAPS (required — see honesty requirements above),\n"
        "10-BUDGET GAP-FILLER SHOPPING LIST (required — see above).\n\n"
        + detail_map.get(detail_level, detail_map["Standard"])
        + (f"\nCONCEPTION BRIEF:\n{conception_context}" if conception_context else "")
    )

    token_limit = {"Standard": 4000, "Industrial": 6000, "Experimental": 8000}
    max_out = token_limit.get(detail_level, 4000)
    inventory_text = _truncate(junk_desc, 3000)
    grok_text = _truncate(grok_analysis, 4000)

    try:
        client = _get_anthropic()
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_out,
            system=system,
            messages=[{
                "role": "user",
                "content": (
                    f"GROK-3 ANALYSIS OF MY INVENTORY:\n{grok_text}\n\n"
                    f"WHAT I WANT TO BUILD (this is my goal — I do NOT own this yet):\n"
                    f"{project_type}\n\n"
                    f"WHAT I ACTUALLY HAVE (build from ONLY these items):\n"
                    f"{inventory_text}\n\n"
                    f"IMPORTANT: '{project_type}' is the thing I want to CREATE. "
                    f"It is NOT in my inventory. Do NOT harvest parts from it. "
                    f"The inventory items listed above are the ONLY source of parts.\n\n"
                    f"Generate a complete blueprint for building '{project_type}' using "
                    f"ONLY parts harvested from the inventory items listed above. "
                    f"Every item in the Materials Manifest must reference which inventory "
                    f"item it was harvested from."
                ),
            }],
        )
        return {
            "blueprint": resp.content[0].text,
            "tokens":    resp.usage.input_tokens + resp.usage.output_tokens,
        }
    except Exception as e:
        log.error("Claude blueprint failed: %s", e)
        return {"blueprint": f"Claude unavailable: {e}", "tokens": 0}


# ══════════════════════════════════════════════════════════════════════════════
# AGENT 3: GEMINI FLASH — QUALITY INSPECTOR
# ══════════════════════════════════════════════════════════════════════════════

async def _run_gemini(blueprint: str,
                      project_type: str,
                      conception_context: str) -> dict:
    """Review blueprint for quality, safety, and inventory usage."""
    _offline = {
        "review_notes":         "Gemini offline.",
        "inventory_usage_score": 0,
        "safety_flags":         [],
        "innovations":          [],
        "difficulty_rating":    "Unknown",
        "estimated_build_time": "Unknown",
        "estimated_cost_usd":   "Unknown",
        "tags":                 [],
        "conception_ready":     False,
    }

    if not GEMINI_KEY or not _GENAI_AVAILABLE:
        log.warning("Gemini offline (key=%s, lib=%s).", bool(GEMINI_KEY), _GENAI_AVAILABLE)
        return {"notes": _offline, "tokens": 0}

    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        generation_config={"response_mime_type": "application/json"},
    )

    prompt = (
        "Review this engineering blueprint. The blueprint MUST use parts harvested from "
        "the user's actual inventory — not generic store-bought materials. Check whether "
        "the blueprint actually references the inventory items. Return JSON only — "
        "no markdown, no preamble:\n"
        "{\n"
        '  "review_notes": "2-3 paragraph quality review — specifically note whether '
        'the blueprint creatively uses the actual inventory or just lists generic parts",\n'
        '  "inventory_usage_score": "0-100 — what percentage of inventory items were '
        'actually used in the blueprint",\n'
        '  "safety_flags": ["list safety issues"],\n'
        '  "innovations": ["2-3 creative ways to better use the inventory items"],\n'
        '  "difficulty_rating": "Beginner|Intermediate|Advanced|Expert",\n'
        '  "estimated_build_time": "e.g. 4-6 hours",\n'
        '  "estimated_cost_usd": "e.g. $15-$40 for consumables only since parts come '
        'from inventory",\n'
        '  "tags": ["engineering domain tags"],\n'
        '  "conception_ready": true or false\n'
        "}\n"
        + (f"CONCEPTION CONTEXT: {conception_context}\n" if conception_context else "")
        + f"BLUEPRINT:\n{_truncate(blueprint, 3000)}\n"
        + f"PROJECT: {project_type}"
    )

    try:
        resp = await model.generate_content_async(prompt)
        notes = json.loads(resp.text)
        return {"notes": notes, "tokens": 0}
    except json.JSONDecodeError as e:
        log.error("Gemini returned invalid JSON: %s", e)
        return {"notes": {**_offline, "review_notes": "Gemini returned invalid JSON."}, "tokens": 0}
    except Exception as e:
        log.error("Gemini failed: %s", e)
        return {"notes": {**_offline, "review_notes": f"Gemini error: {e}"}, "tokens": 0}


# ══════════════════════════════════════════════════════════════════════════════
# AGENT 4: CLAUDE — TECHNICAL SCHEMATIC (SVG)
# ══════════════════════════════════════════════════════════════════════════════

async def _generate_schematic(blueprint: str,
                               project_type: str,
                               junk_desc: str) -> str:
    """Generate SVG technical illustration of the assembled project."""
    if not ANTHROPIC_KEY:
        log.warning("Schematic skipped — no Anthropic key.")
        return ""

    system = (
        "You are a technical illustrator who draws simplified side-view technical "
        "drawings of engineering projects. Return ONLY valid SVG code.\n\n"
        "ABSOLUTE RULES:\n"
        "1. Output starts with <svg and ends with </svg>. NOTHING else.\n"
        "2. No markdown, no ```svg, no explanation text before or after.\n"
        "3. Allowed SVG elements: <svg>, <rect>, <text>, <line>, <g>, <circle>, "
        "<ellipse>, <polygon>, <path>. No <foreignObject>, no <image>, no <style>, "
        "no <script>, no <clipPath>, no <defs>, no <filter>.\n"
        "4. All styling via inline attributes (fill=, stroke=, font-size=, etc).\n"
        "5. font-family='Arial, sans-serif' on all text.\n"
        "6. viewBox='0 0 800 550'. White background rect first.\n\n"
        "DRAWING STYLE — TECHNICAL ILLUSTRATION:\n"
        "Draw the project as it would ACTUALLY LOOK when assembled, using a "
        "simplified side-view or 3/4 view. Use basic geometric shapes to represent "
        "the real form:\n"
        "- A ROBOT: Draw a recognizable humanoid silhouette — rectangular torso, "
        "cylindrical/rectangular legs with joints, circular joints at hips/knees, "
        "rectangular feet. It should look like a robot.\n"
        "- A VEHICLE: Draw the vehicle shape — chassis, wheels, cab, etc.\n"
        "- A MACHINE: Draw the machine shape — housing, drum, conveyor, etc.\n"
        "- ANY PROJECT: Draw what it actually looks like, simplified.\n\n"
        "The shapes should be recognizable as the thing being built. NOT just "
        "a block diagram of labeled rectangles.\n\n"
        "LABELING:\n"
        "- Use thin leader lines (stroke='#94A3B8' stroke-width='0.5') from "
        "components to labels positioned to the LEFT or RIGHT of the drawing.\n"
        "- Each label: bold 10px component name + 8px source in #64748B below it.\n"
        "- Keep labels outside the drawing, connected by leader lines.\n\n"
        "COLOR FILLS:\n"
        "- Structure/frame: fill='#2563EB' opacity='0.2' stroke='#2563EB'\n"
        "- Motors/actuators: fill='#DC2626' opacity='0.2' stroke='#DC2626'\n"
        "- Electronics: fill='#16A34A' opacity='0.2' stroke='#16A34A'\n"
        "- Sensors: fill='#9333EA' opacity='0.2' stroke='#9333EA'\n"
        "- Belts/mechanical: fill='#D97706' opacity='0.2' stroke='#D97706'\n"
        "- Joints/pivots: fill='#475569' stroke='#1E293B' (dark circles)\n\n"
        "LAYOUT:\n"
        "- Center the drawing in the canvas (main object roughly x=200-600)\n"
        "- Labels on left side (x=20-180) and right side (x=620-790)\n"
        "- Title: 14px bold top-left with project name\n"
        "- 2-3 dimension lines with arrows showing overall height and width\n"
        "- Small color legend in bottom-right corner (5 small squares with text)\n"
        "- Faint grid behind everything: lines every 40px, stroke='#F1F5F9'\n\n"
        "Keep path d= attributes simple — straight lines and basic curves only. "
        "No complex bezier art. Think engineering drawing, not illustration."
    )

    blueprint_excerpt = _truncate(blueprint, 2000)

    try:
        client = _get_anthropic()
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            system=system,
            messages=[{
                "role": "user",
                "content": (
                    f"Draw a technical illustration of: {project_type}\n\n"
                    f"It is built from these inventory items:\n{_truncate(junk_desc, 500)}\n\n"
                    f"Here is the blueprint describing the assembly:\n{blueprint_excerpt}\n\n"
                    f"Draw what the finished {project_type} looks like from the side, "
                    f"with each major component colored by type and labeled with "
                    f"leader lines showing what it is and which inventory item it came from.\n\n"
                    f"Output ONLY the <svg>...</svg> code. Nothing else."
                ),
            }],
        )
        svg = resp.content[0].text.strip()

        # Extract only the SVG tags
        svg_start = svg.find("<svg")
        svg_end = svg.rfind("</svg>")
        if svg_start == -1 or svg_end == -1:
            log.warning("Schematic: no valid SVG tags found in %d char response.", len(svg))
            return ""
        svg = svg[svg_start:svg_end + 6]

        # Clean stray markdown
        svg = svg.replace("```", "").replace("`", "")

        # Reject broken SVGs (usually way too large)
        if len(svg) > 20000:
            log.warning("Schematic SVG too large (%d chars), likely broken.", len(svg))
            return ""

        log.info("Schematic SVG generated: %d chars", len(svg))
        return svg

    except Exception as e:
        log.error("Schematic generation failed: %s", e)
        return ""


# ══════════════════════════════════════════════════════════════════════════════
# FORGE PIPELINE — ORCHESTRATES ALL 4 AGENTS
# ══════════════════════════════════════════════════════════════════════════════

async def _forge_pipeline(user_email: str,
                           junk_desc: str,
                           project_type: str,
                           detail_level: str,
                           task=None) -> dict:
    """Run the complete forge pipeline with progress updates."""

    def _update(msg: str):
        """Push real-time progress message to the Celery result backend."""
        if task:
            task.update_state(state="PROGRESS", meta={"message": msg})

    # 0 — Recall Conception memory
    _update("🔍 Scanning Conception memory banks...")
    ctx = await _recall_conception_memory(user_email, junk_desc, project_type)

    # 1 — Grok: inventory analysis
    _update("🔧 GROK-3 disassembling inventory... identifying harvestable components")
    log.info("Agent 1: Grok structural analysis")
    grok_r   = await _run_grok(junk_desc, project_type, detail_level, ctx)
    grok_out = grok_r["analysis"]

    # 2 — Claude: engineering blueprint
    _update("📐 CLAUDE mapping component pathways... drafting engineering blueprint")
    log.info("Agent 2: Claude blueprint")
    claude_r  = await _run_claude(junk_desc, project_type, grok_out, detail_level, ctx)
    blueprint = claude_r["blueprint"]

    # 3 — Gemini: quality review
    _update("🔬 GEMINI inspecting blueprint... checking safety and inventory usage")
    log.info("Agent 3: Gemini review")
    gemini_r = await _run_gemini(blueprint, project_type, ctx)
    notes    = gemini_r["notes"] if isinstance(gemini_r["notes"], dict) else {}

    # 4 — Schematic: technical drawing
    _update("✏️ Plotting technical schematic... rendering component layout")
    log.info("Agent 4: Schematic generation")
    schematic_svg = await _generate_schematic(blueprint, project_type, junk_desc)

    total_tokens = grok_r["tokens"] + claude_r["tokens"]

    # 5 — Save to database
    _update("💾 Archiving blueprint to Conception DNA Vault...")
    build_id = None
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO builds
                        (user_email, junk_desc, project_type, blueprint,
                         grok_notes, claude_notes, tokens_used, conception_ready)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        user_email, junk_desc[:5000], project_type, blueprint,
                        grok_out[:5000],
                        notes.get("review_notes", "")[:2000],
                        total_tokens,
                        notes.get("conception_ready", False),
                    ),
                )
                build_id = cur.fetchone()[0]
                conn.commit()
        log.info("Build %d saved to database.", build_id)
    except Exception as e:
        log.error("DB save failed: %s", e)

    # 6 — Feed to Conception for deep learning
    if build_id:
        await _absorb_into_conception(
            user_email   = user_email,
            junk_desc    = junk_desc,
            project_type = project_type,
            blueprint    = blueprint,
            grok_notes   = grok_out,
            claude_notes = notes.get("review_notes", ""),
            build_id     = build_id,
            tokens_used  = total_tokens,
        )

    return {
        "status":                  "complete",
        "build_id":                build_id,
        "user_email":              user_email,
        "project_type":            project_type,
        "detail_level":            detail_level,
        "content":                 blueprint,
        "schematic_svg":           schematic_svg,
        "grok_analysis":           grok_out,
        "review_notes":            notes.get("review_notes", ""),
        "safety_flags":            notes.get("safety_flags", []),
        "innovations":             notes.get("innovations", []),
        "difficulty":              notes.get("difficulty_rating", "Unknown"),
        "build_time":              notes.get("estimated_build_time", "Unknown"),
        "cost_estimate":           notes.get("estimated_cost_usd", "Unknown"),
        "tags":                    notes.get("tags", []),
        "conception_ready":        notes.get("conception_ready", False),
        "tokens_used":             total_tokens,
        "agents_used":             ["GROK-3", "CLAUDE-SONNET", "GEMINI-2.5-FLASH"],
        "conception_context_used": bool(ctx),
    }


# ══════════════════════════════════════════════════════════════════════════════
# CELERY TASK — ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

@celery_app.task(
    bind=True,
    name="ai_worker.forge_blueprint_task",
    max_retries=2,
    soft_time_limit=300,
    time_limit=330,
)
def forge_blueprint_task(self,
                          user_email: str,
                          junk_desc: str,
                          project_type: str,
                          detail_level: str = "Standard"):
    """
    Celery entry point. Creates a fresh event loop and runs the async pipeline.
    Retries up to 2 times with escalating backoff on failure.
    """
    log.info(
        "Forge started: user=%s project='%s' depth=%s",
        user_email, project_type[:50], detail_level
    )
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            _forge_pipeline(user_email, junk_desc, project_type, detail_level, task=self)
        )
    except Exception as e:
        log.error("Forge pipeline failed: %s", e)
        # Escalating retry: 10s, then 30s
        countdown = 10 if self.request.retries == 0 else 30
        raise self.retry(exc=e, countdown=countdown)
    finally:
        loop.close()
