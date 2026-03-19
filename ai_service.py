"""
AI SERVICE — FASTAPI GATEWAY
==============================
Routes blueprint requests through content safety → quota check → Celery queue.
Also serves Arena chat, robot battles, and health checks.

Key fixes applied:
  - Content safety filter (Tier 1/2) blocks weapons & harmful builds at the gate
  - Argument order matches ai_worker.forge_blueprint_task signature exactly
  - Input validation rejects empty project names or inventory
  - detail_level default matches actual slider values
  - Logging for safety blocks, errors, and key events
  - Health check verifies DB and Redis connectivity
  - Python 3.9+ compatible type hints
"""

import os
import re
import json
import secrets
import logging
from typing import Optional
from datetime import datetime

import psycopg2.pool
import redis
from fastapi import FastAPI, Header, Depends, HTTPException
from pydantic import BaseModel
from celery import Celery
from celery.result import AsyncResult

# ── LOGGING ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ai_service")

# ── APP ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Builder Foundry AI Service", version="1.0.0")

# ── CELERY ────────────────────────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("ai_tasks", broker=REDIS_URL, backend=REDIS_URL)

# ── REDIS (for rate limiting + Arena chat) ────────────────────────────────────
try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()
    log.info("Redis connected.")
except Exception as e:
    log.warning("Redis unavailable: %s", e)
    redis_client = None


# ── RATE LIMITER ──────────────────────────────────────────────────────────────
def _rate_limit(key: str, max_requests: int, window_seconds: int) -> bool:
    """
    Redis-based sliding window rate limiter.
    Returns True if request is ALLOWED, False if rate limit exceeded.
    If Redis is down, allows the request (fail-open).
    """
    if not redis_client:
        return True  # No Redis = no rate limiting = fail-open
    try:
        rk = f"rl:{key}"
        current = redis_client.get(rk)
        if current and int(current) >= max_requests:
            return False
        pipe = redis_client.pipeline()
        pipe.incr(rk)
        pipe.expire(rk, window_seconds)
        pipe.execute()
        return True
    except Exception as e:
        log.warning("Rate limiter error (allowing request): %s", e)
        return True

# ── DATABASE ──────────────────────────────────────────────────────────────────
_db_url = os.getenv("DATABASE_URL")
if not _db_url:
    raise RuntimeError("DATABASE_URL environment variable is not set. Cannot start ai_service.")

db_pool = psycopg2.pool.ThreadedConnectionPool(1, 10, _db_url)
log.info("Database pool created.")


# ── AUTH ──────────────────────────────────────────────────────────────────────
def verify_key(x_internal_key: str = Header(None)):
    """Authenticate internal service-to-service requests."""
    expected = os.getenv("INTERNAL_API_KEY", "")
    if not secrets.compare_digest(x_internal_key or "", expected):
        raise HTTPException(status_code=403, detail="Invalid internal key.")


# ══════════════════════════════════════════════════════════════════════════════
# CONTENT SAFETY FILTER
# ══════════════════════════════════════════════════════════════════════════════
# Screens project names and inventory descriptions BEFORE any AI agent is called.
# Zero API cost — blocked requests never enter the Celery queue.
#
# TIER 1: Absolute block — weapons, explosives, chemical/biological threats
# TIER 2: Block with redirect — drugs, break-in tools, stalking, counterfeiting
# TIER 3: Allowed — knives, crossbows, trebuchets, hunting gear (legitimate maker projects)

_TIER1_PATTERNS = [
    # ── Explosives & bombs ──
    r"\b(pipe\s*bomb|ied|improvised\s*explosive|explosive\s*device)\b",
    r"\b(c[\-\s]?4|semtex|dynamite|det[oa]nat[oe]r|blasting\s*cap)\b",
    r"\b(car\s*bomb|suicide\s*bomb|vest\s*bomb|nail\s*bomb|pressure\s*cooker\s*bomb)\b",
    r"\b(grenade|land\s*mine|claymore|molotov|napalm|incendiary\s*device)\b",
    r"\b(ammonium\s*nitrate\s*(bomb|explosive|device))\b",
    r"\b(thermite\s*(bomb|weapon|device))\b",
    # ── Firearms manufacturing ──
    r"\b(ghost\s*gun|3d\s*print(ed)?\s*gun|zip\s*gun|slam\s*fire)\b",
    r"\b(gun\s*manufactur|build\s*a?\s*(gun|firearm|rifle|pistol|shotgun))\b",
    r"\b(ar[\-\s]?15\s*(lower|receiver|build))\b",
    r"\b(suppressor|silencer)\b(?!.*\b(exhaust|muffler|noise\s*reduc)\b)",
    r"\b(bump\s*stock|auto\s*sear|full\s*auto\s*convert)\b",
    # ── Chemical weapons ──
    r"\b(nerve\s*(agent|gas)|sarin|vx\s*gas|tabun|mustard\s*gas)\b",
    r"\b(chlorine\s*gas\s*(weapon|bomb|attack))\b",
    r"\b(ricin|anthrax|botulinum\s*toxin)\b",
    r"\b(chemical\s*weapon|poison\s*gas|toxic\s*(gas|weapon|agent))\b",
    # ── Biological weapons ──
    r"\b(biological\s*weapon|bio[\-\s]?weapon|weaponized\s*(virus|bacteria|pathogen))\b",
    # ── Radiological ──
    r"\b(dirty\s*bomb|radiological\s*(weapon|device|dispersal))\b",
    r"\b(nuclear\s*(bomb|weapon|device))\b",
]

_TIER2_PATTERNS = [
    # ── Drug manufacturing ──
    r"\b(meth\s*lab|cook(ing)?\s*meth|synthesize\s*(meth|mdma|lsd|fentanyl|cocaine))\b",
    r"\b(drug\s*(lab|manufactur|production|synthesis))\b",
    # ── Break-in tools (unless hobby/locksmith context) ──
    r"\b(lock\s*pick(ing)?\s*(kit|set|tool))\b(?!.*\b(sport|hobby|locksmith)\b)",
    r"\b(bump\s*key|slim\s*jim\s*(break|car\s*theft))\b",
    # ── Stalking / surveillance targeting individuals ──
    r"\b(spy\s*on\s*(my|wife|husband|girlfriend|boyfriend|ex|neighbor))\b",
    r"\b(hidden\s*camera\s*(spy|stalk|watch))\b",
    r"\b(gps\s*track(er|ing)\s*(stalk|spy|follow|someone))\b",
    # ── Counterfeiting ──
    r"\b(counterfeit\s*(money|currency|bills|coins))\b",
    r"\b(fake\s*(id|passport|license|documents))\b",
    r"\b(money\s*print(er|ing)\s*(fake|counterfeit))\b",
]

_tier1_compiled = [re.compile(p, re.IGNORECASE) for p in _TIER1_PATTERNS]
_tier2_compiled = [re.compile(p, re.IGNORECASE) for p in _TIER2_PATTERNS]


def _check_content_safety(project_type: str, junk_desc: str) -> Optional[dict]:
    """
    Screen user input for dangerous content BEFORE any AI is called.
    Returns None if safe, or a dict with rejection details if blocked.
    """
    combined = f"{project_type} {junk_desc}"

    for pattern in _tier1_compiled:
        if pattern.search(combined):
            log.warning("TIER 1 BLOCK: project='%s'", project_type[:80])
            return {
                "blocked": True,
                "tier": 1,
                "message": (
                    "This project request has been blocked. The Builder Foundry "
                    "does not generate blueprints for weapons, explosives, or "
                    "devices intended to harm people. This policy exists to keep "
                    "our community safe."
                ),
            }

    for pattern in _tier2_compiled:
        if pattern.search(combined):
            log.warning("TIER 2 BLOCK: project='%s'", project_type[:80])
            return {
                "blocked": True,
                "tier": 2,
                "message": (
                    "This project request has been blocked. The Builder Foundry "
                    "cannot assist with this type of build. If you believe this "
                    "is an error, please rephrase your project description or "
                    "contact support."
                ),
            }

    return None  # Safe — proceed


# ══════════════════════════════════════════════════════════════════════════════
# PYDANTIC MODELS
# ══════════════════════════════════════════════════════════════════════════════

class BuildReq(BaseModel):
    junk_desc: str
    project_type: str
    detail_level: str = "Standard"
    user_email: str = "anonymous"
    mode: str = "blueprint"  # "blueprint" or "mechanic"

class ChatMsg(BaseModel):
    user_name: str
    tier: str
    message: str

class BattleReq(BaseModel):
    robot_a_name: str
    robot_a_specs: str
    robot_b_name: str
    robot_b_specs: str


# ══════════════════════════════════════════════════════════════════════════════
# BLUEPRINT GENERATION
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/generate", dependencies=[Depends(verify_key)])
def gen_blueprint(req: BuildReq):

    # ── INPUT VALIDATION ──
    project_clean = req.project_type.strip()
    inventory_clean = req.junk_desc.strip()

    if not project_clean:
        raise HTTPException(status_code=400, detail="Project name is required.")
    if not inventory_clean:
        raise HTTPException(status_code=400, detail="Inventory description is required.")
    if len(project_clean) < 3:
        raise HTTPException(status_code=400, detail="Project name is too short.")
    if len(inventory_clean) < 10:
        raise HTTPException(
            status_code=400,
            detail="Inventory description is too short. Describe what you have in more detail."
        )

    # ── CONTENT SAFETY CHECK (before any AI call or quota deduction) ──
    safety = _check_content_safety(project_clean, inventory_clean)
    if safety:
        raise HTTPException(status_code=403, detail=safety["message"])

    # ── RATE LIMITING (before quota check — blocks spam before touching DB) ──
    if not _rate_limit(f"forge:{req.user_email}", max_requests=10, window_seconds=3600):
        log.warning("Rate limit hit: forge by %s", req.user_email)
        raise HTTPException(
            status_code=429,
            detail="Too many forge requests. Please wait before trying again."
        )

    # ── TOKEN COST CALCULATION ──
    token_costs = {"Standard": 1, "Industrial": 3, "Experimental": 5}
    cost = token_costs.get(req.detail_level, 1)

    # ── TOKEN DEDUCTION (replaces old build_count system) ──
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            if req.user_email not in ("admin", "anonymous"):
                cur.execute(
                    "SELECT token_balance, tier FROM licenses "
                    "WHERE email = %s AND status = 'active' "
                    "ORDER BY created_at DESC LIMIT 1",
                    (req.user_email,)
                )
                lic = cur.fetchone()

                if not lic:
                    raise HTTPException(
                        status_code=402,
                        detail="No active license found."
                    )

                balance, tier = lic

                if balance < cost:
                    if balance == 0 and tier == "trial":
                        raise HTTPException(
                            status_code=402,
                            detail="Your free token has been used. Buy a Spark pack (3 tokens / $9.99) to keep building!"
                        )
                    raise HTTPException(
                        status_code=402,
                        detail=f"Not enough tokens. This {req.detail_level} build costs {cost} tokens. You have {balance}. Buy more tokens to continue."
                    )

                cur.execute(
                    "UPDATE licenses SET token_balance = token_balance - %s, "
                    "tokens_used = tokens_used + %s "
                    "WHERE email = %s AND status = 'active'",
                    (cost, cost, req.user_email)
                )
                conn.commit()
                log.info(
                    "Forge queued: user=%s project='%s' depth=%s cost=%d tokens remaining=%d",
                    req.user_email, project_clean[:40], req.detail_level,
                    cost, balance - cost
                )
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        log.error("Database error during token check: %s", e)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        db_pool.putconn(conn)

    # ── DISPATCH TO CELERY ──
    # Argument order MUST match ai_worker.forge_blueprint_task signature:
    #   forge_blueprint_task(self, user_email, junk_desc, project_type, detail_level, mode)
    task = celery_app.send_task(
        "ai_worker.forge_blueprint_task",
        args=[req.user_email, inventory_clean, project_clean, req.detail_level, req.mode]
    )
    return {"status": "processing", "task_id": task.id}


# ══════════════════════════════════════════════════════════════════════════════
# TASK STATUS POLLING
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/generate/status/{tid}", dependencies=[Depends(verify_key)])
def chk_task(tid: str):
    res = AsyncResult(tid, app=celery_app)

    if res.state == "SUCCESS":
        return {"status": "complete", "result": res.result}

    if res.state == "FAILURE":
        return {"status": "failed", "error": str(res.info)}

    if res.state == "PROGRESS":
        message = "Processing..."
        if isinstance(res.info, dict):
            message = res.info.get("message", message)
        return {"status": "processing", "message": message}

    # PENDING or STARTED
    return {"status": "processing", "message": "Initializing Round Table..."}


# ══════════════════════════════════════════════════════════════════════════════
# ARENA CHAT
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/arena/chat/send", dependencies=[Depends(verify_key)])
def send_chat(msg: ChatMsg):
    if not redis_client:
        raise HTTPException(status_code=503, detail="Chat service unavailable.")

    # Rate limit: 30 messages per minute per user
    if not _rate_limit(f"chat:{msg.user_name}", max_requests=30, window_seconds=60):
        raise HTTPException(status_code=429, detail="Slow down — too many messages.")

    try:
        entry = json.dumps({
            "user": msg.user_name,
            "tier": msg.tier,
            "text": msg.message,
            "time": datetime.utcnow().strftime("%H:%M")
        })
        redis_client.lpush("global_chat", entry)
        redis_client.ltrim("global_chat", 0, 49)
    except Exception as e:
        log.error("Chat send failed: %s", e)
        raise HTTPException(status_code=500, detail="Chat send failed.")
    return {"status": "ok"}


@app.get("/arena/chat/recent", dependencies=[Depends(verify_key)])
def get_chat():
    if not redis_client:
        return []
    try:
        messages = redis_client.lrange("global_chat", 0, 49)
        return [json.loads(m) for m in messages][::-1]
    except Exception as e:
        log.error("Chat fetch failed: %s", e)
        return []


# ══════════════════════════════════════════════════════════════════════════════
# ROBOT BATTLE
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/arena/battle", dependencies=[Depends(verify_key)])
def battle(req: BattleReq):
    task = celery_app.send_task(
        "ai_worker.simulate_battle_task",
        args=[req.robot_a_name, req.robot_a_specs, req.robot_b_name, req.robot_b_specs]
    )
    return {"status": "processing", "task_id": task.id}


# ══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    """Deep health check — verifies DB and Redis are alive."""
    status = {"api": "ok", "database": "unknown", "redis": "unknown"}

    # Check database
    try:
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            status["database"] = "ok"
        finally:
            db_pool.putconn(conn)
    except Exception as e:
        status["database"] = f"error: {e}"

    # Check Redis
    try:
        if redis_client and redis_client.ping():
            status["redis"] = "ok"
        else:
            status["redis"] = "unavailable"
    except Exception as e:
        status["redis"] = f"error: {e}"

    return status
