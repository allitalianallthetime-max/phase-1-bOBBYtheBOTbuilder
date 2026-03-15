import os, json, psycopg2
from celery import Celery
import google.generativeai as genai

# ── INFRASTRUCTURE ──
_redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("ws_tasks", broker=_redis_url, backend=_redis_url)

# BUG FIX: Bare redis.from_url() at module level crashes the entire worker if
# Redis is unavailable — Celery can't even start. Wrap in try/except.
try:
    import redis as redis_lib
    rc = redis_lib.from_url(_redis_url, decode_responses=True)
except Exception:
    rc = None

if os.getenv("GEMINI_API_KEY"):
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


# ── VISION SCAN TASK ──
@celery_app.task(bind=True, name="workshop_worker.vision_scan_task")
def vision_scan_task(self, pkey: str, mime: str, ctx: str, email: str):
    self.update_state(state="PROGRESS", meta={"message": "Running Computer Vision Hardware Extraction..."})

    # BUG FIX: Guard for Redis being offline — fail fast with a clear message
    # instead of an AttributeError on None.
    if not rc:
        raise RuntimeError("Redis client is offline. Cannot retrieve image data.")

    # BUG FIX: rc.get() returns None if the key expired (10-min TTL) or was
    # never stored. Passing None as image data to Gemini produces a cryptic
    # API error. Catch it here with a clear message.
    b64 = rc.get(pkey)
    if not b64:
        raise ValueError(
            f"Image data not found for key '{pkey}'. "
            "The scan request may have expired (10-minute TTL) or Redis lost the data."
        )

    # BUG FIX: Guard before model creation — if GEMINI_API_KEY is missing,
    # genai is not configured and generate_content() will fail deep in the task.
    # Surface the problem here with a clean offline message.
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is not set. Vision scan unavailable.")

    self.update_state(state="PROGRESS", meta={"message": "Analyzing components with Gemini Vision..."})

    model = genai.GenerativeModel(
        "gemini-2.0-flash",
        generation_config={"response_mime_type": "application/json"},
    )

    prompt = (
        f"Identify robotics hardware, microcontrollers, motors, and structural components "
        f"in this image. Context: {ctx}. "
        "Return strictly a JSON object with an 'identification' object (containing "
        "'equipment_name') and a 'components' array (containing 'name' and 'quantity'). "
        "Do not hallucinate parts not visible."
    )

    r = model.generate_content([
        prompt,
        {"inline_data": {"mime_type": mime, "data": b64}},
    ])

    # BUG FIX: Gemini can return a safety refusal or markdown-wrapped text even
    # with response_mime_type set. json.loads() crashes on those with no useful
    # error. Catch it and return the raw text so you can diagnose the refusal.
    try:
        res = json.loads(r.text)
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(
            f"Gemini returned non-JSON output: {str(e)}. Raw response: {r.text[:300]}"
        )

    self.update_state(state="PROGRESS", meta={"message": "Archiving scan to IP Vault..."})

    # BUG FIX: conn.close() and rc.delete(pkey) were only called on the happy
    # path. Any exception (JSON parse failure, DB error) leaked the connection
    # and left the image key in Redis indefinitely.
    # Fix: try/finally guarantees cleanup no matter what happens.
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS equipment_scans (
                    id             SERIAL PRIMARY KEY,
                    user_email     TEXT,
                    equipment_name TEXT,
                    scan_result    JSONB,
                    created_at     TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute(
                """
                INSERT INTO equipment_scans (user_email, equipment_name, scan_result)
                VALUES (%s, %s, %s) RETURNING id
                """,
                (
                    email,
                    res.get("identification", {}).get("equipment_name", "Unknown"),
                    json.dumps(res),
                ),
            )
            sid = cur.fetchone()[0]
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()          # Always closes — no leak possible
        rc.delete(pkey)       # Always cleans up the Redis key, even on DB failure

    return {"scan_id": sid, "scan_result": res}
