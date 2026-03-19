"""
AI WORKER — CELERY TASK RUNNER (Thin Orchestrator)
===================================================
Pipeline: GROK-4.2 + GEMINI (parallel) -> CLAUDE -> GEMINI review -> Save

All agents, prompts, and config are in separate modules.
This file only contains the pipeline logic and Celery task.
"""

import json
import asyncio
from worker_config import (
    celery_app, celery, get_db, log, log_event,
    Timer, estimate_cost, send_blueprint_email,
)
from agent_grok import run_grok, grok_failed, format_grok_for_claude
from agent_claude import run_claude, generate_schematic
from agent_gemini import run_gemini_research, format_research_for_claude, run_gemini
from conception_memory import recall, absorb


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
        tick = 0
        while _heartbeat_active:
            await asyncio.sleep(10)
            tick += 1
            if task and _heartbeat_active:
                task.update_state(state="PROGRESS",
                    meta={"message": f"Round Table deliberating... ({tick * 10}s elapsed)"})

    heartbeat_task = asyncio.ensure_future(_heartbeat())

    try:
        # 0 — Conception memory
        _update("Scanning Conception memory banks...")
        with Timer("Conception Recall") as t:
            ctx = await recall(user_email, junk_desc, project_type)
        timings["recall"] = t.elapsed

        # 1 — Grok + Gemini Research IN PARALLEL
        if is_mechanic:
            _update("GROK-4.2 diagnosing engine + GEMINI searching web for real fixes...")
        else:
            _update("GROK-4.2 analyzing inventory + GEMINI searching maker projects...")
        with Timer("Grok + Gemini Research") as t:
            grok_r, research_r = await asyncio.gather(
                run_grok(junk_desc, project_type, detail_level, ctx, mode=mode),
                run_gemini_research(project_type, mode=mode),
            )
        timings["grok_and_research"] = t.elapsed
        grok_analysis = grok_r["analysis"]
        grok_ok = not grok_failed(grok_analysis)
        web_research = research_r.get("research", {})

        if not grok_ok:
            if is_mechanic:
                _update("GROK-4.2 incomplete — CLAUDE diagnosing from symptoms directly")
            else:
                _update("GROK-4.2 incomplete — CLAUDE analyzing inventory directly")

        research_text = format_research_for_claude(web_research, mode=mode)

        # 2 — Claude (gets Grok analysis + Gemini research)
        if is_mechanic:
            _update("CLAUDE writing field repair procedure with real-world data...")
        else:
            _update("CLAUDE drafting engineering blueprint with maker research...")
        with Timer("Claude Blueprint") as t:
            claude_r = await run_claude(junk_desc, project_type, grok_analysis,
                                        detail_level, ctx, grok_ok, mode=mode,
                                        research_text=research_text)
        timings["claude"] = t.elapsed
        blueprint = claude_r["blueprint"]

        # 3 + 4 — Gemini Review + Schematic PARALLEL
        if is_mechanic:
            _update("GEMINI verifying repair procedure...")
            with Timer("Gemini Review") as t:
                gemini_r = await run_gemini(blueprint, project_type, ctx)
            timings["review"] = t.elapsed
            schematic_svg = ""
        else:
            _update("GEMINI reviewing + rendering schematic...")
            with Timer("Gemini + Schematic") as t:
                gemini_r, schematic_svg = await asyncio.gather(
                    run_gemini(blueprint, project_type, ctx),
                    generate_schematic(blueprint, project_type, junk_desc),
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

    # Cost estimation
    costs = {}
    grok_tok = grok_r["tokens"]
    costs["grok"] = estimate_cost("grok", int(grok_tok * 0.4), int(grok_tok * 0.6))
    claude_tok = claude_r["tokens"]
    costs["claude_blueprint"] = estimate_cost("claude", int(claude_tok * 0.5), int(claude_tok * 0.5))
    costs["claude_schematic"] = estimate_cost("claude", 1000, 3000) if schematic_svg else 0
    costs["gemini"] = estimate_cost("gemini", 3000, 500)
    costs["total"] = round(sum(costs.values()), 4)

    # 5 — Save to database
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
        log_event("db_save", build_id=build_id)
    except Exception as e:
        log.error("DB save failed: %s", e)

    # 6 — Conception learning
    grok_text_for_absorb = (json.dumps(grok_analysis)[:2000] if isinstance(grok_analysis, dict)
                            else str(grok_analysis)[:2000])
    if build_id:
        await absorb(
            user_email, junk_desc, project_type, blueprint,
            grok_text_for_absorb, notes.get("review_notes", ""),
            build_id, total_tokens,
        )

    # 7 — Email (non-blocking)
    email_sent = await asyncio.to_thread(
        send_blueprint_email, user_email, project_type, blueprint, build_id, notes
    )

    log_event("forge_complete",
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
        "grok_analysis":    format_grok_for_claude(grok_analysis) if isinstance(grok_analysis, dict) else grok_analysis,
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
    log_event("forge_started", user=user_email,
               project=project_type[:50], depth=detail_level, mode=mode)
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            _forge_pipeline(user_email, junk_desc, project_type, detail_level,
                           mode=mode, task=self)
        )
    except Exception as e:
        log_event("forge_failed", user=user_email, error=str(e)[:200],
                   retry=self.request.retries)
        countdown = 10 if self.request.retries == 0 else 30
        raise self.retry(exc=e, countdown=countdown)
    finally:
        loop.close()
