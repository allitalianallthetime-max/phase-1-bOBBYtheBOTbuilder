import os, secrets, json, logging
import psycopg2.pool, stripe, httpx
from contextlib import contextmanager
from fastapi import FastAPI, Header, Request, Depends, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("billing_service")

app = FastAPI()

# ── STARTUP GUARDS ──
_db_url = os.getenv("DATABASE_URL")
if not _db_url:
    raise RuntimeError("DATABASE_URL is not set.")

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
_webhook_secret  = os.getenv("STRIPE_WEBHOOK_SEC", "")
_auth_url        = os.getenv("AUTH_SERVICE_URL", "http://builder-auth:10000")
_internal_key    = os.getenv("INTERNAL_API_KEY", "")

pool = psycopg2.pool.ThreadedConnectionPool(2, 10, _db_url)


# ── DB CONTEXT MANAGER ──
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


# ── DB INIT ──
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
            conn.commit()

init_db()


# ── AUTH ──
def verify(x_internal_key: str = Header(None)):
    if not secrets.compare_digest(x_internal_key or "", _internal_key):
        raise HTTPException(status_code=403, detail="Invalid internal key.")


# ── TIER MAPPING ──
# Set STRIPE_PRICE_PRO and STRIPE_PRICE_MASTER in Render env vars
# to match your actual Stripe Price IDs.
PRICE_TO_TIER = {
    os.getenv("STRIPE_PRICE_STARTER", "price_starter"): ("starter", 25,  30),
    os.getenv("STRIPE_PRICE_PRO",     "price_pro"):     ("pro",     100, 30),
    os.getenv("STRIPE_PRICE_MASTER",  "price_master"):  ("master",  999, 365),
}


def _tier_for_price(price_id: str) -> tuple:
    """Returns (tier_name, build_limit, days_valid) for a Stripe price ID."""
    return PRICE_TO_TIER.get(price_id, ("starter", 25, 30))


# ── INTERNAL: CREATE LICENSE VIA AUTH SERVICE ──
async def _create_license(email: str, name: str, stripe_customer_id: str, tier: str, days: int) -> dict:
    """Calls auth_service to issue a new license key after successful payment."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{_auth_url}/auth/create",
            json={
                "email": email,
                "name": name,
                "stripe_customer_id": stripe_customer_id,
                "tier": tier,
                "days": days,
                "notes": f"Auto-created by billing_service via Stripe",
            },
            headers={"x-internal-key": _internal_key},
        )
        resp.raise_for_status()
        return resp.json()


async def _revoke_license(stripe_customer_id: str):
    """Marks all licenses for a customer as revoked on subscription cancellation."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE licenses SET status = 'revoked' WHERE stripe_customer_id = %s",
                (stripe_customer_id,)
            )
            conn.commit()
    log.info("Revoked licenses for customer: %s", stripe_customer_id)


async def _reactivate_license(stripe_customer_id: str):
    """Reactivates licenses after a failed payment is recovered."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE licenses SET status = 'active' WHERE stripe_customer_id = %s",
                (stripe_customer_id,)
            )
            conn.commit()
    log.info("Reactivated licenses for customer: %s", stripe_customer_id)


# ── STRIPE WEBHOOK ──
@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    """
    Receives all Stripe events. Verified via webhook signature.
    Handles: checkout.session.completed, customer.subscription.deleted,
             invoice.payment_failed, invoice.payment_succeeded
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    # Verify the webhook signature — reject anything not from Stripe
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, _webhook_secret)
    except stripe.error.SignatureVerificationError:
        log.warning("Invalid Stripe webhook signature — rejected.")
        raise HTTPException(status_code=400, detail="Invalid signature.")

    event_id   = event["id"]
    event_type = event["type"]
    data_obj   = event["data"]["object"]

    # Idempotency: skip already-processed events
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO stripe_events (stripe_id, event_type, customer_id, payload) "
                "VALUES (%s, %s, %s, %s) ON CONFLICT (stripe_id) DO NOTHING RETURNING id",
                (event_id, event_type, data_obj.get("customer"), json.dumps(event))
            )
            if not cur.fetchone():
                log.info("Duplicate Stripe event %s — skipped.", event_id)
                return {"status": "duplicate"}
            conn.commit()

    log.info("Processing Stripe event: %s (%s)", event_type, event_id)

    # ── EVENT HANDLERS ──

    if event_type == "checkout.session.completed":
        # New purchase: create a license automatically
        # Use "or" to convert any None values to empty strings
        customer_id = data_obj.get("customer") or ""
        customer_details = data_obj.get("customer_details") or {}
        email       = customer_details.get("email") or ""
        name        = customer_details.get("name") or ""
        price_id    = ""

        # Pull price ID from line items if available
        raw_line_items = data_obj.get("line_items") or {}
        if isinstance(raw_line_items, dict):
            line_items = raw_line_items.get("data", [])
        else:
            line_items = []
        if line_items:
            price_obj = line_items[0].get("price") or {}
            price_id = price_obj.get("id") or ""

        tier, _, days = _tier_for_price(price_id)

        log.info("Checkout data: email=%s, name=%s, customer=%s, price=%s, tier=%s",
                 email, name, customer_id, price_id, tier)

        try:
            result = await _create_license(email, name, customer_id, tier, days)
            log.info("License created: %s -> %s (%s)", email, result.get("key"), tier)

            # Mark event processed
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE stripe_events SET processed = TRUE WHERE stripe_id = %s",
                        (event_id,)
                    )
                    conn.commit()
        except Exception as e:
            log.error("Failed to create license for %s: %s", email, e)

    elif event_type == "customer.subscription.deleted":
        # Subscription cancelled — revoke access
        customer_id = data_obj.get("customer")
        await _revoke_license(customer_id)

    elif event_type == "invoice.payment_failed":
        # Payment failed — revoke until resolved
        customer_id = data_obj.get("customer")
        log.warning("Payment failed for customer %s — revoking licenses.", customer_id)
        await _revoke_license(customer_id)

    elif event_type == "invoice.payment_succeeded":
        # Payment recovered — reactivate
        customer_id = data_obj.get("customer")
        await _reactivate_license(customer_id)

    else:
        log.info("Unhandled Stripe event type: %s", event_type)

    return {"status": "ok"}


# ── INTERNAL: MANUAL LICENSE CREATION ──
class ManualLicenseReq(BaseModel):
    email: str
    name: str = ""
    tier: str = "pro"
    days: int = 30
    stripe_customer_id: str = ""
    notes: str = ""

@app.post("/billing/create-license", dependencies=[Depends(verify)])
async def manual_create(req: ManualLicenseReq):
    """Admin endpoint to manually issue a license outside of Stripe."""
    result = await _create_license(
        req.email, req.name, req.stripe_customer_id, req.tier, req.days
    )
    return result


# ── INTERNAL: QUOTA CHECK ──
@app.get("/billing/quota/{email}", dependencies=[Depends(verify)])
def check_quota(email: str):
    """Returns current build count and limit for a user."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tier, build_count, expires_at, status FROM licenses "
                "WHERE email = %s AND status = 'active' ORDER BY created_at DESC LIMIT 1",
                (email,)
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="No active license found.")

    tier, build_count, expires_at, status = row
    _, limit, _ = _tier_for_price("")  # fallback
    # Look up correct limit by tier name
    for price_id, (t, lim, _) in PRICE_TO_TIER.items():
        if t == tier:
            limit = lim
            break

    return {
        "email":       email,
        "tier":        tier,
        "build_count": build_count,
        "build_limit": limit,
        "remaining":   max(0, limit - build_count),
        "expires_at":  expires_at.isoformat() if expires_at else None,
        "status":      status,
    }


# ── HEALTH ──
@app.get("/health")
def health():
    return {"status": "ok"}
