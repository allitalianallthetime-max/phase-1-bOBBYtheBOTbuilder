"""
CONCEPTION MARKETING ENGINE
==============================
Generates ready-to-post marketing content for The Builder Foundry.
Focused on FREE channels: Reddit, Facebook groups, Twitter/X, Hacker News.

How it works:
  1. /marketing/daily-tasks  — Conception picks today's best platforms and
     generates copy-paste-ready posts for each one.
  2. /marketing/generate     — Generate a post for a specific platform + angle.
  3. /marketing/log          — Log that you posted (Conception tracks what works).
  4. /marketing/stats        — See what's been posted and what's pending.
  5. /marketing/ideas        — Fresh content ideas based on Builder Foundry features.

Conception learns: every post logged feeds back into his understanding
of what resonates on each platform.

This is a FastAPI Router — imported by the main conception_service.py gateway.
"""

import os
import json
import logging
from datetime import datetime, date, timedelta
from typing import Optional
from contextlib import contextmanager

import psycopg2.pool
from fastapi import APIRouter, Header, Depends, HTTPException
from pydantic import BaseModel

try:
    import google.generativeai as genai
    _GENAI_OK = True
except ImportError:
    _GENAI_OK = False

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("conception_marketing")

router = APIRouter(prefix="/marketing", tags=["marketing"])

# ── DB (pool injected by gateway) ─────────────────────────────────────────────
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


# ── AUTH ──────────────────────────────────────────────────────────────────────
_int_key = os.getenv("INTERNAL_API_KEY", "")


def verify(x_internal_key: str = Header(None)):
    import secrets
    if not secrets.compare_digest(x_internal_key or "", _int_key):
        raise HTTPException(status_code=403, detail="Forbidden")


# ── DB INIT ───────────────────────────────────────────────────────────────────
def init_marketing_db():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS marketing_posts (
                id            SERIAL PRIMARY KEY,
                platform      TEXT NOT NULL,
                subreddit     TEXT,
                post_type     TEXT DEFAULT 'text',
                title         TEXT,
                body          TEXT,
                status        TEXT DEFAULT 'draft',
                engagement    JSONB DEFAULT '{}',
                created_at    TIMESTAMP DEFAULT NOW(),
                posted_at     TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS marketing_schedule (
                id            SERIAL PRIMARY KEY,
                day_of_week   INTEGER,
                platform      TEXT NOT NULL,
                subreddit     TEXT,
                angle         TEXT,
                active        BOOLEAN DEFAULT TRUE
            );
        """)
        # Seed weekly schedule if empty
        cur.execute("SELECT COUNT(*) FROM marketing_schedule")
        if cur.fetchone()[0] == 0:
            schedule = [
                # Monday: Reddit launch day
                (0, "reddit", "r/SideProject", "Show off what you built"),
                (0, "reddit", "r/maker", "Junkyard engineering angle"),
                # Tuesday: Hacker News + Reddit
                (1, "reddit", "r/robotics", "Technical deep-dive"),
                (1, "hackernews", None, "Show HN post"),
                # Wednesday: Facebook
                (2, "facebook", None, "Story-driven — built from scraps"),
                (2, "reddit", "r/engineering", "Engineering problem solved"),
                # Thursday: Reddit variety
                (3, "reddit", "r/startups", "Solo founder story"),
                (3, "reddit", "r/DIY", "Build project showcase"),
                # Friday: Twitter + Facebook
                (4, "twitter", None, "Thread — how it works"),
                (4, "facebook", None, "Community engagement post"),
                # Saturday: Reddit weekend
                (5, "reddit", "r/ArtificialIntelligence", "AI multi-agent angle"),
                (5, "reddit", "r/3Dprinting", "Cross-maker appeal"),
                # Sunday: Reflection + planning
                (6, "facebook", None, "Weekly wins / builder spotlight"),
                (6, "twitter", None, "Quick tip or feature highlight"),
            ]
            for dow, plat, sub, angle in schedule:
                cur.execute(
                    "INSERT INTO marketing_schedule (day_of_week, platform, subreddit, angle) "
                    "VALUES (%s, %s, %s, %s)",
                    (dow, plat, sub, angle)
                )
        conn.commit()
    log.info("Marketing DB initialized.")


# ══════════════════════════════════════════════════════════════════════════════
# CONTENT KNOWLEDGE — What Builder Foundry IS
# ══════════════════════════════════════════════════════════════════════════════

BUILDER_FOUNDRY_CONTEXT = """
THE BUILDER FOUNDRY (bobtherobotbuilder.com)
- AI-powered engineering blueprint generator
- You tell it what you HAVE (junk, scrap, old equipment) and what you WANT TO BUILD
- 3 AI agents collaborate: GROK-3 (inventory analysis), CLAUDE SONNET (blueprint), GEMINI (quality review)
- Every blueprint traces parts back to YOUR inventory — no "go buy new parts"
- Includes: technical SVG schematic, honesty assessment, feasibility rating, budget gap-filler shopping list
- Built by a self-taught developer who pieces together computers from scrap
- This is Phase 1 of CONCEPTION — an advanced AI learning from every blueprint
- Free trial: 1 build, no credit card
- Pricing: Starter $25/mo (25 builds), Pro $100/mo (100 builds), Master $999/yr (unlimited)
- Built on: Python, FastAPI, Celery, Redis, PostgreSQL, Render.com
- Creator: Anthony Coco / AoC3P0 Systems

KEY DIFFERENTIATORS:
- Other AI tools tell you to buy parts. Builder Foundry uses what you HAVE.
- 3 agents debate the design — not just one AI hallucinating
- Honesty layer: tells you what WON'T work and what's missing
- Budget gap-filler: cheapest parts to complete the build (Harbor Freight, salvage yards)
- Every blueprint trains Conception (the AI gets smarter)

EXAMPLE: User inputs "cat litter robot" + "old treadmill + Dell computer"
→ Gets a complete blueprint using treadmill motor as drive, belt as sifting surface,
  computer as controller. Feasibility: 70%. Gap cost: $35-80 from salvage.

TARGET AUDIENCES:
- Makers, DIY builders, garage tinkerers
- Robotics hobbyists
- Engineering students
- Preppers and off-grid builders
- Anyone with a pile of junk and a project idea
"""

# ── Platform-specific style guides ────────────────────────────────────────────
PLATFORM_GUIDES = {
    "reddit": {
        "style": (
            "Conversational, value-first, NO salesy language. Reddit hates ads. "
            "Lead with the problem you solved or something cool you built. "
            "Mention the product naturally as 'something I built' or 'a tool I made.' "
            "End with an invitation to try it, not a hard sell. "
            "Include the URL only once, at the end. Never use emojis in titles."
        ),
        "rules": [
            "No clickbait titles",
            "No '🚀🔥💰' emoji spam",
            "Share genuine value before mentioning the product",
            "Be honest about limitations",
            "Engage authentically in comments",
        ],
    },
    "facebook": {
        "style": (
            "Story-driven, personal, emotional. Facebook rewards stories. "
            "Talk about WHY you built it, not just WHAT it does. "
            "Mention being self-taught, building from scraps, no funding. "
            "Use 1-2 emojis max. Ask a question at the end to drive comments. "
            "Include the URL in the first comment, not the main post."
        ),
        "rules": [
            "Personal story hooks perform 3x better",
            "Questions in posts drive engagement",
            "URL in first comment, not main body",
            "Post in relevant groups, not just your wall",
        ],
    },
    "twitter": {
        "style": (
            "Punchy, hook-first, thread-friendly. First tweet must grab attention. "
            "Use threads for complex ideas. Each tweet under 280 chars. "
            "1-2 hashtags max. Be opinionated — 'hot takes' get engagement. "
            "Show don't tell — screenshots, examples, results."
        ),
        "rules": [
            "Hook in first 10 words",
            "Threads get 5x more engagement than single tweets",
            "Tag relevant people/communities",
            "Post between 9am-12pm EST for best reach",
        ],
    },
    "hackernews": {
        "style": (
            "Technical, understated, Show HN format. HN rewards substance and "
            "hates marketing speak. Lead with what's technically interesting — "
            "multi-agent AI, inventory-first engineering, Celery pipeline. "
            "Be humble. Mention limitations openly. Expect tough questions."
        ),
        "rules": [
            "Title format: 'Show HN: [product] – [one-line description]'",
            "First comment should explain the technical story",
            "Be ready to answer architecture questions",
            "Post Tuesday-Thursday 9am-11am EST",
        ],
    },
}

# ── Subreddit knowledge ───────────────────────────────────────────────────────
SUBREDDIT_GUIDES = {
    "r/SideProject": "Show off personal projects. Be honest about revenue, tech stack, and journey.",
    "r/maker": "Maker community. Show physical builds, tools, junkyard finds. They love resourcefulness.",
    "r/robotics": "Technical crowd. Show the AI pipeline, multi-agent architecture, blueprint quality.",
    "r/engineering": "Professional engineers. Lead with the engineering problem, not the product.",
    "r/startups": "Startup founders. Talk about solo founding, bootstrapping, $0 budget.",
    "r/DIY": "DIY builders. Show a specific project built from the blueprint. Before/after.",
    "r/ArtificialIntelligence": "AI enthusiasts. Multi-agent collaboration is the hook.",
    "r/3Dprinting": "Cross-maker audience. They understand iterative design from inventory.",
    "r/arduino": "Electronics hobbyists. The computer-as-controller angle resonates.",
    "r/Frugal": "Budget-conscious. 'Build it from junk instead of buying it' is their language.",
}


# ══════════════════════════════════════════════════════════════════════════════
# AI CONTENT GENERATION
# ══════════════════════════════════════════════════════════════════════════════

async def _generate_post(platform: str,
                         angle: str,
                         subreddit: Optional[str] = None) -> dict:
    """Generate a ready-to-post piece of content using Gemini."""
    if not _GENAI_OK or not os.getenv("GEMINI_API_KEY"):
        return _fallback_post(platform, angle, subreddit)

    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel("gemini-2.5-flash")

    platform_guide = PLATFORM_GUIDES.get(platform, PLATFORM_GUIDES["reddit"])
    sub_guide = SUBREDDIT_GUIDES.get(subreddit, "") if subreddit else ""

    prompt = f"""You are Conception, an AI marketing assistant for The Builder Foundry.

PRODUCT CONTEXT:
{BUILDER_FOUNDRY_CONTEXT}

TASK: Write a {platform} post.
ANGLE: {angle}
{"SUBREDDIT: " + subreddit if subreddit else ""}
{"SUBREDDIT GUIDE: " + sub_guide if sub_guide else ""}

PLATFORM STYLE:
{platform_guide['style']}

PLATFORM RULES:
{chr(10).join('- ' + r for r in platform_guide['rules'])}

OUTPUT FORMAT — Return ONLY valid JSON, no markdown:
{{
    "title": "Post title (for Reddit/HN) or first line (for Facebook/Twitter)",
    "body": "Full post body. Ready to copy-paste.",
    "hashtags": ["relevant", "hashtags"],
    "best_time": "Suggested posting time (EST)",
    "notes": "Any tips for Anthony when posting this"
}}
"""
    try:
        resp = model.generate_content(prompt)
        text = resp.text.strip()
        # Clean markdown fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        return json.loads(text)
    except json.JSONDecodeError:
        log.warning("Gemini returned invalid JSON, using fallback")
        return _fallback_post(platform, angle, subreddit)
    except Exception as e:
        log.error("Content generation failed: %s", e)
        return _fallback_post(platform, angle, subreddit)


def _fallback_post(platform: str, angle: str, subreddit: Optional[str] = None) -> dict:
    """Static fallback if Gemini is unavailable."""
    return {
        "title": f"I built an AI that turns junk into engineering blueprints",
        "body": (
            "I'm a self-taught developer who builds computers from scrap parts. "
            "I got tired of AI tools telling me to 'go buy new parts' when I asked "
            "how to build things from what I already have.\n\n"
            "So I built The Builder Foundry — 3 AI agents collaborate to generate "
            "complete engineering blueprints from YOUR actual inventory. Every part "
            "traces back to something you own.\n\n"
            "It even tells you what WON'T work and gives you a budget shopping list "
            "for the gaps (Harbor Freight prices, not Snap-On).\n\n"
            "Free trial — one build, no credit card: bobtherobotbuilder.com"
        ),
        "hashtags": ["maker", "engineering", "AI", "DIY"],
        "best_time": "9:00 AM EST",
        "notes": f"Post to {subreddit or platform}. Engage with every comment.",
    }


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

class GenerateReq(BaseModel):
    platform: str = "reddit"
    angle: str = "general product showcase"
    subreddit: Optional[str] = None


class LogPostReq(BaseModel):
    platform: str
    subreddit: Optional[str] = None
    title: str
    body: str = ""
    url: Optional[str] = None


class EngagementReq(BaseModel):
    post_id: int
    upvotes: int = 0
    comments: int = 0
    clicks: int = 0
    signups: int = 0


@router.get("/daily-tasks", dependencies=[Depends(verify)])
async def daily_tasks():
    """
    Conception's daily marketing plan. Returns today's posting tasks
    with ready-to-use content for each platform.
    """
    today_dow = datetime.utcnow().weekday()  # 0=Monday

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT platform, subreddit, angle FROM marketing_schedule "
            "WHERE day_of_week = %s AND active = TRUE",
            (today_dow,)
        )
        tasks = cur.fetchall()

        # Check what's already been posted today
        cur.execute(
            "SELECT platform, subreddit FROM marketing_posts "
            "WHERE posted_at::date = CURRENT_DATE AND status = 'posted'"
        )
        already_posted = {(r[0], r[1]) for r in cur.fetchall()}

    results = []
    for platform, subreddit, angle in tasks:
        already_done = (platform, subreddit) in already_posted
        post_content = None

        if not already_done:
            post_content = await _generate_post(platform, angle, subreddit)
            # Save as draft
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO marketing_posts (platform, subreddit, title, body, status) "
                    "VALUES (%s, %s, %s, %s, 'draft')",
                    (platform, subreddit,
                     post_content.get("title", ""),
                     post_content.get("body", ""))
                )
                conn.commit()

        results.append({
            "platform":  platform,
            "subreddit": subreddit,
            "angle":     angle,
            "status":    "already_posted" if already_done else "ready",
            "content":   post_content,
        })

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return {
        "day":   day_names[today_dow],
        "tasks": results,
        "total": len(results),
        "done":  sum(1 for r in results if r["status"] == "already_posted"),
        "message": f"Conception has {len(results)} marketing tasks for you today."
    }


@router.post("/generate", dependencies=[Depends(verify)])
async def generate_post(req: GenerateReq):
    """Generate a single post for a specific platform and angle."""
    content = await _generate_post(req.platform, req.angle, req.subreddit)

    # Save as draft
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO marketing_posts (platform, subreddit, title, body, status) "
            "VALUES (%s, %s, %s, %s, 'draft') RETURNING id",
            (req.platform, req.subreddit,
             content.get("title", ""), content.get("body", ""))
        )
        post_id = cur.fetchone()[0]
        conn.commit()

    return {
        "post_id":  post_id,
        "platform": req.platform,
        "content":  content,
        "message":  "Copy-paste ready. Log it after you post."
    }


@router.post("/log", dependencies=[Depends(verify)])
def log_post(req: LogPostReq):
    """Log that you actually posted content. Conception tracks it."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO marketing_posts (platform, subreddit, title, body, status, posted_at) "
            "VALUES (%s, %s, %s, %s, 'posted', NOW()) RETURNING id",
            (req.platform, req.subreddit, req.title, req.body)
        )
        post_id = cur.fetchone()[0]
        conn.commit()

    log.info("Post logged: %s %s (id=%d)", req.platform, req.subreddit or "", post_id)
    return {"post_id": post_id, "status": "logged"}


@router.post("/engagement", dependencies=[Depends(verify)])
def update_engagement(req: EngagementReq):
    """Feed engagement data back. Conception learns what works."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE marketing_posts SET engagement = %s WHERE id = %s",
            (json.dumps({
                "upvotes": req.upvotes, "comments": req.comments,
                "clicks": req.clicks, "signups": req.signups,
            }), req.post_id)
        )
        conn.commit()

    log.info("Engagement updated for post %d", req.post_id)
    return {"status": "updated", "message": "Conception learned from this post's performance."}


@router.get("/stats", dependencies=[Depends(verify)])
def marketing_stats(days: int = 30):
    """Marketing performance overview."""
    with get_db() as conn:
        cur = conn.cursor()

        # Total posts by platform
        cur.execute("""
            SELECT platform, COUNT(*), 
                   SUM(COALESCE((engagement->>'clicks')::int, 0)),
                   SUM(COALESCE((engagement->>'signups')::int, 0))
            FROM marketing_posts
            WHERE created_at >= NOW() - INTERVAL '%s days'
              AND status = 'posted'
            GROUP BY platform ORDER BY COUNT(*) DESC
        """, (days,))
        by_platform = [
            {"platform": r[0], "posts": r[1], "clicks": r[2] or 0, "signups": r[3] or 0}
            for r in cur.fetchall()
        ]

        # Total drafts pending
        cur.execute("SELECT COUNT(*) FROM marketing_posts WHERE status = 'draft'")
        pending = cur.fetchone()[0]

        # Posts this week
        cur.execute(
            "SELECT COUNT(*) FROM marketing_posts "
            "WHERE status = 'posted' AND posted_at >= NOW() - INTERVAL '7 days'"
        )
        this_week = cur.fetchone()[0]

    return {
        "period_days":   days,
        "by_platform":   by_platform,
        "pending_drafts": pending,
        "posts_this_week": this_week,
    }


@router.get("/ideas", dependencies=[Depends(verify)])
async def content_ideas():
    """Fresh content ideas based on Builder Foundry's features."""
    ideas = [
        {
            "angle": "Before/After",
            "description": "Show a pile of junk → the blueprint it generated. Visual proof.",
            "platforms": ["reddit", "facebook", "twitter"],
            "subreddits": ["r/maker", "r/DIY", "r/engineering"],
        },
        {
            "angle": "Honest AI",
            "description": "Most AI tools hallucinate. Ours says 'Feasibility: 70% — here's what's missing.' Post a screenshot of the honesty section.",
            "platforms": ["reddit", "twitter", "hackernews"],
            "subreddits": ["r/ArtificialIntelligence", "r/SideProject"],
        },
        {
            "angle": "Self-Taught Developer Story",
            "description": "No CS degree. No funding. Built from a Frankenstein computer. The underdog story resonates.",
            "platforms": ["reddit", "facebook"],
            "subreddits": ["r/startups", "r/SideProject", "r/learnprogramming"],
        },
        {
            "angle": "3 AI Agents Debate Your Blueprint",
            "description": "Grok tears apart inventory, Claude designs the build, Gemini reviews it. Multi-agent collaboration in action.",
            "platforms": ["reddit", "hackernews", "twitter"],
            "subreddits": ["r/ArtificialIntelligence", "r/robotics"],
        },
        {
            "angle": "Budget Gap-Filler",
            "description": "The AI tells you exactly which $8 part from Harbor Freight fills the gap. Screenshot the shopping list section.",
            "platforms": ["reddit", "facebook"],
            "subreddits": ["r/Frugal", "r/DIY", "r/maker"],
        },
        {
            "angle": "Challenge Post",
            "description": "Give me your weirdest inventory and I'll show you what the AI designs. Interactive engagement.",
            "platforms": ["reddit", "facebook", "twitter"],
            "subreddits": ["r/maker", "r/robotics", "r/DIY"],
        },
        {
            "angle": "Conception Origin Story",
            "description": "This is Phase 1 of an AI that will eventually walk in a body. Every blueprint makes him smarter.",
            "platforms": ["reddit", "hackernews"],
            "subreddits": ["r/ArtificialIntelligence", "r/Futurology"],
        },
    ]
    return {"ideas": ideas, "count": len(ideas)}


@router.get("/schedule", dependencies=[Depends(verify)])
def view_schedule():
    """View the weekly posting schedule."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT day_of_week, platform, subreddit, angle, active "
            "FROM marketing_schedule ORDER BY day_of_week, platform"
        )
        rows = cur.fetchall()

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return {
        "schedule": [
            {
                "day": day_names[r[0]],
                "platform": r[1],
                "subreddit": r[2],
                "angle": r[3],
                "active": r[4],
            }
            for r in rows
        ]
    }
