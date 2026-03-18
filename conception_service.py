"""
CONCEPTION SERVICE — GATEWAY
==============================
Single FastAPI service that imports all Conception module routers.
One $7/month deploy instead of $28.

Current modules:
  /marketing/*  — Builder Foundry marketing engine (posts, schedule, ideas)

Planned modules (add as routers when ready):
  /briefing/*   — Daily morning summary
  /finance/*    — API cost vs income tracking
  /growth/*     — Self-improvement logging
  /writer/*     — Product description generator

Each module is its own file with its own Router.
When revenue supports it, split into individual services with zero code changes.
"""

import os
import logging

import psycopg2.pool
from fastapi import FastAPI

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("conception_service")

# ── APP ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Conception Intelligence Service", version="1.0.0")

# ── DATABASE ──────────────────────────────────────────────────────────────────
_db_url = os.getenv("DATABASE_URL")
if not _db_url:
    raise RuntimeError("DATABASE_URL is not set.")

pool = psycopg2.pool.ThreadedConnectionPool(2, 10, _db_url)
log.info("Conception DB pool created.")

# ── IMPORT & REGISTER ROUTERS ────────────────────────────────────────────────

# Marketing engine
from conception_marketing import router as marketing_router, set_pool as marketing_set_pool, init_marketing_db
marketing_set_pool(pool)
init_marketing_db()
app.include_router(marketing_router)
log.info("Marketing router loaded: /marketing/*")

# Admin dashboard
from conception_dashboard import router as dashboard_router, set_pool as dashboard_set_pool
dashboard_set_pool(pool)
app.include_router(dashboard_router)
log.info("Dashboard router loaded: /dashboard")

# Future routers go here:
# from conception_briefing_router import router as briefing_router, set_pool as briefing_set_pool
# briefing_set_pool(pool)
# app.include_router(briefing_router)

# from conception_finance_router import router as finance_router, set_pool as finance_set_pool
# finance_set_pool(pool)
# app.include_router(finance_router)


# ── HEALTH ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    """Health check — verifies DB is alive."""
    try:
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        finally:
            pool.putconn(conn)
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    return {
        "status": "ok",
        "service": "conception",
        "database": db_status,
        "modules": ["marketing", "dashboard"],
    }


@app.get("/")
def root():
    return {
        "name": "Conception Intelligence Service",
        "version": "1.0.0",
        "modules": {
            "marketing": "/marketing/daily-tasks, /marketing/generate, /marketing/log, /marketing/stats, /marketing/ideas, /marketing/schedule",
            "dashboard": "/dashboard (browser) or /dashboard/data (JSON)",
        },
        "status": "online",
    }
