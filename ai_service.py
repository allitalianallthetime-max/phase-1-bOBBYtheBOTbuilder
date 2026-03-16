import os, secrets, re, psycopg2.pool, redis, json
from fastapi import FastAPI, Header, Depends, HTTPException
from pydantic import BaseModel
from celery.result import AsyncResult
from celery import Celery
from datetime import datetime

app = FastAPI()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("ai_tasks", broker=REDIS_URL, backend=REDIS_URL)

try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
except Exception:
    redis_client = None

# ── STARTUP GUARD: Fail loudly if DATABASE_URL is missing ──
_db_url = os.getenv("DATABASE_URL")
if not _db_url:
    raise RuntimeError("DATABASE_URL environment variable is not set. Cannot start ai_service.")

db_pool = psycopg2.pool.ThreadedConnectionPool(1, 10, _db_url)


def verify_key(x_internal_key: str = Header(None)):
    """Authenticate internal service-to-service requests."""
    expected = os.getenv("INTERNAL_API_KEY", "")
    if not secrets.compare_digest(x_internal_key or "", expected):
        raise HTTPException(status_code=403, detail="Invalid internal key.")


# ── CONTENT SAFETY FILTER ──────────────────────────────────────────────────────
# Screens project names and inventory descriptions before any AI agent is called.
# Zero API cost — blocked requests never enter the Celery queue.
#
# TIER 1: Absolute block — weapons, explosives, chemical/biological threats
# TIER 2: Block with redirect — drugs, break-in tools, stalking, counterfeiting
# TIER 3: Allowed — knives, crossbows, trebuchets, hunting gear (legitimate maker projects)

_TIER1_PATTERNS = [
    # Explosives & bombs
    r"\b(pipe\s*bomb|ied|improvised\s*explosive|explosive\s*device)\b",
    r"\b(c[\-\s]?4|semtex|dynamite|det[oa]nat[oe]r|blasting\s*cap)\b",
    r"\b(car\s*bomb|suicide\s*bomb|vest\s*bomb|nail\s*bomb|pressure\s*cooker\s*bomb)\b",
    r"\b(grenade|land\s*mine|claymore|molotov|napalm|incendiary\s*device)\b",
    r"\b(ammonium\s*nitrate\s*(bomb|explosive|device))\b",
    r"\b(thermite\s*(bomb|weapon|device))\b",
    # Firearms manufacturing
    r"\b(ghost\s*gun|3d\s*print(ed)?\s*gun|zip\s*gun|slam\s*fire)\b",
    r"\b(gun\s*manufactur|build\s*a?\s*(gun|firearm|rifle|pistol|shotgun))\b",
    r"\b(ar[\-\s]?15\s*(lower|receiver|build))\b",
    r"\b(suppressor|silencer)\b(?!.*\b(exhaust|muffler|noise\s*reduc)\b)",
    r"\b(bump\s*stock|auto\s*sear|full\s*auto\s*convert)\b",
    # Chemical weapons
    r"\b(nerve\s*(agent|gas)|sarin|vx\s*gas|tabun|mustard\s*gas)\b",
    r"\b(chlorine\s*gas\s*(weapon|bomb|attack))\b",
    r"\b(ricin|anthrax|botulinum\s*toxin)\b",
    r"\b(chemical\s*weapon|poison\s*gas|toxic\s*(gas|weapon|agent))\b",
    # Biological weapons
    r"\b(biological\s*weapon|bio[\-\s]?weapon|weaponized\s*(virus|bacteria|pathogen))\b",
    # Radiological
    r"\b(dirty\s*bomb|radiological\s*(weapon|device|dispersal))\b",
    r"\b(nuclear\s*(bomb|weapon|device))\b",
]

_TIER2_PATTERNS = [
    # Drug manufacturing
    r"\b(meth\s*lab|cook(ing)?\s*meth|synthesize\s*(meth|mdma|lsd|fentanyl|cocaine))\b",
    r"\b(drug\s*(lab|manufactur|production|synthesis))\b",
    # Break-in tools designed for illegal entry
    r"\b(lock\s*pick(ing)?\s*(kit|set|tool))\b(?!.*\b(sport|hobby|locksmith)\b)",
    r"\b(bump\s*key|slim\s*jim\s*(break|car\s*theft))\b",
    # Stalking / surveillance targeting individuals
    r"\b(spy\s*on\s*(my|wife|husband|girlfriend|boyfriend|ex|neighbor))\b",
    r"\b(hidden\s*camera\s*(spy|stalk|watch))\b",
    r"\b(gps\s*track(er|ing)\s*(stalk|spy|follow|someone))\b",
    # Counterfeiting
    r"\b(counterfeit\s*(money|currency|bills|coins))\b",
    r"\b(fake\s*(id|passport|license|documents))\b",
    r"\b(money\s*print(er|ing)\s*(fake|counterfeit))\b",
]

_tier1_compiled = [re.compile(p, re.IGNORECASE) for p in _TIER1_PATTERNS]
_tier2_compiled = [re.compile(p, re.IGNORECASE) for p in _TIER2_PATTERNS]


def _check_content_safety(project_type: str, junk_desc: str) -> dict | None:
    """
    Screen user input for dangerous content BEFORE any AI is called.
    Returns None if safe, or a dict with rejection details if blocked.
    """
    combined = f"{project_type} {junk_desc}"

    # Tier 1: absolute block
    for pattern in _tier1_compiled:
        if pattern.search(combined):
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

    # Tier 2: block with redirect
    for pattern in _tier2_compiled:
        if pattern.search(combined):
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


# ── PYDANTIC MODELS ──
class BuildReq(BaseModel):
    junk_desc: str
    project_type: str
    detail_level: str = "Standard Overview"
    user_email: str = "anonymous"

class ChatMsg(BaseModel):
    user_name: str
    tier: str
    message: str

class BattleReq(BaseModel):
    robot_a_name: str
    robot_a_specs: str
    robot_b_name: str
    robot_b_specs: str


# ── BLUEPRINT GENERATION ──
@app.post("/generate", dependencies=[Depends(verify_key)])
def gen_blueprint(req: BuildReq):

    # ── CONTENT SAFETY CHECK (before any AI call or quota deduction) ──
    safety = _check_content_safety(req.project_type, req.junk_desc)
    if safety:
        raise HTTPException(status_code=403, detail=safety["message"])

    # BUG FIX: getconn() is NOT a context manager. Use try/finally to guarantee
    # the connection is always returned to the pool, even if an exception occurs.
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            if req.user_email not in ("admin", "anonymous"):
                cur.execute(
                    "SELECT build_count, tier FROM licenses WHERE email = %s AND status = 'active'",
                    (req.user_email,)
                )
                lic = cur.fetchone()

                if not lic:
                    raise HTTPException(status_code=402, detail="No active license found.")

                build_count, tier = lic
                limit = 999 if tier == "master" else 100 if tier == "pro" else 25

                if build_count >= limit:
                    raise HTTPException(status_code=402, detail="Engineering quota exceeded.")

                cur.execute(
                    "UPDATE licenses SET build_count = build_count + 1 WHERE email = %s",
                    (req.user_email,)
                )
                conn.commit()
    except HTTPException:
        raise  # Re-raise HTTP exceptions without wrapping them
    except Exception as e:
        conn.rollback()  # Roll back any partial transaction on unexpected errors
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        db_pool.putconn(conn)  # ALWAYS returns the connection, no matter what

    # BUG FIX: argument order must match ai_worker.forge_blueprint_task signature:
    #   forge_blueprint_task(self, user_email, junk_desc, project_type, detail_level)
    task = celery_app.send_task(
        "ai_worker.forge_blueprint_task",
        args=[req.user_email, req.junk_desc, req.project_type, req.detail_level]
    )
    return {"status": "processing", "task_id": task.id}


# ── TASK STATUS POLLING ──
@app.get("/generate/status/{tid}", dependencies=[Depends(verify_key)])
def chk_task(tid: str):
    res = AsyncResult(tid, app=celery_app)

    if res.state == "SUCCESS":
        return {"status": "complete", "result": res.result}

    if res.state == "FAILURE":
        return {"status": "failed", "error": str(res.info)}

    # PENDING, STARTED, or PROGRESS — info may be None or a dict
    message = "Processing..."
    if isinstance(res.info, dict):
        message = res.info.get("message", message)

    return {"status": "processing", "message": message}


# ── ARENA CHAT ──
@app.post("/arena/chat/send", dependencies=[Depends(verify_key)])
def send_chat(msg: ChatMsg):
    if redis_client:
        entry = json.dumps({
            "user": msg.user_name,
            "tier": msg.tier,
            "text": msg.message,
            "time": datetime.utcnow().strftime("%H:%M")
        })
        redis_client.lpush("global_chat", entry)
        redis_client.ltrim("global_chat", 0, 49)
    return {"status": "ok"}


@app.get("/arena/chat/recent", dependencies=[Depends(verify_key)])
def get_chat():
    if not redis_client:
        return []
    messages = redis_client.lrange("global_chat", 0, 49)
    return [json.loads(m) for m in messages][::-1]


# ── ROBOT BATTLE ──
@app.post("/arena/battle", dependencies=[Depends(verify_key)])
def battle(req: BattleReq):
    task = celery_app.send_task(
        "ai_worker.simulate_battle_task",
        args=[req.robot_a_name, req.robot_a_specs, req.robot_b_name, req.robot_b_specs]
    )
    return {"status": "processing", "task_id": task.id}


# ── HEALTH CHECK ──
@app.get("/health")
def health():
    return {"status": "ok"}
