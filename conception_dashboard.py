"""
CONCEPTION ADMIN DASHBOARD
=============================
One page to see everything. No hopping between Render, Stripe, and Reddit.

Endpoints:
  GET /dashboard/data   — JSON blob of all metrics (for API consumers)
  GET /dashboard        — Full HTML dashboard (open in browser)

Pulls from the same PostgreSQL database as all other services:
  - licenses table  → signups, trials, paid users, tiers
  - builds table    → total forges, tokens used, projects
  - marketing_posts → posts drafted, posted, engagement
"""

import os
import json
import logging
from datetime import datetime, timedelta
from contextlib import contextmanager

import psycopg2.pool
from fastapi import APIRouter, Header, Depends, HTTPException
from fastapi.responses import HTMLResponse

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("conception_dashboard")

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_pool = None


def set_pool(pool):
    global _pool
    _pool = pool


@contextmanager
def get_db():
    conn = _pool.getconn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


_int_key = os.getenv("INTERNAL_API_KEY", "")
_admin_pass = os.getenv("DASHBOARD_PASSWORD", "conception2026")


def _safe_query(cur, sql, params=None, default=None):
    """Run a query, return result or default if table doesn't exist."""
    try:
        cur.execute(sql, params)
        return cur.fetchall()
    except Exception:
        return default if default is not None else []


# ══════════════════════════════════════════════════════════════════════════════
# DATA ENDPOINT — Raw JSON
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/data")
def dashboard_data(password: str = ""):
    """All dashboard metrics as JSON."""
    if password != _admin_pass:
        raise HTTPException(status_code=403, detail="Invalid dashboard password.")

    data = {}

    with get_db() as conn:
        cur = conn.cursor()
        conn.autocommit = True  # Prevent transaction errors on missing tables

        # ── LICENSE METRICS ──
        rows = _safe_query(cur, "SELECT COUNT(*) FROM licenses")
        data["total_licenses"] = rows[0][0] if rows else 0

        rows = _safe_query(cur, "SELECT tier, COUNT(*) FROM licenses WHERE status='active' GROUP BY tier")
        data["licenses_by_tier"] = {r[0]: r[1] for r in rows} if rows else {}

        rows = _safe_query(cur, "SELECT COUNT(*) FROM licenses WHERE tier='trial' AND status='active'")
        data["trial_users"] = rows[0][0] if rows else 0

        rows = _safe_query(cur, "SELECT COUNT(*) FROM licenses WHERE tier != 'trial' AND status='active'")
        data["paid_users"] = rows[0][0] if rows else 0

        rows = _safe_query(cur,
            "SELECT COUNT(*) FROM licenses WHERE created_at >= NOW() - INTERVAL '24 hours'")
        data["signups_today"] = rows[0][0] if rows else 0

        rows = _safe_query(cur,
            "SELECT COUNT(*) FROM licenses WHERE created_at >= NOW() - INTERVAL '7 days'")
        data["signups_this_week"] = rows[0][0] if rows else 0

        # ── BUILD METRICS ──
        rows = _safe_query(cur, "SELECT COUNT(*) FROM builds")
        data["total_builds"] = rows[0][0] if rows else 0

        rows = _safe_query(cur,
            "SELECT COUNT(*) FROM builds WHERE created_at >= NOW() - INTERVAL '24 hours'")
        data["builds_today"] = rows[0][0] if rows else 0

        rows = _safe_query(cur,
            "SELECT COUNT(*) FROM builds WHERE created_at >= NOW() - INTERVAL '7 days'")
        data["builds_this_week"] = rows[0][0] if rows else 0

        rows = _safe_query(cur, "SELECT COALESCE(SUM(tokens_used), 0) FROM builds")
        data["total_tokens"] = rows[0][0] if rows else 0

        rows = _safe_query(cur,
            "SELECT project_type, COUNT(*) as cnt FROM builds GROUP BY project_type ORDER BY cnt DESC LIMIT 5")
        data["top_projects"] = [{"project": r[0], "count": r[1]} for r in rows] if rows else []

        # Recent builds
        rows = _safe_query(cur,
            "SELECT user_email, project_type, tokens_used, created_at "
            "FROM builds ORDER BY created_at DESC LIMIT 10")
        data["recent_builds"] = [
            {"email": r[0], "project": r[1], "tokens": r[2],
             "time": r[3].strftime("%Y-%m-%d %H:%M") if r[3] else ""}
            for r in rows
        ] if rows else []

        # ── MARKETING METRICS ──
        rows = _safe_query(cur,
            "SELECT COUNT(*) FROM marketing_posts WHERE status='posted'")
        data["total_posts"] = rows[0][0] if rows else 0

        rows = _safe_query(cur,
            "SELECT COUNT(*) FROM marketing_posts WHERE status='draft'")
        data["pending_drafts"] = rows[0][0] if rows else 0

        rows = _safe_query(cur,
            "SELECT COUNT(*) FROM marketing_posts WHERE status='posted' "
            "AND posted_at >= NOW() - INTERVAL '7 days'")
        data["posts_this_week"] = rows[0][0] if rows else 0

        rows = _safe_query(cur,
            "SELECT platform, COUNT(*) FROM marketing_posts WHERE status='posted' "
            "GROUP BY platform ORDER BY COUNT(*) DESC")
        data["posts_by_platform"] = {r[0]: r[1] for r in rows} if rows else {}

        # ── TRIAL CONVERSION ──
        rows = _safe_query(cur,
            "SELECT COUNT(*) FROM licenses WHERE tier='trial' AND build_count > 0")
        data["trials_used"] = rows[0][0] if rows else 0

        rows = _safe_query(cur,
            "SELECT notes FROM licenses WHERE tier='trial' AND notes LIKE '%email_optin=True%'")
        data["email_optins"] = len(rows) if rows else 0

        # ── EMAIL LIST ──
        rows = _safe_query(cur,
            "SELECT email, created_at FROM licenses WHERE tier='trial' "
            "AND notes LIKE '%email_optin=True%' ORDER BY created_at DESC LIMIT 50")
        data["mailing_list"] = [
            {"email": r[0], "signed_up": r[1].strftime("%Y-%m-%d") if r[1] else ""}
            for r in rows
        ] if rows else []

    data["generated_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return data


# ══════════════════════════════════════════════════════════════════════════════
# HTML DASHBOARD — Open in browser
# ══════════════════════════════════════════════════════════════════════════════

@router.get("", response_class=HTMLResponse)
def dashboard_html(password: str = ""):
    """Full HTML dashboard. Fetches data inline."""
    if password != _admin_pass:
        return HTMLResponse(content="""
        <html><body style="background:#0A0E17;color:#E2E8F0;font-family:system-ui;
        display:flex;align-items:center;justify-content:center;height:100vh;">
        <form method="get" style="text-align:center;">
          <h2 style="color:#FF4500;">Conception Dashboard</h2>
          <input name="password" type="password" placeholder="Dashboard password"
           style="padding:12px;border-radius:6px;border:1px solid #334155;
           background:#1E293B;color:white;font-size:16px;width:260px;" />
          <br><br>
          <button style="padding:12px 32px;background:#FF4500;color:white;border:none;
           border-radius:6px;font-size:16px;cursor:pointer;">ENTER</button>
        </form></body></html>
        """, status_code=200)

    # Fetch data
    data = dashboard_data(password=password)

    # Build HTML
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Conception Dashboard</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:#0A0E17; color:#E2E8F0; font-family:system-ui,-apple-system,sans-serif;
         padding:20px; max-width:1200px; margin:0 auto; }}
  h1 {{ color:#FF4500; font-size:24px; margin-bottom:4px; }}
  .subtitle {{ color:#64748B; font-size:13px; margin-bottom:24px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(160px, 1fr));
           gap:12px; margin-bottom:24px; }}
  .card {{ background:#1E293B; border-radius:8px; padding:16px; text-align:center; }}
  .card .number {{ font-size:32px; font-weight:bold; color:#FF4500; }}
  .card .label {{ font-size:11px; color:#94A3B8; letter-spacing:1px; margin-top:4px; }}
  .section {{ margin-bottom:24px; }}
  .section h2 {{ color:#E2E8F0; font-size:16px; border-bottom:1px solid #2A3A52;
                 padding-bottom:8px; margin-bottom:12px; }}
  table {{ width:100%; border-collapse:collapse; }}
  th {{ text-align:left; color:#94A3B8; font-size:11px; letter-spacing:1px;
       padding:8px; border-bottom:1px solid #2A3A52; }}
  td {{ padding:8px; font-size:13px; border-bottom:1px solid #1E293B; }}
  .tier {{ display:inline-block; padding:2px 8px; border-radius:4px; font-size:11px;
           font-weight:bold; }}
  .tier-trial {{ background:#10B981; color:white; }}
  .tier-starter {{ background:#94A3B8; color:white; }}
  .tier-pro {{ background:#FF4500; color:white; }}
  .tier-master {{ background:#FFD700; color:#000; }}
  .stat-row {{ display:flex; justify-content:space-between; padding:6px 0;
              border-bottom:1px solid #1E293B; font-size:13px; }}
  .stat-row .label {{ color:#94A3B8; }}
  .refresh {{ display:inline-block; margin-top:12px; padding:8px 20px; background:#FF4500;
              color:white; border-radius:6px; text-decoration:none; font-size:13px; }}
  .refresh:hover {{ background:#E03D00; }}
  @media (max-width:600px) {{
    .grid {{ grid-template-columns:repeat(2, 1fr); }}
  }}
</style>
</head>
<body>

<h1>CONCEPTION COMMAND CENTER</h1>
<div class="subtitle">Builder Foundry Intelligence Dashboard | {data.get('generated_at','')}</div>

<!-- KEY METRICS -->
<div class="grid">
  <div class="card">
    <div class="number">{data.get('total_licenses', 0)}</div>
    <div class="label">TOTAL SIGNUPS</div>
  </div>
  <div class="card">
    <div class="number">{data.get('trial_users', 0)}</div>
    <div class="label">TRIAL USERS</div>
  </div>
  <div class="card">
    <div class="number">{data.get('paid_users', 0)}</div>
    <div class="label">PAID USERS</div>
  </div>
  <div class="card">
    <div class="number">{data.get('total_builds', 0)}</div>
    <div class="label">TOTAL BUILDS</div>
  </div>
  <div class="card">
    <div class="number">{data.get('signups_today', 0)}</div>
    <div class="label">SIGNUPS TODAY</div>
  </div>
  <div class="card">
    <div class="number">{data.get('builds_today', 0)}</div>
    <div class="label">BUILDS TODAY</div>
  </div>
  <div class="card">
    <div class="number">{data.get('email_optins', 0)}</div>
    <div class="label">EMAIL OPTINS</div>
  </div>
  <div class="card">
    <div class="number">{data.get('total_tokens', 0):,}</div>
    <div class="label">TOKENS USED</div>
  </div>
</div>

<!-- TIER BREAKDOWN -->
<div class="section">
  <h2>LICENSES BY TIER</h2>
  {''.join(f'''
  <div class="stat-row">
    <span class="tier tier-{tier}">{tier.upper()}</span>
    <span>{count}</span>
  </div>''' for tier, count in data.get('licenses_by_tier', {}).items())}
</div>

<!-- TRIAL FUNNEL -->
<div class="section">
  <h2>TRIAL FUNNEL</h2>
  <div class="stat-row"><span class="label">Trial Signups</span><span>{data.get('trial_users', 0)}</span></div>
  <div class="stat-row"><span class="label">Trials That Built</span><span>{data.get('trials_used', 0)}</span></div>
  <div class="stat-row"><span class="label">Email Opt-ins</span><span>{data.get('email_optins', 0)}</span></div>
  <div class="stat-row"><span class="label">Paid Conversions</span><span>{data.get('paid_users', 0)}</span></div>
</div>

<!-- RECENT BUILDS -->
<div class="section">
  <h2>RECENT BUILDS</h2>
  <table>
    <tr><th>USER</th><th>PROJECT</th><th>TOKENS</th><th>TIME</th></tr>
    {''.join(f"""
    <tr>
      <td>{b['email'][:20]}...</td>
      <td>{b['project'][:30]}</td>
      <td>{b['tokens']:,}</td>
      <td>{b['time']}</td>
    </tr>""" for b in data.get('recent_builds', []))}
  </table>
</div>

<!-- TOP PROJECTS -->
<div class="section">
  <h2>TOP PROJECTS</h2>
  {''.join(f'''
  <div class="stat-row">
    <span>{p["project"][:40]}</span>
    <span>{p["count"]} builds</span>
  </div>''' for p in data.get('top_projects', []))}
</div>

<!-- MARKETING -->
<div class="section">
  <h2>MARKETING</h2>
  <div class="stat-row"><span class="label">Total Posts</span><span>{data.get('total_posts', 0)}</span></div>
  <div class="stat-row"><span class="label">Posts This Week</span><span>{data.get('posts_this_week', 0)}</span></div>
  <div class="stat-row"><span class="label">Pending Drafts</span><span>{data.get('pending_drafts', 0)}</span></div>
  {''.join(f'''
  <div class="stat-row">
    <span class="label">{plat}</span>
    <span>{count} posts</span>
  </div>''' for plat, count in data.get('posts_by_platform', {}).items())}
</div>

<!-- MAILING LIST -->
<div class="section">
  <h2>MAILING LIST ({data.get('email_optins', 0)} subscribers)</h2>
  <table>
    <tr><th>EMAIL</th><th>SIGNED UP</th></tr>
    {''.join(f"""
    <tr><td>{m['email']}</td><td>{m['signed_up']}</td></tr>"""
    for m in data.get('mailing_list', []))}
  </table>
</div>

<a href="?password={password}" class="refresh">REFRESH</a>

</body></html>"""

    return HTMLResponse(content=html, status_code=200)
