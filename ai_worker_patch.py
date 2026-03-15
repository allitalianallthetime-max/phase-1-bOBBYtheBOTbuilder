"""
AI WORKER — CONCEPTION MEMORY HOOKS
====================================
This file shows the exact changes to make to ai_worker.py.
Two hooks: RECALL (before forge) and ABSORB (after forge).

STEP 1: Add this import near the top of ai_worker.py
------------------------------------------------------
"""
import httpx  # already imported? keep it. if not, add it.

CONCEPTION_URL = os.getenv("CONCEPTION_SERVICE_URL", "http://builder-conception:10000")
INTERNAL_KEY   = os.getenv("INTERNAL_API_KEY", "")

def _h():
    return {"x-internal-key": INTERNAL_KEY}


"""
STEP 2: RECALL — inject Conception memory BEFORE calling the AI agents.
------------------------------------------------------------------------
Add this function to ai_worker.py, then call it at the top of forge_blueprint_task().
"""

def _recall_conception_memory(user_email: str, project_type: str, inventory: str) -> str:
    """
    Pulls Conception's accumulated memory for this operator and project domain.
    Returns a context string to prepend to every AI agent's system prompt.
    If Conception service is offline or empty, returns "" — no crash, no block.
    """
    try:
        resp = httpx.post(
            f"{CONCEPTION_URL}/conception/recall",
            json={
                "user_email":   user_email,
                "project_type": project_type,
                "inventory":    inventory,
            },
            headers=_h(),
            timeout=8.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("context", "")
    except Exception as e:
        # Conception being offline must NEVER block a blueprint from being forged
        log.warning("Conception recall unavailable: %s", e)
    return ""


"""
STEP 3: ABSORB — feed the finished blueprint into Conception after saving to DB.
---------------------------------------------------------------------------------
Add this function, then call it at the END of forge_blueprint_task() after
the database INSERT is complete.

Call it like:
    _absorb_into_conception(
        build_id=new_build_id,
        user_email=user_email,
        project_type=project_type,
        blueprint=final_blueprint,
        grok_notes=grok_output,
        claude_notes=claude_output,
        tokens_used=total_tokens,
    )
"""

def _absorb_into_conception(
    build_id:     int,
    user_email:   str,
    project_type: str,
    blueprint:    str,
    grok_notes:   str,
    claude_notes: str,
    tokens_used:  int,
):
    """
    Sends the completed blueprint to Conception for learning.
    Runs synchronously but is fast — Gemini extraction happens async in conception_memory.py.
    Non-blocking: any failure is logged and ignored so the task result is never affected.
    """
    try:
        resp = httpx.post(
            f"{CONCEPTION_URL}/conception/absorb",
            json={
                "build_id":     build_id,
                "user_email":   user_email,
                "project_type": project_type,
                "blueprint":    blueprint,
                "grok_notes":   grok_notes,
                "claude_notes": claude_notes,
                "tokens_used":  tokens_used,
            },
            headers=_h(),
            timeout=15.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            log.info(
                "Conception absorbed build %d — domain: %s, patterns: %d, insight: %s",
                build_id,
                data.get("domain", "?"),
                data.get("patterns_extracted", 0),
                data.get("insight", ""),
            )
        else:
            log.warning("Conception absorb returned %d for build %d", resp.status_code, build_id)
    except Exception as e:
        log.warning("Conception absorb failed (non-critical): %s", e)


"""
STEP 4: In forge_blueprint_task(), add the memory context to each agent prompt.
--------------------------------------------------------------------------------
Find where you build the system prompt for each agent and prepend:

    memory_ctx = _recall_conception_memory(user_email, project_type, junk_desc)

    # Then in each agent's system prompt:
    grok_system = f\"\"\"{memory_ctx}

    You are GROK-3, an expert mechanical engineer...
    [rest of your existing system prompt]
    \"\"\"

    # Same for Claude and Gemini prompts.
"""


"""
STEP 5: After saving to DB, add the absorb call.
-------------------------------------------------
Your existing DB save code does something like:
    cur.execute("INSERT INTO builds (...) VALUES (...) RETURNING id")
    build_id = cur.fetchone()[0]
    conn.commit()

Right after that conn.commit(), add:
    _absorb_into_conception(
        build_id=build_id,
        user_email=user_email,
        project_type=project_type,
        blueprint=final_synthesis,
        grok_notes=grok_output,
        claude_notes=claude_output,
        tokens_used=total_tokens_used,
    )
"""
