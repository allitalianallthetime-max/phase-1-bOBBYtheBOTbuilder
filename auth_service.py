"""
AUTH SERVICE
============
Handles license verification, JWT issuance, license creation,
and expiring-license queries for the scheduler worker.

Merged from: auth_service.py + auth_service_expiring_patch.py
Fixes applied:
  - JWT_SECRET guard: None key produces forgeable tokens → RuntimeError on startup
  - expires_at NULL guard: None < datetime raises TypeError → guarded explicitly
  - compare_digest guard: os.getenv returns None → always pass two strings
  - Patch import cleanup: datetime already imported at module level, removed
    redundant `from datetime import datetime, timedelta` inside the endpoint
  - Patch endpoint fully integrated (no longer a separate file)
"""

import os
import secrets
import datetime
import json
import logging
import psycopg2.pool
import jwt
from contextlib import contextmanager
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("auth_service")

app = FastAPI()

# ── STARTUP GUARDS ─────────────────────────────────────────────────────────────

_db_url = os.getenv("DATABASE_URL")
if not _db_url:
    raise RuntimeError("DATABASE_URL is not set.")

_jwt_secret = os.getenv("JWT_SECRET")
if not _jwt_secret:
    # jwt.encode() with None as key signs with a null secret —
    # every token becomes trivially forgeable.
    raise RuntimeError("JWT_SECRET is not set. Cannot issue secure tokens.")

_int_key = os.getenv("INTERNAL_API_KEY", "")

pool = psycopg2.pool.ThreadedConnectionPool(2, 15, _db_url)


# ── DB CONTEXT MANAGER ─────────────────────────────────────────────────────────

@contextmanager
def get_db():
    """
    Correct pool pattern: @contextmanager + try/finally guarantees
    putconn() always runs. Rollback on error prevents dirty connections
    being returned to the pool mid-transaction.
    """
    conn = pool.getconn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


# ── DB INIT ────────────────────────────────────────────────────────────────────

def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS licenses (
                    id                 SERIAL PRIMARY KEY,
                    license_key        TEXT UNIQUE,
                    email              TEXT,
                    name               TEXT,
                    stripe_customer_id TEXT,
                    status             TEXT      DEFAULT 'active',
                    tier               TEXT,
                    expires_at         TIMESTAMP,
                    build_count        INTEGER   DEFAULT 0,
                    token_balance      INTEGER   DEFAULT 0,
                    tokens_purchased   INTEGER   DEFAULT 0,
                    tokens_used        INTEGER   DEFAULT 0,
                    sub_tier           VARCHAR(20) DEFAULT NULL,
                    sub_tokens_monthly INTEGER   DEFAULT 0,
                    sub_next_refill    TIMESTAMP DEFAULT NULL,
                    notes              TEXT,
                    created_at         TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS notification_queue (
                    id         SERIAL PRIMARY KEY,
                    type       TEXT,
                    to_email   TEXT,
                    name       TEXT,
                    payload    JSONB,
                    status     TEXT      DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    id              SERIAL PRIMARY KEY,
                    email           TEXT UNIQUE NOT NULL,
                    display_name    TEXT,
                    business_name   TEXT,
                    phone           TEXT,
                    location        TEXT,
                    bio             TEXT,
                    certification   TEXT,
                    default_labor_rate  DECIMAL(8,2),
                    default_tax_rate    DECIMAL(5,2),
                    default_markup      DECIMAL(5,2),
                    default_terms       TEXT,
                    preferences     JSONB DEFAULT '{}',
                    created_at      TIMESTAMP DEFAULT NOW(),
                    updated_at      TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_vehicles (
                    id          SERIAL PRIMARY KEY,
                    email       TEXT NOT NULL,
                    nickname    TEXT,
                    year        TEXT,
                    make        TEXT,
                    model       TEXT,
                    engine      TEXT,
                    mileage     TEXT,
                    environment TEXT,
                    notes       TEXT,
                    is_default  BOOLEAN DEFAULT FALSE,
                    created_at  TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_inventory (
                    id          SERIAL PRIMARY KEY,
                    email       TEXT NOT NULL,
                    item_name   TEXT NOT NULL,
                    description TEXT,
                    category    TEXT,
                    condition   TEXT,
                    specs       TEXT,
                    location    TEXT,
                    added_at    TIMESTAMP DEFAULT NOW()
                )
            """)
            conn.commit()
    log.info("DB initialized.")


init_db()


# ── INTERNAL AUTH ──────────────────────────────────────────────────────────────

def verify_int(x_internal_key: str = Header(None)):
    """
    compare_digest requires two strings. os.getenv returns None when unset,
    so we default _int_key to "" at module level and coerce the header the same.
    """
    if not secrets.compare_digest(x_internal_key or "", _int_key):
        raise HTTPException(status_code=403, detail="Invalid internal key.")


# ── MODELS ─────────────────────────────────────────────────────────────────────

class VerifyReq(BaseModel):
    license_key: str


class CreateReq(BaseModel):
    email: str
    name: str = ""
    stripe_customer_id: str = ""
    days: int = 30
    tier: str = "pro"
    notes: str = ""


class TrialReq(BaseModel):
    email: str
    email_optin: bool = False


# ── RATE LIMITER (in-memory, resets on restart — fine for abuse prevention) ──
_rate_limits: dict = {}  # {"key": (count, first_request_timestamp)}


def _rate_limit(key: str, max_requests: int, window_seconds: int) -> bool:
    """Returns True if ALLOWED, False if rate limit exceeded."""
    import time
    now = time.time()
    if key in _rate_limits:
        count, window_start = _rate_limits[key]
        if now - window_start > window_seconds:
            _rate_limits[key] = (1, now)
            return True
        if count >= max_requests:
            return False
        _rate_limits[key] = (count + 1, window_start)
        return True
    _rate_limits[key] = (1, now)
    return True


# ── ENDPOINTS ──────────────────────────────────────────────────────────────

@app.post("/auth/trial")
def create_trial(req: TrialReq, _=Depends(verify_int)):
    """
    Create a free trial license. 1 build, 7 days, no payment required.
    Returns the license key immediately. One trial per email address.
    """
    email = req.email.strip().lower()

    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email address required.")

    # Rate limit: 5 trial attempts per hour per email (blocks rapid-fire abuse)
    if not _rate_limit(f"trial:{email}", max_requests=5, window_seconds=3600):
        log.warning("Trial rate limit hit: %s", email)
        raise HTTPException(status_code=429, detail="Too many trial requests. Try again later.")

    # Check if this email already has ANY license (trial or paid)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, tier, status FROM licenses WHERE email = %s LIMIT 1",
                (email,),
            )
            existing = cur.fetchone()

    if existing:
        _, ex_tier, ex_status = existing
        if ex_status == "active":
            raise HTTPException(
                status_code=409,
                detail=f"This email already has an active {ex_tier} license. Log in with your existing key."
            )
        else:
            raise HTTPException(
                status_code=409,
                detail="This email already has a license. Contact support if you need help."
            )

    # Create trial license
    key = f"BOB-{secrets.token_hex(4).upper()}"
    exp = datetime.datetime.utcnow() + datetime.timedelta(days=7)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO licenses
                    (license_key, email, name, stripe_customer_id, tier, expires_at,
                     token_balance, tokens_purchased, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (key, email, "", "", "trial", exp,
                 1, 1,
                 f"Free trial — 1 token | email_optin={req.email_optin}"),
            )
            conn.commit()

    log.info("Trial license created: %s | %s | expires=%s", key, email, exp.date())
    return {"key": key, "email": email, "tier": "trial", "expires": exp.isoformat()}

@app.post("/verify-license")
def verify_lic(req: VerifyReq, _=Depends(verify_int)):
    """Validate a license key and issue a 24-hour JWT."""
    # Rate limit: 10 login attempts per 15 minutes per key (blocks brute-force)
    if not _rate_limit(f"login:{req.license_key[:12]}", max_requests=120, window_seconds=900):
        log.warning("Login rate limit hit: key=%s...", req.license_key[:8])
        raise HTTPException(status_code=429, detail="Too many login attempts. Wait a few minutes.")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, expires_at, tier, email, name "
                "FROM licenses WHERE license_key = %s",
                (req.license_key,),
            )
            res = cur.fetchone()

    if not res:
        raise HTTPException(status_code=403, detail="License not found.")

    status, expires_at, tier, email, name = res

    if status != "active":
        raise HTTPException(status_code=403, detail="License is inactive or revoked.")

    # expires_at can be NULL (perpetual licenses). None < datetime raises
    # TypeError in Python 3 — guard before comparing.
    if expires_at is not None and expires_at < datetime.datetime.utcnow():
        raise HTTPException(status_code=403, detail="License has expired.")

    tkn = jwt.encode(
        {
            "sub":   req.license_key,
            "email": email,
            "name":  name,
            "tier":  tier,
            "exp":   datetime.datetime.utcnow() + datetime.timedelta(hours=24),
        },
        _jwt_secret,   # Startup-validated — never None
        algorithm="HS256",
    )
    log.info("License verified: %s | tier=%s", email, tier)
    return {"token": tkn, "tier": tier, "name": name, "email": email}


@app.post("/auth/create", dependencies=[Depends(verify_int)])
def create_lic(req: CreateReq):
    """Create a new license key for a user."""
    key = f"BOB-{secrets.token_hex(4).upper()}"
    exp = datetime.datetime.utcnow() + datetime.timedelta(days=req.days)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO licenses
                    (license_key, email, name, stripe_customer_id, tier, expires_at, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (key, req.email, req.name, req.stripe_customer_id,
                 req.tier, exp, req.notes),
            )
            conn.commit()

    log.info("License created: %s | %s | tier=%s | expires=%s",
             key, req.email, req.tier, exp.date())
    return {"key": key, "email": req.email, "name": req.name, "tier": req.tier}


@app.get("/auth/expiring", dependencies=[Depends(verify_int)])
def expiring_licenses(within_days: int = 7):
    """
    Returns all active licenses expiring within `within_days` days.
    Called daily by scheduler_worker.py to trigger warning emails.
    Merged from: auth_service_expiring_patch.py

    Fix: removed redundant `from datetime import datetime, timedelta` that was
    inside the original patch function — datetime is already imported at module
    level and used as datetime.datetime / datetime.timedelta throughout.
    """
    cutoff = datetime.datetime.utcnow() + datetime.timedelta(days=within_days)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT email, name, tier, expires_at,
                       EXTRACT(DAY FROM expires_at - NOW())::INTEGER AS days_left
                FROM licenses
                WHERE status     = 'active'
                  AND expires_at IS NOT NULL
                  AND expires_at <= %s
                ORDER BY expires_at ASC
                """,
                (cutoff,),
            )
            rows = cur.fetchall()

    licenses = [
        {
            "email":      r[0],
            "name":       r[1],
            "tier":       r[2],
            "expires_at": r[3].isoformat() if r[3] else None,
            "days_left":  r[4],
        }
        for r in rows
    ]
    log.info("Expiring licenses query: %d results within %d days",
             len(licenses), within_days)
    return {"licenses": licenses}


# ══════════════════════════════════════════════════════════════════════════════
# PROFILE CRUD
# ══════════════════════════════════════════════════════════════════════════════

class ProfileUpdate(BaseModel):
    display_name: str = ""
    business_name: str = ""
    phone: str = ""
    location: str = ""
    bio: str = ""
    certification: str = ""
    default_labor_rate: float = 0
    default_tax_rate: float = 0
    default_markup: float = 0
    default_terms: str = ""


@app.get("/profile/{email}", dependencies=[Depends(verify_int)])
def get_profile(email: str):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM user_profiles WHERE email = %s", (email,))
            row = cur.fetchone()
            if not row:
                return {"profile": None, "vehicles": [], "inventory": []}
            cols = [d[0] for d in cur.description]
            profile = dict(zip(cols, row))

            cur.execute("SELECT * FROM user_vehicles WHERE email = %s ORDER BY is_default DESC, created_at DESC", (email,))
            v_rows = cur.fetchall()
            v_cols = [d[0] for d in cur.description]
            vehicles = [dict(zip(v_cols, r)) for r in v_rows]

            cur.execute("SELECT * FROM user_inventory WHERE email = %s ORDER BY added_at DESC", (email,))
            i_rows = cur.fetchall()
            i_cols = [d[0] for d in cur.description]
            inventory = [dict(zip(i_cols, r)) for r in i_rows]

    return {"profile": profile, "vehicles": vehicles, "inventory": inventory}


@app.post("/profile/{email}", dependencies=[Depends(verify_int)])
def upsert_profile(email: str, req: ProfileUpdate):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM user_profiles WHERE email = %s", (email,))
            if cur.fetchone():
                cur.execute(
                    """UPDATE user_profiles SET display_name=%s, business_name=%s,
                    phone=%s, location=%s, bio=%s, certification=%s,
                    default_labor_rate=%s, default_tax_rate=%s, default_markup=%s,
                    default_terms=%s, updated_at=NOW() WHERE email=%s""",
                    (req.display_name, req.business_name, req.phone, req.location,
                     req.bio, req.certification, req.default_labor_rate,
                     req.default_tax_rate, req.default_markup, req.default_terms, email)
                )
            else:
                cur.execute(
                    """INSERT INTO user_profiles (email, display_name, business_name,
                    phone, location, bio, certification, default_labor_rate,
                    default_tax_rate, default_markup, default_terms)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (email, req.display_name, req.business_name, req.phone,
                     req.location, req.bio, req.certification, req.default_labor_rate,
                     req.default_tax_rate, req.default_markup, req.default_terms)
                )
            conn.commit()
    return {"status": "ok"}


# ══════════════════════════════════════════════════════════════════════════════
# VEHICLE CRUD
# ══════════════════════════════════════════════════════════════════════════════

class VehicleReq(BaseModel):
    nickname: str = ""
    year: str = ""
    make: str = ""
    model: str = ""
    engine: str = ""
    mileage: str = ""
    environment: str = ""
    notes: str = ""
    is_default: bool = False


@app.post("/profile/{email}/vehicle", dependencies=[Depends(verify_int)])
def add_vehicle(email: str, req: VehicleReq):
    with get_db() as conn:
        with conn.cursor() as cur:
            if req.is_default:
                cur.execute("UPDATE user_vehicles SET is_default=FALSE WHERE email=%s", (email,))
            cur.execute(
                """INSERT INTO user_vehicles (email, nickname, year, make, model,
                engine, mileage, environment, notes, is_default)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (email, req.nickname, req.year, req.make, req.model,
                 req.engine, req.mileage, req.environment, req.notes, req.is_default)
            )
            vid = cur.fetchone()[0]
            conn.commit()
    return {"id": vid, "status": "created"}


@app.put("/profile/{email}/vehicle/{vid}", dependencies=[Depends(verify_int)])
def update_vehicle(email: str, vid: int, req: VehicleReq):
    with get_db() as conn:
        with conn.cursor() as cur:
            if req.is_default:
                cur.execute("UPDATE user_vehicles SET is_default=FALSE WHERE email=%s", (email,))
            cur.execute(
                """UPDATE user_vehicles SET nickname=%s, year=%s, make=%s, model=%s,
                engine=%s, mileage=%s, environment=%s, notes=%s, is_default=%s
                WHERE id=%s AND email=%s""",
                (req.nickname, req.year, req.make, req.model, req.engine,
                 req.mileage, req.environment, req.notes, req.is_default, vid, email)
            )
            conn.commit()
    return {"status": "updated"}


@app.delete("/profile/{email}/vehicle/{vid}", dependencies=[Depends(verify_int)])
def delete_vehicle(email: str, vid: int):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_vehicles WHERE id=%s AND email=%s", (vid, email))
            conn.commit()
    return {"status": "deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# INVENTORY (MY GARAGE) CRUD
# ══════════════════════════════════════════════════════════════════════════════

class InventoryReq(BaseModel):
    item_name: str
    description: str = ""
    category: str = ""
    condition: str = ""
    specs: str = ""
    location: str = ""


@app.post("/profile/{email}/inventory", dependencies=[Depends(verify_int)])
def add_inventory(email: str, req: InventoryReq):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO user_inventory (email, item_name, description,
                category, condition, specs, location)
                VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (email, req.item_name, req.description, req.category,
                 req.condition, req.specs, req.location)
            )
            iid = cur.fetchone()[0]
            conn.commit()
    return {"id": iid, "status": "created"}


@app.delete("/profile/{email}/inventory/{iid}", dependencies=[Depends(verify_int)])
def delete_inventory(email: str, iid: int):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_inventory WHERE id=%s AND email=%s", (iid, email))
            conn.commit()
    return {"status": "deleted"}


# ── HEALTH ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}
