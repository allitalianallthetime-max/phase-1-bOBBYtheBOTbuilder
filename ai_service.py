import os, secrets, psycopg2.pool, redis, json
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
    # Was previously: args=[req.junk_desc, req.project_type, req.user_email, req.detail_level]
    # which put inventory into user_email, project name into junk_desc, and email into project_type.
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

    # PENDING or STARTED — info may be None or a dict
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
