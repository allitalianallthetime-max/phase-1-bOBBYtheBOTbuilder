"""
BILLING SERVICE — TOKEN SYSTEM
================================
Handles Stripe webhooks for:
  - Token pack purchases (one-time checkout → add tokens)
  - Subscription creation (checkout → set sub_tier + add monthly tokens)
  - Subscription renewal (invoice.paid → add monthly tokens)
  - Subscription cancellation (keep tokens, stop refill)

Also provides:
  - GET /billing/tokens/{email} — current balance and sub info
  - GET /billing/quota/{email} — backward-compatible quota endpoint
"""

import os
import secrets
import json
import logging

import psycopg2.pool
import stripe
import httpx
from contextlib import contextmanager
from fastapi import FastAPI, Header, Request, Depends, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("billing_service")

app = FastAPI()

# ── CONFIG ────────────────────────────────────────────────────────────────────
_db_url = os.getenv("DATABASE_URL")
if not _db_url:
    raise RuntimeError("DATABASE_URL is not set.")

stripe.api_key   = os.getenv("STRIPE_SECRET_KEY")
_webhook_secret  = os.getenv("STRIPE_WEBHOOK_SEC", "")
_auth_url        = os.getenv("AUTH_SERVICE_URL", "http://builder-auth:10000")
_internal_key    = os.getenv("INTERNAL_API_KEY", "")

pool = psycopg2.pool.ThreadedConnectionPool(2, 10, _db_url)


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


# ── DB INIT ───────────────────────────────────────────────────────────────────
def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS stripe_events (
                    id          SERIAL PRIMARY KEY,
                    stripe_id   TEXT UNIQUE,
                    event_type  TEXT,
                    customer_id TEXT,
                    payload     JSONB,
                    processed   BOOLEAN   DEFAULT FALSE,
                    created_at  TIMESTAMP DEFAULT NOW()
                )
            """)
            # Ensure token columns exist
            for col, defn in [
                ("token_balance",     "INTEGER DEFAULT 0"),
                ("tokens_purchased",  "INTEGER DEFAULT 0"),
                ("tokens_used",       "INTEGER DEFAULT 0"),
                ("sub_tier",          "VARCHAR(20) DEFAULT NULL"),
                ("sub_tokens_monthly","INTEGER DEFAULT 0"),
                ("sub_next_refill",   "TIMESTAMP DEFAULT NULL"),
            ]:
                cur.execute(f"""
                    DO $$ BEGIN
                        ALTER TABLE licenses ADD COLUMN {col} {defn};
                    EXCEPTION WHEN duplicate_column THEN NULL;
                    END $$;
                """)
            conn.commit()

init_db()


# ── AUTH ──────────────────────────────────────────────────────────────────────
def verify(x_internal_key: str = Header(None)):
    if not secrets.compare_digest(x_internal_key or "", _internal_key):
        raise HTTPException(status_code=403, detail="Invalid internal key.")


# ── TOKEN PACK + SUBSCRIPTION MAPPING ─────────────────────────────────────────
# Map Stripe Price IDs to token amounts / subscription config
# Set these env vars in Render to match your actual Stripe Price IDs

TOKEN_PACKS = {
    os.getenv("STRIPE_PRICE_SPARK",     "price_spark"):     3,
    os.getenv("STRIPE_PRICE_BUILDER",   "price_builder"):   10,
    os.getenv("STRIPE_PRICE_FOUNDRY",   "price_foundry"):   30,
    os.getenv("STRIPE_PRICE_SHOPPASS",  "price_shoppass"):   100,
}

SUB_TIERS = {
    os.getenv("STRIPE_PRICE_PRO_SUB",    "price_pro_sub"):    ("pro",    20),
    os.getenv("STRIPE_PRICE_MASTER_SUB", "price_master_sub"): ("master", 60),
}

# Legacy tier mapping for backward compatibility
LEGACY_TIERS = {
    os.getenv("STRIPE_PRICE_STARTER", "price_starter"): ("starter", 25, 30),
    os.getenv("STRIPE_PRICE_PRO",     "price_pro"):     ("pro",    100, 30),
    os.getenv("STRIPE_PRICE_MASTER",  "price_master"):  ("master", 999, 365),
}


# ── INTERNAL: CREATE LICENSE VIA AUTH SERVICE ─────────────────────────────────
async def _create_license(email: str, name: str, stripe_customer_id: str,
                          tier: str, days: int) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{_auth_url}/auth/create",
            json={
                "email": email, "name": name,
                "stripe_customer_id": stripe_customer_id,
                "tier": tier, "days": days,
                "notes": "Auto-created by billing_service via Stripe",
            },
            headers={"x-internal-key": _internal_key},
        )
        resp.raise_for_status()
        return resp.json()


def _add_tokens(email: str, amount: int, reason: str):
    """Add tokens to a user's balance."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE licenses SET token_balance = token_balance + %s, "
                "tokens_purchased = tokens_purchased + %s "
                "WHERE email = %s AND status = 'active'",
                (amount, amount, email)
            )
            if cur.rowcount == 0:
                log.warning("No active license found for %s — tokens not added", email)
            else:
                log.info("Added %d tokens to %s (%s)", amount, email, reason)
            conn.commit()


def _setup_subscription(email: str, tier: str, monthly_tokens: int):
    """Configure subscription tier and add first month's tokens."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE licenses SET sub_tier = %s, sub_tokens_monthly = %s, "
                "token_balance = token_balance + %s, tokens_purchased = tokens_purchased + %s, "
                "tier = %s "
                "WHERE email = %s AND status = 'active'",
                (tier, monthly_tokens, monthly_tokens, monthly_tokens, tier, email)
            )
            if cur.rowcount == 0:
                log.warning("No active license for %s — sub not set up", email)
            else:
                log.info("Subscription %s set up for %s (+%d tokens)", tier, email, monthly_tokens)
            conn.commit()


def _cancel_subscription(stripe_customer_id: str):
    """Cancel subscription but keep existing token balance."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE licenses SET sub_tier = NULL, sub_tokens_monthly = 0, "
                "sub_next_refill = NULL "
                "WHERE stripe_customer_id = %s AND status = 'active'",
                (stripe_customer_id,)
            )
            conn.commit()
    log.info("Subscription cancelled for customer %s (tokens preserved)", stripe_customer_id)


def _refill_subscription(email: str):
    """Add monthly token refill for active subscriber."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT sub_tier, sub_tokens_monthly FROM licenses "
                "WHERE email = %s AND status = 'active' AND sub_tier IS NOT NULL "
                "ORDER BY created_at DESC LIMIT 1",
                (email,)
            )
            row = cur.fetchone()
            if not row:
                log.warning("No active subscription for %s — refill skipped", email)
                return
            tier, monthly = row
            cur.execute(
                "UPDATE licenses SET token_balance = token_balance + %s, "
                "tokens_purchased = tokens_purchased + %s "
                "WHERE email = %s AND status = 'active'",
                (monthly, monthly, email)
            )
            conn.commit()
    log.info("Subscription refill: +%d tokens for %s (%s)", monthly, email, tier)


# ── STRIPE WEBHOOK ────────────────────────────────────────────────────────────
@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, _webhook_secret)
    except stripe.error.SignatureVerificationError:
        log.warning("Invalid Stripe webhook signature — rejected.")
        raise HTTPException(status_code=400, detail="Invalid signature.")

    event_id   = event["id"]
    event_type = event["type"]
    data_obj   = event["data"]["object"]

    # Idempotency
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO stripe_events (stripe_id, event_type, customer_id, payload) "
                "VALUES (%s, %s, %s, %s) ON CONFLICT (stripe_id) DO NOTHING RETURNING id",
                (event_id, event_type, data_obj.get("customer"), json.dumps(event))
            )
            if not cur.fetchone():
                return {"status": "duplicate"}
            conn.commit()

    log.info("Processing Stripe event: %s (%s)", event_type, event_id)

    if event_type == "checkout.session.completed":
        customer_id = data_obj.get("customer", "")
        email       = data_obj.get("customer_details", {}).get("email", "")
        name        = data_obj.get("customer_details", {}).get("name", "")
        mode        = data_obj.get("mode", "")  # "payment" or "subscription"

        # Get price ID from line items
        price_id = ""
        line_items = data_obj.get("line_items", {}).get("data", [])
        if line_items:
            price_id = line_items[0].get("price", {}).get("id", "")

        if mode == "payment" and price_id in TOKEN_PACKS:
            # Token pack purchase
            tokens = TOKEN_PACKS[price_id]
            # Ensure user has a license (create one if new)
            try:
                await _create_license(email, name, customer_id, "token", 3650)
            except Exception:
                pass  # License might already exist — that's fine
            _add_tokens(email, tokens, f"pack purchase ({tokens} tokens)")

        elif mode == "subscription" and price_id in SUB_TIERS:
            # Subscription purchase
            tier, monthly = SUB_TIERS[price_id]
            try:
                await _create_license(email, name, customer_id, tier, 3650)
            except Exception:
                pass
            _setup_subscription(email, tier, monthly)

        elif price_id in LEGACY_TIERS:
            # Legacy tier purchase (backward compatible)
            tier, _, days = LEGACY_TIERS[price_id]
            try:
                result = await _create_license(email, name, customer_id, tier, days)
                log.info("Legacy license created: %s → %s", email, tier)
            except Exception as e:
                log.error("Failed to create legacy license for %s: %s", email, e)
        else:
            log.info("Unknown price_id %s in checkout — no action taken", price_id)

        # Mark processed
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE stripe_events SET processed = TRUE WHERE stripe_id = %s",
                    (event_id,)
                )
                conn.commit()

    elif event_type == "invoice.payment_succeeded":
        # Subscription renewal — add monthly tokens
        customer_id = data_obj.get("customer", "")
        email       = data_obj.get("customer_email", "")

        # Only refill on renewals, not initial payment (which is handled by checkout)
        billing_reason = data_obj.get("billing_reason", "")
        if billing_reason in ("subscription_cycle", "subscription_update"):
            if email:
                _refill_subscription(email)
            else:
                log.warning("invoice.payment_succeeded but no email for customer %s", customer_id)

    elif event_type == "customer.subscription.deleted":
        customer_id = data_obj.get("customer", "")
        _cancel_subscription(customer_id)

    elif event_type == "invoice.payment_failed":
        customer_id = data_obj.get("customer", "")
        log.warning("Payment failed for customer %s", customer_id)
        # Don't revoke tokens — just log. They keep what they have.
        # Sub will eventually cancel via customer.subscription.deleted

    else:
        log.info("Unhandled Stripe event type: %s", event_type)

    return {"status": "ok"}


# ── TOKEN BALANCE ENDPOINT ────────────────────────────────────────────────────
@app.get("/billing/tokens/{email}", dependencies=[Depends(verify)])
def get_tokens(email: str):
    """Returns current token balance and subscription info."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT token_balance, tokens_purchased, tokens_used, "
                "sub_tier, sub_tokens_monthly, tier, status "
                "FROM licenses WHERE email = %s AND status = 'active' "
                "ORDER BY created_at DESC LIMIT 1",
                (email,)
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="No active license found.")

    balance, purchased, used, sub_tier, sub_monthly, tier, status = row
    return {
        "email":            email,
        "token_balance":    balance,
        "tokens_purchased": purchased,
        "tokens_used":      used,
        "sub_tier":         sub_tier,
        "sub_tokens_monthly": sub_monthly,
        "tier":             tier,
        "status":           status,
    }


# ── BACKWARD-COMPATIBLE QUOTA ENDPOINT ────────────────────────────────────────
@app.get("/billing/quota/{email}", dependencies=[Depends(verify)])
def check_quota(email: str):
    """Backward-compatible quota check. Maps tokens to build count/limit."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tier, token_balance, tokens_used, expires_at, status, sub_tier "
                "FROM licenses WHERE email = %s AND status = 'active' "
                "ORDER BY created_at DESC LIMIT 1",
                (email,)
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="No active license found.")

    tier, balance, used, expires_at, status, sub_tier = row
    return {
        "email":       email,
        "tier":        sub_tier or tier,
        "build_count": used,
        "build_limit": balance + used,  # total ever = used + remaining
        "remaining":   balance,
        "token_balance": balance,
        "expires_at":  expires_at.isoformat() if expires_at else None,
        "status":      status,
    }


# ── MANUAL LICENSE CREATION ───────────────────────────────────────────────────
class ManualLicenseReq(BaseModel):
    email: str
    name: str = ""
    tier: str = "token"
    days: int = 3650
    stripe_customer_id: str = ""
    notes: str = ""
    tokens: int = 0

@app.post("/billing/create-license", dependencies=[Depends(verify)])
async def manual_create(req: ManualLicenseReq):
    result = await _create_license(
        req.email, req.name, req.stripe_customer_id, req.tier, req.days
    )
    if req.tokens > 0:
        _add_tokens(req.email, req.tokens, f"manual grant ({req.tokens})")
    return result


# ── HEALTH ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}
