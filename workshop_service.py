import os, secrets, re
import psycopg2.pool, redis, json
from fastapi import FastAPI, Header, Depends, HTTPException
from pydantic import BaseModel
from celery.result import AsyncResult
from celery import Celery

app = FastAPI()

# ── INFRASTRUCTURE ──
_redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("ws_tasks", broker=_redis_url, backend=_redis_url)

try:
    rc = redis.from_url(_redis_url, decode_responses=True)
except Exception:  # BUG FIX: bare except: swallows SystemExit/KeyboardInterrupt
    rc = None

# BUG FIX: db_pool was created but never used in any endpoint, silently holding
# up to 10 Postgres connections open for nothing. Removed until this service
# actually needs direct DB access. Add it back when you wire in DB endpoints.
# If you DO need it:
#   _db_url = os.getenv("DATABASE_URL")
#   if not _db_url: raise RuntimeError("DATABASE_URL not set")
#   db_pool = psycopg2.pool.ThreadedConnectionPool(1, 10, _db_url)


# ── AUTH ──
def verify(x_internal_key: str = Header(None)):
    # BUG FIX: os.getenv("INTERNAL_API_KEY") returns None when the var is missing.
    # secrets.compare_digest(str, None) raises TypeError — crashing the whole service.
    # Fix: always fall back to "" so compare_digest always gets two strings.
    expected = os.getenv("INTERNAL_API_KEY", "")
    if not secrets.compare_digest(x_internal_key or "", expected):
        raise HTTPException(status_code=403, detail="Invalid internal key.")


# ── MODELS ──
class ScanImg(BaseModel):
    image_base64: str
    user_email: str
    context: str


# ── ENDPOINTS ──
@app.post("/scan/base64", dependencies=[Depends(verify)])
def scan_img(req: ScanImg):
    mime = "image/jpeg"
    b64 = req.image_base64

    if b64.startswith("data:"):
        # BUG FIX: match can be None if the data URL is malformed (e.g. missing
        # semicolon or base64 marker). Dereferencing None raises AttributeError.
        match = re.match(r"data:(image/\w+);base64,(.+)", b64, re.DOTALL)
        if not match:
            raise HTTPException(
                status_code=400,
                detail="Malformed data URL. Expected format: data:image/<type>;base64,<data>"
            )
        mime = match.group(1)
        b64  = match.group(2)

    # BUG FIX: If Redis is unavailable, the image is never stored but the task
    # is dispatched anyway with a key that resolves to nothing. The worker gets
    # an empty result and silently fails. Now we fail fast with a clear error.
    if not rc:
        raise HTTPException(
            status_code=503,
            detail="Image cache unavailable. Redis connection is offline."
        )

    pkey = f"scan:{secrets.token_hex(8)}"
    rc.setex(pkey, 600, b64)

    task = celery_app.send_task(
        "workshop_worker.vision_scan_task",
        args=[pkey, mime, req.context, req.user_email]
    )
    return {"status": "processing", "task_id": task.id}


@app.get("/task/status/{tid}", dependencies=[Depends(verify)])
def check_task(tid: str):
    res = AsyncResult(tid, app=celery_app)

    if res.state == "SUCCESS":
        return {"status": "complete", "result": res.result}

    if res.state == "FAILURE":
        return {"status": "failed", "error": str(res.info)}

    # PENDING or STARTED — res.info may be None or a progress dict
    message = "Processing data..."
    if isinstance(res.info, dict):
        message = res.info.get("message", message)

    return {"status": "processing", "message": message}


# ── HEALTH ──
@app.get("/health")
def health():
    return {
        "status": "ok",
        "redis": "connected" if rc else "offline",
    }
