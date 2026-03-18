"""
CONCEPTION COMMAND CENTER
===========================
One page. All metrics. Marketing controls. Works on your phone.

GET /dashboard              — Full HTML dashboard (password via query param)
GET /dashboard/data         — Raw JSON metrics
POST /dashboard/generate    — Generate a marketing post (called via fetch from dashboard)
POST /dashboard/mark-posted — Mark a draft as posted
"""

import os
import json
import logging
from datetime import datetime, timedelta
from contextlib import contextmanager

import psycopg2.pool
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

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


_admin_pass = os.getenv("DASHBOARD_PASSWORD", "conception2026")


def _check_pass(password: str):
    if password != _admin_pass:
        raise HTTPException(status_code=403, detail="Invalid password.")


def _safe_query(cur, sql, params=None):
    try:
        cur.execute(sql, params)
        return cur.fetchall()
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════════════════════
# DATA ENDPOINT
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/data")
def dashboard_data(password: str = ""):
    _check_pass(password)
    data = {}

    with get_db() as conn:
        cur = conn.cursor()
        conn.autocommit = True

        # Licenses
        rows = _safe_query(cur, "SELECT COUNT(*) FROM licenses")
        data["total_licenses"] = rows[0][0] if rows else 0

        rows = _safe_query(cur, "SELECT tier, COUNT(*) FROM licenses WHERE status='active' GROUP BY tier")
        data["licenses_by_tier"] = {r[0]: r[1] for r in rows} if rows else {}

        rows = _safe_query(cur, "SELECT COUNT(*) FROM licenses WHERE tier='trial' AND status='active'")
        data["trial_users"] = rows[0][0] if rows else 0

        rows = _safe_query(cur, "SELECT COUNT(*) FROM licenses WHERE tier != 'trial' AND status='active'")
        data["paid_users"] = rows[0][0] if rows else 0

        rows = _safe_query(cur, "SELECT COUNT(*) FROM licenses WHERE created_at >= NOW() - INTERVAL '24 hours'")
        data["signups_today"] = rows[0][0] if rows else 0

        rows = _safe_query(cur, "SELECT COUNT(*) FROM licenses WHERE created_at >= NOW() - INTERVAL '7 days'")
        data["signups_this_week"] = rows[0][0] if rows else 0

        # Builds
        rows = _safe_query(cur, "SELECT COUNT(*) FROM builds")
        data["total_builds"] = rows[0][0] if rows else 0

        rows = _safe_query(cur, "SELECT COUNT(*) FROM builds WHERE created_at >= NOW() - INTERVAL '24 hours'")
        data["builds_today"] = rows[0][0] if rows else 0

        rows = _safe_query(cur, "SELECT COUNT(*) FROM builds WHERE created_at >= NOW() - INTERVAL '7 days'")
        data["builds_this_week"] = rows[0][0] if rows else 0

        rows = _safe_query(cur, "SELECT COALESCE(SUM(tokens_used), 0) FROM builds")
        data["total_tokens"] = rows[0][0] if rows else 0

        rows = _safe_query(cur, "SELECT project_type, COUNT(*) as cnt FROM builds GROUP BY project_type ORDER BY cnt DESC LIMIT 5")
        data["top_projects"] = [{"project": r[0], "count": r[1]} for r in rows] if rows else []

        rows = _safe_query(cur, "SELECT user_email, project_type, tokens_used, created_at FROM builds ORDER BY created_at DESC LIMIT 10")
        data["recent_builds"] = [
            {"email": r[0], "project": r[1], "tokens": r[2], "time": r[3].strftime("%Y-%m-%d %H:%M") if r[3] else ""}
            for r in rows
        ] if rows else []

        # Marketing
        rows = _safe_query(cur, "SELECT COUNT(*) FROM marketing_posts WHERE status='posted'")
        data["total_posts"] = rows[0][0] if rows else 0

        rows = _safe_query(cur, "SELECT COUNT(*) FROM marketing_posts WHERE status='draft'")
        data["pending_drafts"] = rows[0][0] if rows else 0

        rows = _safe_query(cur, "SELECT COUNT(*) FROM marketing_posts WHERE status='posted' AND posted_at >= NOW() - INTERVAL '7 days'")
        data["posts_this_week"] = rows[0][0] if rows else 0

        rows = _safe_query(cur, "SELECT platform, COUNT(*) FROM marketing_posts WHERE status='posted' GROUP BY platform ORDER BY COUNT(*) DESC")
        data["posts_by_platform"] = {r[0]: r[1] for r in rows} if rows else {}

        # Trials
        rows = _safe_query(cur, "SELECT COUNT(*) FROM licenses WHERE tier='trial' AND build_count > 0")
        data["trials_used"] = rows[0][0] if rows else 0

        rows = _safe_query(cur, "SELECT notes FROM licenses WHERE tier='trial' AND notes LIKE '%%email_optin=True%%'")
        data["email_optins"] = len(rows) if rows else 0

        rows = _safe_query(cur, "SELECT email, created_at FROM licenses WHERE tier='trial' AND notes LIKE '%%email_optin=True%%' ORDER BY created_at DESC LIMIT 50")
        data["mailing_list"] = [
            {"email": r[0], "signed_up": r[1].strftime("%Y-%m-%d") if r[1] else ""}
            for r in rows
        ] if rows else []

        # Drafts ready to post
        rows = _safe_query(cur,
            "SELECT id, platform, subreddit, title, body, created_at "
            "FROM marketing_posts WHERE status='draft' ORDER BY created_at DESC LIMIT 20")
        data["drafts"] = [
            {"id": r[0], "platform": r[1], "subreddit": r[2] or "",
             "title": r[3] or "", "body": r[4] or "",
             "created": r[5].strftime("%Y-%m-%d %H:%M") if r[5] else ""}
            for r in rows
        ] if rows else []

        # Weekly schedule
        rows = _safe_query(cur,
            "SELECT day_of_week, platform, subreddit, angle, active "
            "FROM marketing_schedule WHERE active=TRUE ORDER BY day_of_week, platform")
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        data["schedule"] = [
            {"day": days[r[0]] if r[0] < 7 else "?", "platform": r[1],
             "subreddit": r[2] or "", "angle": r[3]}
            for r in rows
        ] if rows else []

    data["generated_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return data


# ══════════════════════════════════════════════════════════════════════════════
# ACTION ENDPOINTS (called via fetch from dashboard JS)
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/generate")
async def generate_from_dashboard(request: Request):
    """Generate a marketing post. Called by dashboard JS."""
    body = await request.json()
    password = body.get("password", "")
    _check_pass(password)

    platform = body.get("platform", "reddit")
    angle = body.get("angle", "general product showcase")
    subreddit = body.get("subreddit")

    # Import the generate function from marketing module
    from conception_marketing import _generate_post
    content = await _generate_post(platform, angle, subreddit)

    # Save as draft
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO marketing_posts (platform, subreddit, title, body, status) "
            "VALUES (%s, %s, %s, %s, 'draft') RETURNING id",
            (platform, subreddit, content.get("title", ""), content.get("body", ""))
        )
        post_id = cur.fetchone()[0]
        conn.commit()

    return {"post_id": post_id, "content": content}


@router.post("/mark-posted")
async def mark_posted(request: Request):
    """Mark a draft as posted."""
    body = await request.json()
    _check_pass(body.get("password", ""))
    post_id = body.get("post_id")

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE marketing_posts SET status='posted', posted_at=NOW() WHERE id=%s",
            (post_id,)
        )
        conn.commit()
    return {"status": "ok"}


# ══════════════════════════════════════════════════════════════════════════════
# HTML DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@router.get("", response_class=HTMLResponse)
def dashboard_html(password: str = ""):
    if password != _admin_pass:
        return HTMLResponse(content="""
        <html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head>
        <body style="background:#0A0E17;color:#E2E8F0;font-family:system-ui;
        display:flex;align-items:center;justify-content:center;height:100vh;">
        <form method="get" style="text-align:center;">
          <h2 style="color:#FF4500;">Conception Command Center</h2>
          <input name="password" type="password" placeholder="Password"
           style="padding:12px;border-radius:6px;border:1px solid #334155;
           background:#1E293B;color:white;font-size:16px;width:260px;" />
          <br><br>
          <button style="padding:12px 32px;background:#FF4500;color:white;border:none;
           border-radius:6px;font-size:16px;cursor:pointer;">ENTER</button>
        </form></body></html>
        """, status_code=200)

    data = dashboard_data(password=password)

    # Content ideas (hardcoded — no DB needed)
    ideas_json = json.dumps([
        {"angle": "Before/After", "desc": "Pile of junk vs the blueprint it generated", "platforms": "Reddit, Facebook"},
        {"angle": "Honest AI", "desc": "Screenshot the feasibility rating + gaps section", "platforms": "Reddit, Twitter, HN"},
        {"angle": "Self-Taught Story", "desc": "No CS degree, no funding, built from scraps", "platforms": "Reddit, Facebook"},
        {"angle": "3 Agents Debate", "desc": "Grok + Claude + Gemini collaborate on your build", "platforms": "Reddit, HN, Twitter"},
        {"angle": "Budget Gap-Filler", "desc": "AI finds $8 parts at Harbor Freight to complete your build", "platforms": "Reddit, Facebook"},
        {"angle": "Challenge Post", "desc": "Give me your weirdest inventory, I'll show the blueprint", "platforms": "Reddit, Facebook"},
        {"angle": "Conception Origin", "desc": "Phase 1 of an AI that will eventually walk in a body", "platforms": "Reddit, HN"},
    ])

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Conception Command Center</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:#0A0E17; color:#E2E8F0; font-family:system-ui,-apple-system,sans-serif;
       padding:16px; max-width:1000px; margin:0 auto; }}
h1 {{ color:#FF4500; font-size:22px; }}
.sub {{ color:#64748B; font-size:12px; margin-bottom:20px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:10px; margin-bottom:20px; }}
.card {{ background:#1E293B; border-radius:8px; padding:14px; text-align:center; }}
.card .n {{ font-size:28px; font-weight:bold; color:#FF4500; }}
.card .l {{ font-size:10px; color:#94A3B8; letter-spacing:1px; margin-top:2px; }}
.sec {{ margin-bottom:20px; }}
.sec h2 {{ color:#E2E8F0; font-size:14px; border-bottom:1px solid #2A3A52;
           padding-bottom:6px; margin-bottom:10px; letter-spacing:1px; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{ text-align:left; color:#94A3B8; font-size:10px; letter-spacing:1px; padding:6px; border-bottom:1px solid #2A3A52; }}
td {{ padding:6px; border-bottom:1px solid #1E293B; }}
.row {{ display:flex; justify-content:space-between; padding:5px 0; border-bottom:1px solid #1E293B; font-size:13px; }}
.row .lbl {{ color:#94A3B8; }}
.tier {{ display:inline-block; padding:2px 8px; border-radius:4px; font-size:10px; font-weight:bold; }}
.t-trial {{ background:#10B981; color:white; }}
.t-starter {{ background:#94A3B8; color:white; }}
.t-pro {{ background:#FF4500; color:white; }}
.t-master {{ background:#FFD700; color:#000; }}
.btn {{ padding:10px 20px; border:none; border-radius:6px; font-size:13px; cursor:pointer; font-weight:bold; }}
.btn-orange {{ background:#FF4500; color:white; }}
.btn-green {{ background:#10B981; color:white; }}
.btn-blue {{ background:#3B82F6; color:white; }}
.btn-sm {{ padding:6px 12px; font-size:11px; }}
.btn:hover {{ opacity:0.85; }}
.draft {{ background:#1E293B; border:1px solid #2A3A52; border-radius:8px; padding:14px; margin-bottom:12px; }}
.draft h3 {{ color:#F97316; font-size:13px; margin-bottom:4px; }}
.draft .platform {{ color:#3B82F6; font-size:11px; font-weight:bold; letter-spacing:1px; }}
.draft .body {{ color:#CBD5E1; font-size:13px; white-space:pre-wrap; margin:8px 0;
               background:#0F1623; padding:10px; border-radius:4px; max-height:200px; overflow-y:auto; }}
.draft .actions {{ display:flex; gap:8px; flex-wrap:wrap; }}
.idea {{ background:#1E293B; border-left:3px solid #F97316; padding:10px 14px; margin-bottom:8px; border-radius:0 6px 6px 0; }}
.idea .angle {{ color:#F97316; font-size:13px; font-weight:bold; }}
.idea .desc {{ color:#94A3B8; font-size:12px; margin-top:2px; }}
.idea .plat {{ color:#64748B; font-size:10px; margin-top:2px; }}
.gen-form {{ background:#1E293B; padding:16px; border-radius:8px; margin-bottom:16px; }}
.gen-form select, .gen-form input {{ padding:8px; border-radius:4px; border:1px solid #334155;
  background:#0F1623; color:white; font-size:13px; margin-right:8px; margin-bottom:8px; }}
#gen-result {{ margin-top:12px; }}
.loading {{ color:#F97316; font-style:italic; }}
.sched-row {{ display:flex; gap:12px; padding:4px 0; border-bottom:1px solid #1E293B; font-size:12px; }}
.sched-day {{ color:#FF4500; font-weight:bold; width:36px; }}
.sched-plat {{ color:#3B82F6; width:80px; }}
.sched-sub {{ color:#64748B; width:120px; }}
.sched-angle {{ color:#94A3B8; flex:1; }}
@media(max-width:600px) {{
  .grid {{ grid-template-columns:repeat(2,1fr); }}
}}
</style>
</head>
<body>

<h1>CONCEPTION COMMAND CENTER</h1>
<div class="sub">{data.get('generated_at','')} | <a href="?password={password}" style="color:#FF4500;">REFRESH</a></div>

<!-- METRICS -->
<div class="grid">
  <div class="card"><div class="n">{data.get('total_licenses',0)}</div><div class="l">SIGNUPS</div></div>
  <div class="card"><div class="n">{data.get('trial_users',0)}</div><div class="l">TRIALS</div></div>
  <div class="card"><div class="n">{data.get('paid_users',0)}</div><div class="l">PAID</div></div>
  <div class="card"><div class="n">{data.get('total_builds',0)}</div><div class="l">BUILDS</div></div>
  <div class="card"><div class="n">{data.get('signups_today',0)}</div><div class="l">TODAY SIGNUPS</div></div>
  <div class="card"><div class="n">{data.get('builds_today',0)}</div><div class="l">TODAY BUILDS</div></div>
  <div class="card"><div class="n">{data.get('email_optins',0)}</div><div class="l">EMAIL LIST</div></div>
  <div class="card"><div class="n">{data.get('total_tokens',0):,}</div><div class="l">TOKENS</div></div>
</div>

<!-- TRIAL FUNNEL -->
<div class="sec">
  <h2>TRIAL FUNNEL</h2>
  <div class="row"><span class="lbl">Trial Signups</span><span>{data.get('trial_users',0)}</span></div>
  <div class="row"><span class="lbl">Trials That Built</span><span>{data.get('trials_used',0)}</span></div>
  <div class="row"><span class="lbl">Email Opt-ins</span><span>{data.get('email_optins',0)}</span></div>
  <div class="row"><span class="lbl">Paid Conversions</span><span>{data.get('paid_users',0)}</span></div>
</div>

<!-- GENERATE POST -->
<div class="sec">
  <h2>GENERATE MARKETING POST</h2>
  <div class="gen-form">
    <select id="gen-platform">
      <option value="reddit">Reddit</option>
      <option value="facebook">Facebook</option>
      <option value="twitter">Twitter/X</option>
      <option value="hackernews">Hacker News</option>
    </select>
    <input id="gen-sub" placeholder="Subreddit (e.g. r/maker)" style="width:160px;" />
    <input id="gen-angle" placeholder="Angle (e.g. self-taught story)" style="width:200px;" />
    <button class="btn btn-orange" onclick="generatePost()">GENERATE</button>
    <div id="gen-result"></div>
  </div>
</div>

<!-- DRAFTS READY TO POST -->
<div class="sec">
  <h2>DRAFTS READY TO POST ({len(data.get('drafts',[]))})</h2>
  <div id="drafts-area">
  {''.join(f"""
  <div class="draft" id="draft-{d['id']}">
    <div class="platform">{d['platform'].upper()}{(' / ' + d['subreddit']) if d['subreddit'] else ''}</div>
    <h3>{d['title']}</h3>
    <div class="body">{d['body'][:800]}</div>
    <div class="actions">
      <button class="btn btn-sm btn-green" onclick="copyDraft({d['id']})">COPY</button>
      <button class="btn btn-sm btn-blue" onclick="markPosted({d['id']})">MARK AS POSTED</button>
    </div>
  </div>""" for d in data.get('drafts',[]))}
  </div>
</div>

<!-- CONTENT IDEAS -->
<div class="sec">
  <h2>CONTENT IDEAS</h2>
  <div id="ideas-area"></div>
</div>

<!-- WEEKLY SCHEDULE -->
<div class="sec">
  <h2>WEEKLY POSTING SCHEDULE</h2>
  {''.join(f"""
  <div class="sched-row">
    <span class="sched-day">{s['day']}</span>
    <span class="sched-plat">{s['platform']}</span>
    <span class="sched-sub">{s['subreddit']}</span>
    <span class="sched-angle">{s['angle']}</span>
  </div>""" for s in data.get('schedule',[]))}
</div>

<!-- RECENT BUILDS -->
<div class="sec">
  <h2>RECENT BUILDS</h2>
  <table>
    <tr><th>USER</th><th>PROJECT</th><th>TOKENS</th><th>TIME</th></tr>
    {''.join(f"""<tr><td>{b['email'][:25]}</td><td>{b['project'][:35]}</td><td>{b['tokens']:,}</td><td>{b['time']}</td></tr>"""
    for b in data.get('recent_builds',[]))}
  </table>
</div>

<!-- TOP PROJECTS -->
<div class="sec">
  <h2>TOP PROJECTS</h2>
  {''.join(f'<div class="row"><span>{p["project"][:40]}</span><span>{p["count"]} builds</span></div>'
  for p in data.get('top_projects',[]))}
</div>

<!-- MAILING LIST -->
<div class="sec">
  <h2>MAILING LIST ({data.get('email_optins',0)})</h2>
  <table>
    <tr><th>EMAIL</th><th>SIGNED UP</th></tr>
    {''.join(f"<tr><td>{m['email']}</td><td>{m['signed_up']}</td></tr>"
    for m in data.get('mailing_list',[]))}
  </table>
</div>

<!-- LICENSES BY TIER -->
<div class="sec">
  <h2>LICENSES BY TIER</h2>
  {''.join(f'<div class="row"><span class="tier t-{t}">{t.upper()}</span><span>{c}</span></div>'
  for t, c in data.get('licenses_by_tier',{{}}).items())}
</div>

<script>
const PW = "{password}";
const BASE = window.location.origin + "/dashboard";

// Content ideas
const ideas = {ideas_json};
const ideasArea = document.getElementById('ideas-area');
ideas.forEach(i => {{
  ideasArea.innerHTML += `<div class="idea">
    <div class="angle">${{i.angle}}</div>
    <div class="desc">${{i.desc}}</div>
    <div class="plat">${{i.platforms}}</div>
  </div>`;
}});

// Generate post
async function generatePost() {{
  const platform = document.getElementById('gen-platform').value;
  const sub = document.getElementById('gen-sub').value;
  const angle = document.getElementById('gen-angle').value || 'general product showcase';
  const result = document.getElementById('gen-result');
  result.innerHTML = '<div class="loading">Conception is writing...</div>';

  try {{
    const resp = await fetch(BASE + '/generate', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{ password: PW, platform, subreddit: sub || null, angle }})
    }});
    const data = await resp.json();
    const c = data.content;
    result.innerHTML = `
      <div class="draft">
        <div class="platform">${{platform.toUpperCase()}}${{sub ? ' / ' + sub : ''}}</div>
        <h3>${{c.title || ''}}</h3>
        <div class="body">${{c.body || ''}}</div>
        <div style="color:#64748B;font-size:11px;margin-top:4px;">
          Best time: ${{c.best_time || '?'}} | ${{c.notes || ''}}</div>
        <div class="actions" style="margin-top:8px;">
          <button class="btn btn-sm btn-green" onclick="copyText(this)">COPY</button>
          <button class="btn btn-sm btn-blue" onclick="markPosted(${{data.post_id}})">MARK AS POSTED</button>
        </div>
      </div>`;
  }} catch(e) {{
    result.innerHTML = '<div style="color:#EF4444;">Generation failed: ' + e + '</div>';
  }}
}}

// Copy draft text
function copyDraft(id) {{
  const el = document.querySelector('#draft-' + id + ' .body');
  const title = document.querySelector('#draft-' + id + ' h3');
  const text = (title ? title.textContent + '\\n\\n' : '') + el.textContent;
  navigator.clipboard.writeText(text).then(() => {{
    const btn = document.querySelector('#draft-' + id + ' .btn-green');
    btn.textContent = 'COPIED!';
    setTimeout(() => btn.textContent = 'COPY', 2000);
  }});
}}

// Copy generated text
function copyText(btn) {{
  const draft = btn.closest('.draft');
  const title = draft.querySelector('h3');
  const body = draft.querySelector('.body');
  const text = (title ? title.textContent + '\\n\\n' : '') + body.textContent;
  navigator.clipboard.writeText(text).then(() => {{
    btn.textContent = 'COPIED!';
    setTimeout(() => btn.textContent = 'COPY', 2000);
  }});
}}

// Mark as posted
async function markPosted(id) {{
  try {{
    await fetch(BASE + '/mark-posted', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{ password: PW, post_id: id }})
    }});
    const el = document.getElementById('draft-' + id);
    if (el) el.style.opacity = '0.3';
    const btn = event.target;
    btn.textContent = 'POSTED!';
    btn.disabled = true;
  }} catch(e) {{
    alert('Failed: ' + e);
  }}
}}
</script>

</body></html>"""

    return HTMLResponse(content=html, status_code=200)
