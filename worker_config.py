"""
WORKER CONFIG — Shared infrastructure for all agent modules.
Celery, DB pool, API keys, model names, utilities.
"""

import os
import json
import logging
import asyncio
import time as _time
from typing import Optional

import httpx
import psycopg2.pool
from celery import Celery
from celery.signals import worker_process_init
from contextlib import contextmanager
from anthropic import Anthropic

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# ── LOGGING ──
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ai_worker")


def log_event(event: str, **kwargs):
    kwargs["event"] = event
    kwargs["ts"] = _time.time()
    log.info(json.dumps(kwargs, default=str))


# ── CELERY ──
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
celery_app = Celery("ai_worker", broker=REDIS_URL, backend=REDIS_URL)
celery = celery_app
celery_app.conf.update(
    task_serializer="json", result_serializer="json",
    accept_content=["json"], result_expires=3600,
    worker_prefetch_multiplier=1, task_acks_late=True,
)

# ── DATABASE ──
_db_url = os.getenv("DATABASE_URL")
if not _db_url:
    raise RuntimeError("DATABASE_URL is not set.")

pool = None


@worker_process_init.connect
def _init_worker_db(**kwargs):
    global pool
    pool = psycopg2.pool.ThreadedConnectionPool(1, 5, _db_url)
    log.info("DB pool created in worker process (pid=%d)", os.getpid())


@contextmanager
def get_db():
    if pool is None:
        raise RuntimeError("Database pool not initialized.")
    conn = pool.getconn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


# ── ENV / API KEYS ──
CONCEPTION_URL = os.getenv("CONCEPTION_SERVICE_URL", "http://builder-conception:10000")
INT_KEY        = os.getenv("INTERNAL_API_KEY", "")
ANTHROPIC_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_KEY     = os.getenv("GEMINI_API_KEY", "")
GROK_KEY       = os.getenv("GROK_API_KEY", "")
GMAIL_ADDRESS  = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PW   = os.getenv("GMAIL_APP_PW", "")

# ── MODEL NAMES (change here when upgrading) ──
GROK_MODEL    = os.getenv("GROK_MODEL",    "grok-4.20-beta-0309-reasoning")
GROK_TEMPERATURE = float(os.getenv("GROK_TEMPERATURE", "0.3"))
CLAUDE_MODEL  = os.getenv("CLAUDE_MODEL",  "claude-sonnet-4-20250514")
GEMINI_MODEL  = os.getenv("GEMINI_MODEL",  "gemini-2.5-flash")

# ── ANTHROPIC CLIENT ──
_anthropic_client: Optional[Anthropic] = None


def get_anthropic() -> Anthropic:
    global _anthropic_client
    if _anthropic_client is None and ANTHROPIC_KEY:
        _anthropic_client = Anthropic(api_key=ANTHROPIC_KEY)
    return _anthropic_client


# ── GEMINI INIT ──
if GENAI_AVAILABLE and GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)


def internal_headers() -> dict:
    return {"x-internal-key": INT_KEY}


# ── COST ESTIMATION ──
COST_PER_1K = {
    "grok_input": 0.0002, "grok_output": 0.0005,
    "claude_input": 0.003, "claude_output": 0.015,
    "gemini_input": 0.0001, "gemini_output": 0.0004,
}


def estimate_cost(agent: str, input_tokens: int, output_tokens: int) -> float:
    in_cost = (input_tokens / 1000) * COST_PER_1K.get(f"{agent}_input", 0)
    out_cost = (output_tokens / 1000) * COST_PER_1K.get(f"{agent}_output", 0)
    return round(in_cost + out_cost, 4)


# ── UTILITIES ──

def truncate(text: str, max_chars: int = 5000) -> str:
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    for sep in ["\n\n", ".\n", ". ", "\n"]:
        idx = cut.rfind(sep)
        if idx > max_chars * 0.7:
            return cut[:idx + 1]
    return cut


def estimate_tokens(text: str) -> int:
    return len(text) // 4


class Timer:
    def __init__(self, name: str):
        self.name = name
        self.elapsed = 0.0
    def __enter__(self):
        self._start = _time.time()
        return self
    def __exit__(self, *args):
        self.elapsed = round(_time.time() - self._start, 1)
        log_event("agent_timing", agent=self.name, elapsed_s=self.elapsed)


async def retry_async(coro_fn, *args, max_attempts=3, base_delay=4.0, label="LLM"):
    last_err = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await coro_fn(*args)
        except Exception as e:
            last_err = e
            err_str = str(e).lower()
            is_retryable = any(k in err_str for k in ["429", "rate", "timeout", "overloaded", "503"])
            if not is_retryable or attempt == max_attempts:
                log_event("retry_exhausted", label=label, attempt=attempt, error=str(e)[:200])
                raise
            delay = base_delay * (2 ** (attempt - 1))
            log_event("retry_backoff", label=label, attempt=attempt, delay_s=delay)
            await asyncio.sleep(delay)
    raise last_err


def send_blueprint_email(user_email, project_type, blueprint, build_id, notes) -> bool:
    if not GMAIL_ADDRESS or not GMAIL_APP_PW or not user_email:
        return False
    if user_email in ("admin", "anonymous"):
        return False
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    difficulty = notes.get("difficulty_rating", "Unknown")
    build_time = notes.get("estimated_build_time", "Unknown")
    feasibility = "See blueprint"
    for line in blueprint.split("\n"):
        if "FEASIBILITY" in line.upper():
            feasibility = line.strip()[:80]
            break
    html_body = f"""<div style="font-family:Arial;max-width:700px;margin:0 auto;background:#0A0E17;color:#E2E8F0;padding:30px;border-radius:12px;">
<h1 style="color:#FF4500;text-align:center;">YOUR BLUEPRINT IS READY</h1>
<p style="color:#94A3B8;text-align:center;">The Builder Foundry</p>
<div style="background:#1E293B;padding:20px;border-radius:8px;border-left:4px solid #FF4500;margin:20px 0;">
<div style="color:#F97316;font-size:12px;">PROJECT</div>
<div style="color:white;font-size:20px;font-weight:bold;">{project_type}</div>
</div>
<pre style="background:#1E293B;padding:20px;border-radius:8px;color:#CBD5E1;font-size:12px;white-space:pre-wrap;">{blueprint[:2000]}...</pre>
<p style="text-align:center;margin:20px 0;"><a href="https://bobtherobotbuilder.com" style="background:#FF4500;color:white;padding:14px 40px;border-radius:8px;text-decoration:none;font-weight:bold;">VIEW FULL BLUEPRINT</a></p>
<p style="color:#64748B;font-size:11px;text-align:center;">{feasibility}<br>AoC3P0 Systems | The Builder Foundry</p>
</div>"""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Your Blueprint is Ready: {project_type}"
        msg["From"] = f"Builder Foundry <{GMAIL_ADDRESS}>"
        msg["To"] = user_email
        msg.attach(MIMEText(f"Your blueprint for {project_type} is ready at bobtherobotbuilder.com", "plain"))
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PW)
            server.send_message(msg)
        log_event("email_sent", user=user_email)
        return True
    except Exception as e:
        log_event("email_failed", user=user_email, error=str(e)[:100])
        return False
