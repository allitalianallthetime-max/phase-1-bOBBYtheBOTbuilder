# ── ADD THIS ENDPOINT TO auth_service.py ──
# Paste this block before the health check at the bottom of auth_service.py

@app.get("/auth/expiring", dependencies=[Depends(verify_int)])
def expiring_licenses(within_days: int = 7):
    """
    Returns all active licenses expiring within `within_days` days.
    Called daily by scheduler_worker.py to send warning emails.
    """
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() + timedelta(days=within_days)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT email, name, tier, expires_at,
                       EXTRACT(DAY FROM expires_at - NOW())::INTEGER AS days_left
                FROM licenses
                WHERE status = 'active'
                  AND expires_at IS NOT NULL
                  AND expires_at <= %s
                ORDER BY expires_at ASC
                """,
                (cutoff,)
            )
            rows = cur.fetchall()

    return {
        "licenses": [
            {
                "email":      r[0],
                "name":       r[1],
                "tier":       r[2],
                "expires_at": r[3].isoformat() if r[3] else None,
                "days_left":  r[4],
            }
            for r in rows
        ]
    }
