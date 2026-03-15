"""
AUTH SERVICE
============
Handles license verification, JWT issuance, license creation,
email delivery of license keys, and expiring-license queries.

Merged from: auth_service.py + auth_service_expiring_patch.py
Email delivery added: sends license key to customer via Gmail SMTP.
"""

import os
import secrets
import datetime
import json
import logging
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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
    raise RuntimeError("JWT_SECRET is not set. Cannot issue secure tokens.")

_int_key = os.getenv("INTERNAL_API_KEY", "")

# Email config (optional — if not set, license key only appears in logs)
_gmail_address = os.getenv("GMAIL_ADDRESS", "")
_gmail_app_pw  = os.getenv("GMAIL_APP_PW", "")

pool = psycopg2.pool.ThreadedConnectionPool(2, 15, _db_url)


# ── DB CONTEXT MANAGER ─────────────────────────────────────────────────────────

@contextmanager
def get_db():
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
            conn.commit()
    log.info("DB initialized.")


init_db()


# ── EMAIL DELIVERY ─────────────────────────────────────────────────────────────

def _send_license_email(to_email: str, name: str, license_key: str, tier: str):
    """
    Sends the license key to the customer via Gmail SMTP.
    Runs in a background thread so it never blocks the API response.
    If Gmail is not configured, just logs a warning and skips.
    """
    if not _gmail_address or not _gmail_app_pw:
        log.warning("Gmail not configured — license key NOT emailed to %s. "
                     "Key: %s (deliver manually or set GMAIL_ADDRESS + GMAIL_APP_PW)",
                     to_email, license_key)
        return

    def _send():
        try:
            msg = MIMEMultipart("alternative")
            msg["From"]    = _gmail_address
            msg["To"]      = to_email
            msg["Subject"] = f"Your Builder Foundry License Key — {tier.upper()} Access"

            text_body = (
                f"Welcome to The Builder Foundry, {name or 'Operator'}!\n\n"
                f"Your license key:\n\n"
                f"    {license_key}\n\n"
                f"Tier: {tier.upper()}\n\n"
                f"How to get started:\n"
                f"1. Go to your Builder Foundry app\n"
                f"2. Paste the license key into the login box\n"
                f"3. Click AUTHORIZE\n"
                f"4. Start forging blueprints!\n\n"
                f"Keep this key safe. It is your access to the Foundry.\n\n"
                f"— AoC3P0 Systems | The Builder Foundry"
            )

            html_body = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;
                        background: #0F172A; color: #E2E8F0; padding: 32px; border-radius: 8px;">
                <div style="text-align: center; margin-bottom: 24px;">
                    <span style="font-size: 36px;">&#9881;&#65039;</span>
                    <h1 style="color: #FF4500; margin: 8px 0 4px;">THE BUILDER FOUNDRY</h1>
                    <p style="color: #94A3B8; font-size: 14px;">Your License is Ready</p>
                </div>
                <p>Welcome, <strong>{name or 'Operator'}</strong>!</p>
                <p>Your <span style="color: #FF4500; font-weight: bold;">{tier.upper()}</span> license key:</p>
                <div style="background: #1E293B; border: 2px solid #FF4500; border-radius: 8px;
                            padding: 20px; text-align: center; margin: 20px 0;">
                    <span style="font-size: 28px; font-weight: bold; color: #FF4500;
                                 letter-spacing: 3px; font-family: monospace;">{license_key}</span>
                </div>
                <p><strong>How to get started:</strong></p>
                <ol style="color: #94A3B8;">
                    <li>Go to your Builder Foundry app</li>
                    <li>Paste the license key into the login box</li>
                    <li>Click <strong style="color: #FF4500;">AUTHORIZE</strong></li>
                    <li>Start forging blueprints!</li>
                </ol>
                <p style="color: #64748B; font-size: 12px; margin-top: 24px; text-align: center;">
                    Keep this key safe. It is your access to the Foundry.<br>
                    AoC3P0 Systems | The Builder Foundry
                </p>
            </div>
            """

            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(_gmail_address, _gmail_app_pw)
                server.sendmail(_gmail_address, to_email, msg.as_string())

            log.info("License key emailed to %s", to_email)

        except Exception as e:
            log.error("Failed to email license to %s: %s", to_email, e)

    # Fire and forget — don't block the API
    threading.Thread(target=_send, daemon=True).start()


# ── INTERNAL AUTH ──────────────────────────────────────────────────────────────

def verify_int(x_internal_key: str = Header(None)):
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


# ── ENDPOINTS ──────────────────────────────────────────────────────────────────

@app.post("/verify-license")
def verify_lic(req: VerifyReq, _=Depends(verify_int)):
    """Validate a license key and issue a 24-hour JWT."""
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
        _jwt_secret,
        algorithm="HS256",
    )
    log.info("License verified: %s | tier=%s", email, tier)
    return {"token": tkn, "tier": tier, "name": name, "email": email}


@app.post("/auth/create", dependencies=[Depends(verify_int)])
def create_lic(req: CreateReq):
    """Create a new license key for a user and email it to them."""
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

    # Email the license key to the customer (non-blocking)
    if req.email:
        _send_license_email(req.email, req.name, key, req.tier)

    return {"key": key, "email": req.email, "name": req.name, "tier": req.tier}


@app.get("/auth/expiring", dependencies=[Depends(verify_int)])
def expiring_licenses(within_days: int = 7):
    """Returns all active licenses expiring within `within_days` days."""
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


# ── HEALTH ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}
