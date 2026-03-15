"""
AI WORKER — CELERY TASK RUNNER
================================
Runs the 3-agent forge pipeline: GROK-3 → CLAUDE-SONNET → GEMINI-FLASH
Conception memory hooks (recall + absorb) are fully integrated.

Merged from: ai_worker.py + ai_worker_patch.py
Fixes applied:
  - asyncio.ensure_future() bug: was called inside _forge_pipeline() which runs
    inside loop.run_until_complete(). The future gets scheduled on the loop, but
    the loop closes the moment run_until_complete() returns — absorb NEVER ran.
    Fix: absorb is now awaited directly. It has its own 15s timeout and a full
    try/except, so it cannot block or crash the task.
  - Absorb payload updated to include `tokens_used` (was in patch, missing from
    original) so Conception can learn which builds were expensive.
  - Absorb response now logged with domain, patterns_extracted, and insight
    fields (from patch) for better observability.
  - Recall payload unified: both `context` and `inventory` keys sent so the
    Conception service handles either version of the endpoint.
  - Redundant `import httpx as _hx` inside async functions removed — httpx is
    imported once at the top and reused.
  - `run_in_executor` wrappers removed from httpx calls — httpx is async-native;
    wrapping it in an executor is unnecessary overhead.
"""

import os
import logging
import asyncio
import httpx
from celery import Celery
from contextlib import contextmanager
import psycopg2.pool
from anthropic import Anthropic

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ai_worker")

# ── CELERY + DB SETUP ──────────────────────────────────────────────────────────

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
    conn = pool.getconn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


# ── ENVIRONMENT ────────────────────────────────────────────────────────────────

CONCEPTION_URL = os.getenv("CONCEPTION_SERVICE_URL", "http://builder-conception:10000")
INT_KEY        = os.getenv("INTERNAL_API_KEY", "")
ANTHROPIC_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_KEY     = os.getenv("GEMINI_API_KEY", "")
GROK_KEY       = os.getenv("GROK_API_KEY", "")


def _h() -> dict:
    return {"x-internal-key": INT_KEY}


# ── CONCEPTION MEMORY HOOKS ────────────────────────────────────────────────────

async def _recall_conception_memory(user_email: str,
                                    junk_desc: str,
                                    project_type: str) -> str:
    """
    Pull Conception's accumulated memory before running the AI agents.
    Returns a context string to prepend to every agent's system prompt.
    If Conception is offline or empty → returns "" without crashing.

    Sends both `context` and `inventory` keys for compatibility with
    both v1 and v2 of the Conception memory endpoint.
    """
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                f"{CONCEPTION_URL}/conception/recall",
                json={
                    "user_email":   user_email,
                    "context":      f"{project_type}: {junk_desc}",  # v1 key
                    "inventory":    junk_desc,                        # v2 key
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
        log.warning("Conception recall skipped (non-critical): %s", e)
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
    Feed the finished blueprint into Conception for deep learning.
    Awaited directly — has its own 15s timeout + full try/except,
    so it cannot block or crash the forge task.

    FIX: was previously called via asyncio.ensure_future(), which schedules
    on the running loop. But the loop closes immediately after
    run_until_complete() returns in forge_blueprint_task() — the coroutine
    was being silently dropped and Conception never learned anything.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{CONCEPTION_URL}/conception/absorb",
                json={
                    "build_id":     build_id,
                    "user_email":   user_email,
                    "junk_desc":    junk_desc,
                    "project_type": project_type,
                    "blueprint":    blueprint,
                    "grok_notes":   grok_notes,
                    "claude_notes": claude_notes,
                    "tokens_used":  tokens_used,   # added from patch
                },
                headers=_h(),
            )
        if resp.status_code == 200:
            data = resp.json()
            log.info(
                "Conception absorbed build %d — domain: %s | patterns: %d | insight: %s",
                build_id,
                data.get("domain", "?"),
                data.get("patterns_extracted", 0),
                data.get("insight", ""),
            )
        else:
            log.warning("Conception absorb returned HTTP %d for build %d",
                        resp.status_code, build_id)
    except Exception as e:
        log.warning("Conception absorb failed (non-critical): %s", e)


# ── AI AGENTS ──────────────────────────────────────────────────────────────────

async def _run_grok(junk_desc: str,
                    project_type: str,
                    detail_level: str,
                    conception_context: str) -> dict:
    """GROK-3: structural engineering analysis."""
    if not GROK_KEY:
        log.warning("GROK_API_KEY not set — Grok offline.")
        return {"analysis": "Grok offline — no API key configured.", "tokens": 0}

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
        f"Think like a resourceful engineer who builds from what's available — not a "
        f"catalog shopper. If someone lists a treadmill, you see a DC motor, a steel frame, "
        f"a belt drive, an incline actuator, a control board, and wiring. If they list a "
        f"computer, you see fans, power supply, heat sinks, a processing brain, and a metal chassis.\n\n"
        f"Detail level: {detail_level}.\n"
        + ({
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
        }.get(detail_level, "") + "\n")
        + (f"\nCONCEPTION BRIEF:\n{conception_context}" if conception_context else "")
    )
    try:
        async with httpx.AsyncClient(timeout={"Standard": 40.0, "Industrial": 60.0, "Experimental": 80.0}.get(detail_level, 40.0)) as client:
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
                        {"role": "user",   "content":
                            f"WHAT I WANT TO BUILD (this is my goal — I do NOT already have this):\n{project_type}\n\n"
                            f"WHAT I ACTUALLY HAVE (these are the physical items I own — build from THESE):\n{junk_desc}\n\n"
                            f"IMPORTANT: The project goal above is what I want to CREATE. "
                            f"The inventory below is what I have to BUILD IT FROM. "
                            f"Do NOT treat the project goal as an inventory item.\n\n"
                            f"Break down every item in my inventory and tell me exactly "
                            f"what useful parts I can harvest from each one to build the project goal."},
                    ],
                    "max_tokens":  {"Standard": 1500, "Industrial": 2500, "Experimental": 3500}.get(detail_level, 1500),
                    "temperature": 0.3,
                },
            )
        if resp.status_code == 200:
            d = resp.json()
            return {
                "analysis": d["choices"][0]["message"]["content"],
                "tokens":   d.get("usage", {}).get("total_tokens", 0),
            }
        log.error("Grok returned HTTP %d", resp.status_code)
        return {"analysis": f"Grok error {resp.status_code}", "tokens": 0}
    except Exception as e:
        log.error("Grok failed: %s", e)
        return {"analysis": f"Grok unavailable: {e}", "tokens": 0}


async def _run_claude(junk_desc: str,
                      project_type: str,
                      grok_analysis: str,
                      detail_level: str,
                      conception_context: str) -> dict:
    """CLAUDE-SONNET: full engineering blueprint from Grok's analysis."""
    if not ANTHROPIC_KEY:
        log.warning("ANTHROPIC_API_KEY not set — Claude offline.")
        return {"blueprint": "Claude offline — no API key configured.", "tokens": 0}

    detail_map = {
        "Standard": (
            "Complete blueprint with 8 sections: overview, materials manifest, "
            "tools, assembly sequence, technical specs, safety, testing, modifications. "
            "Include specific measurements and dimensions for all structural components."
        ),
        "Industrial": (
            "Industrial-grade engineering document. All 8 standard sections PLUS:\n"
            "- POWER BUDGET: Calculate total wattage for every motor, controller, "
            "and sensor. Show voltage/current per rail.\n"
            "- TORQUE CALCULATIONS: For every joint or driven mechanism, calculate "
            "required torque (load × distance) and verify the harvested motor can deliver it.\n"
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
        "ABSOLUTE RULE: The Materials Manifest section must be built ENTIRELY from "
        "components harvested from the user's inventory items. Do NOT list generic parts "
        "to buy. Instead, for each material needed, specify which inventory item it "
        "comes from. Example: 'Drive Motor: Harvested from treadmill (2.5HP DC motor, "
        "model X)' or 'Structural Frame: Repurposed from treadmill steel base.'\n\n"
        "The ONLY exception is basic consumables (fasteners, wires, adhesives, lubricant) "
        "which you may list separately under 'Additional Consumables Needed.'\n\n"
        "Using GROK-3's structural analysis of the inventory, produce a complete "
        "engineering blueprint with these sections:\n"
        "1-Project Overview (must explain the creative repurposing strategy),\n"
        "2-Materials Manifest (ONLY from inventory — say where each part comes from),\n"
        "3-Tools Required,\n"
        "4-Assembly Sequence (include disassembly/harvesting steps first),\n"
        "5-Technical Specifications,\n"
        "6-Safety Notes,\n"
        "7-Testing Procedure,\n"
        "8-Optional Modifications.\n\n"
        + detail_map.get(detail_level, detail_map["Standard"])
        + (f"\nCONCEPTION BRIEF:\n{conception_context}" if conception_context else "")
    )
    # Scale output length to detail level
    token_limit = {"Standard": 4000, "Industrial": 6000, "Experimental": 8000}
    max_out = token_limit.get(detail_level, 4000)

    try:
        client = Anthropic(api_key=ANTHROPIC_KEY)
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_out,
            system=system,
            messages=[{
                "role":    "user",
                "content": (
                    f"GROK-3 ANALYSIS OF MY INVENTORY:\n{grok_analysis}\n\n"
                    f"WHAT I WANT TO BUILD (this is my goal — I do NOT own this yet):\n{project_type}\n\n"
                    f"WHAT I ACTUALLY HAVE (build from ONLY these items):\n{junk_desc}\n\n"
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
        log.error("Claude failed: %s", e)
        return {"blueprint": f"Claude unavailable: {e}", "tokens": 0}


async def _run_gemini(blueprint: str,
                      project_type: str,
                      conception_context: str) -> dict:
    """GEMINI-FLASH: quality review, safety flags, cost/time estimates."""
    _offline = {
        "review_notes":        "Gemini offline — no API key configured.",
        "safety_flags":        [],
        "innovations":         [],
        "difficulty_rating":   "Unknown",
        "estimated_build_time": "Unknown",
        "estimated_cost_usd":  "Unknown",
        "tags":                [],
        "conception_ready":    False,
    }
    if not GEMINI_KEY:
        log.warning("GEMINI_API_KEY not set — Gemini offline.")
        return {"notes": _offline, "tokens": 0}

    import google.generativeai as genai
    import json as _json

    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel(
        "gemini-2.0-flash",
        generation_config={"response_mime_type": "application/json"},
    )
    prompt = (
        "Review this engineering blueprint. The blueprint MUST use parts harvested from "
        "the user's actual inventory — not generic store-bought materials. Check whether "
        "the blueprint actually references the inventory items. Return JSON only — no markdown, no preamble:\n"
        "{\n"
        '  "review_notes": "2-3 paragraph quality review — specifically note whether the blueprint creatively uses the actual inventory or just lists generic parts",\n'
        '  "inventory_usage_score": "0-100 — what percentage of inventory items were actually used in the blueprint",\n'
        '  "safety_flags": ["list safety issues"],\n'
        '  "innovations": ["2-3 creative ways to better use the inventory items"],\n'
        '  "difficulty_rating": "Beginner|Intermediate|Advanced|Expert",\n'
        '  "estimated_build_time": "e.g. 4-6 hours",\n'
        '  "estimated_cost_usd": "e.g. $15-$40 for consumables only since parts come from inventory",\n'
        '  "tags": ["engineering domain tags"],\n'
        '  "conception_ready": true or false\n'
        "}\n"
        + (f"CONCEPTION CONTEXT: {conception_context}\n" if conception_context else "")
        + f"BLUEPRINT:\n{blueprint[:3000]}\n"
        + f"PROJECT: {project_type}"
    )
    try:
        resp = await model.generate_content_async(prompt)
        notes = _json.loads(resp.text)
        return {"notes": notes, "tokens": 0}
    except Exception as e:
        log.error("Gemini failed: %s", e)
        return {"notes": {**_offline, "review_notes": f"Gemini error: {e}"}, "tokens": 0}


# ── SCHEMATIC GENERATOR ───────────────────────────────────────────────────────

async def _generate_schematic(blueprint: str,
                               project_type: str,
                               junk_desc: str) -> str:
    """Generate an SVG technical schematic from the blueprint."""
    if not ANTHROPIC_KEY:
        log.warning("ANTHROPIC_API_KEY not set — schematic generation skipped.")
        return ""

    system = (
        "You are a technical illustrator. Generate a COMPLETE, VALID SVG technical "
        "schematic drawing. Return ONLY the raw SVG code — no markdown, no ```svg tags, "
        "no explanation. Just the SVG starting with <svg and ending with </svg>.\n\n"
        "DRAWING REQUIREMENTS:\n"
        "- Canvas: 800x600 pixels with a light grid background (10px spacing)\n"
        "- Title block in top-left with project name and scale\n"
        "- Main view: Top-down OR side-view schematic of the assembled project\n"
        "- Each major component drawn as a labeled rectangle or shape with:\n"
        "  - Component name inside or next to it\n"
        "  - Source label (which inventory item it came from) in smaller italic text\n"
        "  - Dimension lines with measurements where relevant\n"
        "- Use these colors:\n"
        "  - #2563EB (blue) for structural/frame components\n"
        "  - #DC2626 (red) for motors and actuators\n"
        "  - #16A34A (green) for electronics and control systems\n"
        "  - #9333EA (purple) for sensors\n"
        "  - #D97706 (amber) for belts, chains, and mechanical linkages\n"
        "  - #1E293B (dark) for text and dimension lines\n"
        "- Include a color-coded legend in the bottom-right corner\n"
        "- Use dashed lines to show connections between components\n"
        "- Add dimension arrows with approximate measurements\n"
        "- Professional engineering drawing style — clean lines, clear labels\n"
        "- All text must be readable (minimum 10px font size)\n"
    )

    try:
        client = Anthropic(api_key=ANTHROPIC_KEY)
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            system=system,
            messages=[{
                "role": "user",
                "content": (
                    f"Create an SVG technical schematic for this project.\n\n"
                    f"PROJECT: {project_type}\n\n"
                    f"INVENTORY ITEMS USED:\n{junk_desc}\n\n"
                    f"BLUEPRINT SUMMARY (focus on the Materials Manifest and "
                    f"Assembly Sequence sections):\n{blueprint[:2500]}\n\n"
                    f"Draw the assembled project showing where each harvested "
                    f"component goes. Label every part with its name and which "
                    f"inventory item it came from."
                ),
            }],
        )
        svg = resp.content[0].text.strip()
        # Clean up in case the AI wrapped it in markdown
        if "```" in svg:
            svg = svg.split("```")[1] if "```" in svg else svg
            if svg.startswith("svg"):
                svg = svg[3:]
            svg = svg.strip()
        # Validate it starts with <svg
        if not svg.startswith("<svg"):
            log.warning("Schematic generation returned non-SVG content.")
            return ""
        log.info("Schematic SVG generated: %d chars", len(svg))
        return svg
    except Exception as e:
        log.error("Schematic generation failed: %s", e)
        return ""


# ── FORGE PIPELINE ─────────────────────────────────────────────────────────────

async def _forge_pipeline(user_email: str,
                           junk_desc: str,
                           project_type: str,
                           detail_level: str,
                           task=None) -> dict:

    def _update(msg):
        if task:
            task.update_state(state="PROGRESS", meta={"message": msg})

    # 0 — Recall Conception memory (context for all agents)
    _update("🔍 Scanning Conception memory banks...")
    ctx = await _recall_conception_memory(user_email, junk_desc, project_type)

    # 1 — Grok: structural analysis
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
                        user_email, junk_desc, project_type, blueprint,
                        grok_out,
                        notes.get("review_notes", ""),
                        total_tokens,
                        notes.get("conception_ready", False),
                    ),
                )
                build_id = cur.fetchone()[0]
                conn.commit()
        log.info("Build %d saved to database.", build_id)
    except Exception as e:
        log.error("DB save failed: %s", e)

    # 5 — Absorb into Conception (awaited directly — fixes ensure_future bug)
    if build_id:
        await _absorb_into_conception(
            user_email    = user_email,
            junk_desc     = junk_desc,
            project_type  = project_type,
            blueprint     = blueprint,
            grok_notes    = grok_out,
            claude_notes  = notes.get("review_notes", ""),
            build_id      = build_id,
            tokens_used   = total_tokens,
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
        "agents_used":             ["GROK-3", "CLAUDE-SONNET", "GEMINI-FLASH"],
        "conception_context_used": bool(ctx),
    }


# ── CELERY TASK ────────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="ai_worker.forge_blueprint_task",
    max_retries=2,
    soft_time_limit=180,
    time_limit=200,
)
def forge_blueprint_task(self,
                          user_email: str,
                          junk_desc: str,
                          project_type: str,
                          detail_level: str = "Standard"):
    log.info("Forge started: %s | %s | %s", user_email, project_type, detail_level)
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            _forge_pipeline(user_email, junk_desc, project_type, detail_level, task=self)
        )
    except Exception as e:
        log.error("Forge pipeline failed: %s", e)
        raise self.retry(exc=e, countdown=10)
    finally:
        loop.close()
