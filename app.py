"""
APP.PY — BUILDER FOUNDRY STREAMLIT FRONTEND
=============================================
Public landing page -> License auth -> Forge -> Vault -> Scanner -> DNA -> Chat

Refactored: all HTTP calls use app_helpers (api_get, api_post, api_get_raw).
Repeated patterns extracted into functions. Error handling is consistent.
"""

import streamlit as st
import os
import base64
import time
import html
from dotenv import load_dotenv
from app_helpers import api_get, api_post, api_get_raw, ping_service, APIError

try:
    from PIL import Image
    import io as _io
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

try:
    from builder_styles import BUILDER_CSS, FORGE_HEADER_HTML
except ImportError:
    BUILDER_CSS = ""
    FORGE_HEADER_HTML = "<h1 style='color:#FF4500; text-align:center;'>THE BUILDER FOUNDRY</h1>"

# ── CONFIGURATION ──────────────────────────────────────────────────────────────
load_dotenv()
st.set_page_config(
    page_title="AoC3P0 | THE BUILDER FOUNDRY",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

AUTH_URL       = os.getenv("AUTH_SERVICE_URL",      "http://localhost:8001")
AI_URL         = os.getenv("AI_SERVICE_URL",        "http://localhost:8002")
WORKSHOP_URL   = os.getenv("WORKSHOP_SERVICE_URL",  "http://localhost:8003")
EXPORT_URL     = os.getenv("EXPORT_SERVICE_URL",    "http://localhost:8004")
BILLING_URL    = os.getenv("BILLING_SERVICE_URL",   "http://localhost:8006")
STRIPE_STARTER = os.getenv("STRIPE_URL_STARTER",    "#")
STRIPE_PRO     = os.getenv("STRIPE_URL_PRO",        "#")
STRIPE_MASTER  = os.getenv("STRIPE_URL_MASTER",     "#")

# ── APPLY THEME ────────────────────────────────────────────────────────────────
if BUILDER_CSS:
    st.markdown(BUILDER_CSS, unsafe_allow_html=True)

# ── SESSION STATE ──────────────────────────────────────────────────────────────
_defaults = {
    "logged_in": False, "user_email": "", "user_name": "", "tier": "",
    "jwt_token": "", "active_task": None, "vault_data": None,
    "active_tab": "forge", "scan_task": None, "scan_attempts": 0,
    "forge_attempts": 0, "mechanic_task": None, "mechanic_attempts": 0,
    "landing_warmed": False, "services_warmed": False,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── CACHED DOWNLOADS (prevents self-DDoS on vault page reruns) ────────────────
@st.cache_data(show_spinner=False, ttl=3600)
def _cached_download(url: str):
    """Cache file downloads so vault page reruns don't spam the API."""
    return api_get_raw(url)


# ── REUSABLE UI HELPERS ───────────────────────────────────────────────────────

def _download_buttons(build_id: str, key_suffix: str = ""):
    """Render .md and .txt download buttons for a build."""
    col1, col2 = st.columns(2)
    with col1:
        data, ok = _cached_download(f"{EXPORT_URL}/export/download/{build_id}?fmt=md")
        if ok:
            st.download_button(
                "📥 DOWNLOAD (.md)", data=data,
                file_name=f"blueprint_{build_id}.md", mime="text/markdown",
                key=f"dlmd_{build_id}{key_suffix}", use_container_width=True
            )
    with col2:
        data, ok = _cached_download(f"{EXPORT_URL}/export/download/{build_id}?fmt=txt")
        if ok:
            st.download_button(
                "📥 DOWNLOAD (.txt)", data=data,
                file_name=f"blueprint_{build_id}.txt", mime="text/plain",
                key=f"dltxt_{build_id}{key_suffix}", use_container_width=True
            )


def _show_schematic(schematic: str, build_id: str):
    """Render SVG schematic as base64 image if valid."""
    if not schematic or "<svg" not in schematic or "</svg>" not in schematic:
        return
    svg_start = schematic.find("<svg")
    svg_end = schematic.rfind("</svg>") + 6
    clean_svg = schematic[svg_start:svg_end]
    svg_b64 = base64.b64encode(clean_svg.encode("utf-8")).decode("utf-8")

    st.markdown("#### 📐 TECHNICAL SCHEMATIC")
    st.markdown(
        f'<div style="background:white; padding:16px; border-radius:8px; '
        f'border:1px solid #334155; overflow-x:auto; text-align:center;">'
        f'<img src="data:image/svg+xml;base64,{svg_b64}" '
        f'style="max-width:100%; height:auto;" /></div>',
        unsafe_allow_html=True
    )
    st.download_button(
        "📐 DOWNLOAD SCHEMATIC (.svg)", data=clean_svg,
        file_name=f"schematic_{build_id or 'draft'}.svg",
        mime="image/svg+xml", use_container_width=True
    )
    st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# LANDING PAGE (not logged in)
# ══════════════════════════════════════════════════════════════════════════════
if not st.session_state.logged_in:

    # Silently wake AI service
    if not st.session_state.landing_warmed:
        ping_service(f"{AI_URL}/health")
        st.session_state.landing_warmed = True

    # ── HERO ──
    st.markdown("""
        <div style='text-align:center; padding:20px 20px 0;'>
          <h1 style='color:#FF4500; font-size:42px; margin:0; letter-spacing:2px;'>
            THE BUILDER FOUNDRY</h1>
          <p style='color:#94A3B8; font-size:20px; margin-top:8px; max-width:700px;
                    margin-left:auto; margin-right:auto;'>
            Turn junk into genius.<br>
            AI-powered engineering blueprints from the parts you already have.</p>
        </div>
    """, unsafe_allow_html=True)

    if os.path.exists("hero_banner.jpg"):
        st.image("hero_banner.jpg", use_container_width=True)

    # ── PROBLEM / SOLUTION ──
    st.markdown("""
        <div style='max-width:900px; margin:30px auto; padding:0 20px;'>
          <div style='display:flex; gap:20px; flex-wrap:wrap; justify-content:center;'>
            <div style='background:#1E293B; border:1px solid #334155; border-radius:8px;
                        padding:24px; flex:1; min-width:280px; max-width:400px;'>
              <div style='color:#EF4444; font-size:13px; font-weight:bold;
                          letter-spacing:2px; margin-bottom:8px;'>THE PROBLEM</div>
              <div style='color:#E2E8F0; font-size:16px; line-height:1.6;'>
                You have a garage full of old equipment, scrap parts, and broken machines.
                Every other AI tool tells you to <span style='color:#EF4444;'>go buy new parts</span>.
                That defeats the whole point.</div>
            </div>
            <div style='background:#1E293B; border:1px solid #FF4500; border-radius:8px;
                        padding:24px; flex:1; min-width:280px; max-width:400px;'>
              <div style='color:#FF4500; font-size:13px; font-weight:bold;
                          letter-spacing:2px; margin-bottom:8px;'>THE SOLUTION</div>
              <div style='color:#E2E8F0; font-size:16px; line-height:1.6;'>
                Tell us what you <strong>have</strong> and what you want to <strong>build</strong>.
                Three AI agents tear apart your inventory, identify every harvestable component,
                and generate a complete blueprint using
                <span style='color:#FF4500;'>only your parts</span>.</div>
            </div>
          </div>
        </div>
    """, unsafe_allow_html=True)

    # ── WHAT CAN YOU BUILD? ──
    st.markdown("""
        <div style='text-align:center; margin:40px 0 16px;'>
          <h2 style='color:#E2E8F0; font-size:28px;'>What Can You Build?</h2>
          <p style='color:#64748B; font-size:14px;'>Anything. From anything. Here are some ideas.</p>
        </div>
        <div style='max-width:900px; margin:0 auto; padding:0 20px;'>
          <div style='display:flex; gap:12px; flex-wrap:wrap; justify-content:center;'>
            <div style='background:#1E293B; border-radius:6px; padding:12px 16px;
                        border-left:3px solid #F97316; min-width:170px; flex:1; max-width:210px;'>
              <div style='color:#F97316; font-size:13px; font-weight:bold;'>Robots</div>
              <div style='color:#64748B; font-size:11px; margin-top:2px;'>Bipeds, quadrupeds, arms</div>
            </div>
            <div style='background:#1E293B; border-radius:6px; padding:12px 16px;
                        border-left:3px solid #3B82F6; min-width:170px; flex:1; max-width:210px;'>
              <div style='color:#3B82F6; font-size:13px; font-weight:bold;'>Home Automation</div>
              <div style='color:#64748B; font-size:11px; margin-top:2px;'>Pet feeders, garden systems</div>
            </div>
            <div style='background:#1E293B; border-radius:6px; padding:12px 16px;
                        border-left:3px solid #10B981; min-width:170px; flex:1; max-width:210px;'>
              <div style='color:#10B981; font-size:13px; font-weight:bold;'>Shop Tools</div>
              <div style='color:#64748B; font-size:11px; margin-top:2px;'>Hydraulic press, jigs, rigs</div>
            </div>
            <div style='background:#1E293B; border-radius:6px; padding:12px 16px;
                        border-left:3px solid #A855F7; min-width:170px; flex:1; max-width:210px;'>
              <div style='color:#A855F7; font-size:13px; font-weight:bold;'>Vehicles</div>
              <div style='color:#64748B; font-size:11px; margin-top:2px;'>Go-karts, e-bikes, trailers</div>
            </div>
            <div style='background:#1E293B; border-radius:6px; padding:12px 16px;
                        border-left:3px solid #EF4444; min-width:170px; flex:1; max-width:210px;'>
              <div style='color:#EF4444; font-size:13px; font-weight:bold;'>Energy Systems</div>
              <div style='color:#64748B; font-size:11px; margin-top:2px;'>Solar rigs, wind turbines</div>
            </div>
            <div style='background:#1E293B; border-radius:6px; padding:12px 16px;
                        border-left:3px solid #F59E0B; min-width:170px; flex:1; max-width:210px;'>
              <div style='color:#F59E0B; font-size:13px; font-weight:bold;'>Farm &amp; Garden</div>
              <div style='color:#64748B; font-size:11px; margin-top:2px;'>Irrigation, coops, planters</div>
            </div>
            <div style='background:#1E293B; border-radius:6px; padding:12px 16px;
                        border-left:3px solid #06B6D4; min-width:170px; flex:1; max-width:210px;'>
              <div style='color:#06B6D4; font-size:13px; font-weight:bold;'>Furniture</div>
              <div style='color:#64748B; font-size:11px; margin-top:2px;'>Desks, shelves, workbenches</div>
            </div>
            <div style='background:#1E293B; border-radius:6px; padding:12px 16px;
                        border-left:3px solid #EC4899; min-width:170px; flex:1; max-width:210px;'>
              <div style='color:#EC4899; font-size:13px; font-weight:bold;'>Anything Else</div>
              <div style='color:#64748B; font-size:11px; margin-top:2px;'>If it can be built, we forge it</div>
            </div>
          </div>
        </div>
    """, unsafe_allow_html=True)

    # ── HOW IT WORKS ──
    st.markdown("""
        <div style='text-align:center; margin:40px 0 20px;'>
          <h2 style='color:#E2E8F0; font-size:28px;'>How The Round Table Works</h2>
          <p style='color:#64748B; font-size:14px;'>Three AI agents collaborate on every blueprint</p>
        </div>
    """, unsafe_allow_html=True)

    a1, a2, a3 = st.columns(3)
    with a1:
        st.markdown("""
            <div style='background:#1E293B; border-radius:8px; padding:24px;
                        border-top:3px solid #F97316; text-align:center; min-height:220px;'>
              <div style='font-size:32px; margin-bottom:8px;'>&#128295;</div>
              <div style='color:#F97316; font-weight:bold; font-size:16px;'>GROK-3</div>
              <div style='color:#64748B; font-size:11px; letter-spacing:1px;
                          margin-bottom:12px;'>JUNKYARD ANALYST</div>
              <div style='color:#94A3B8; font-size:13px; line-height:1.5;'>
                Tears apart every item in your inventory. Identifies motors, frames,
                wiring, bearings, circuit boards — everything harvestable.</div>
            </div>
        """, unsafe_allow_html=True)
    with a2:
        st.markdown("""
            <div style='background:#1E293B; border-radius:8px; padding:24px;
                        border-top:3px solid #3B82F6; text-align:center; min-height:220px;'>
              <div style='font-size:32px; margin-bottom:8px;'>&#128208;</div>
              <div style='color:#3B82F6; font-weight:bold; font-size:16px;'>CLAUDE SONNET</div>
              <div style='color:#64748B; font-size:11px; letter-spacing:1px;
                          margin-bottom:12px;'>BLUEPRINT ENGINEER</div>
              <div style='color:#94A3B8; font-size:13px; line-height:1.5;'>
                Writes the full engineering blueprint using only the parts Grok identified.
                Every material traces back to your inventory. Plus a technical schematic.</div>
            </div>
        """, unsafe_allow_html=True)
    with a3:
        st.markdown("""
            <div style='background:#1E293B; border-radius:8px; padding:24px;
                        border-top:3px solid #10B981; text-align:center; min-height:220px;'>
              <div style='font-size:32px; margin-bottom:8px;'>&#128300;</div>
              <div style='color:#10B981; font-weight:bold; font-size:16px;'>GEMINI FLASH</div>
              <div style='color:#64748B; font-size:11px; letter-spacing:1px;
                          margin-bottom:12px;'>QUALITY INSPECTOR</div>
              <div style='color:#94A3B8; font-size:13px; line-height:1.5;'>
                Reviews the blueprint for safety, rates difficulty, estimates build time,
                and scores how well it actually used your inventory.</div>
            </div>
        """, unsafe_allow_html=True)

    # ── EXAMPLE OUTPUT ──
    st.markdown("""
        <div style='text-align:center; margin:40px 0 20px;'>
          <h2 style='color:#E2E8F0; font-size:28px;'>What You Get</h2>
          <p style='color:#64748B; font-size:14px;'>Real output from a real forge</p>
        </div>
    """, unsafe_allow_html=True)
    st.markdown("""
        <div style='max-width:900px; margin:0 auto;'>
          <div style='background:#1E293B; border:1px solid #334155; border-radius:8px;
                      padding:24px; margin-bottom:16px;'>
            <div style='color:#64748B; font-size:11px; letter-spacing:2px;
                        margin-bottom:4px;'>EXAMPLE INPUT</div>
            <div style='color:#F97316; font-size:14px; font-weight:bold;
                        margin-bottom:4px;'>PROJECT: Automated Cat Litter Robot</div>
            <div style='color:#94A3B8; font-size:13px;'>
              INVENTORY: Old treadmill with auto incline + Refurbished Dell OptiPlex computer</div>
          </div>
          <div style='background:#1E293B; border:1px solid #FF4500; border-radius:8px;
                      padding:24px;'>
            <div style='color:#FF4500; font-size:11px; letter-spacing:2px;
                        margin-bottom:12px;'>EXAMPLE OUTPUT</div>
            <div style='color:#E2E8F0; font-size:14px; line-height:1.7;'>
              <strong style='color:#3B82F6;'>&#9654; Drive Motor:</strong>
              Harvested from treadmill (1-2HP DC motor with variable speed control)<br>
              <strong style='color:#3B82F6;'>&#9654; Conveyor Belt:</strong>
              Repurposed treadmill wide belt, modified with sifting perforations<br>
              <strong style='color:#3B82F6;'>&#9654; Structural Frame:</strong>
              Cut and welded sections from treadmill steel frame<br>
              <strong style='color:#3B82F6;'>&#9654; Tilting Mechanism:</strong>
              Linear actuator harvested from treadmill auto-incline system<br>
              <strong style='color:#3B82F6;'>&#9654; Control Computer:</strong>
              Dell OptiPlex i5 programmed for cycle timing and automation<br>
              <strong style='color:#3B82F6;'>&#9654; Ventilation:</strong>
              Computer case fans repurposed for odor management<br>
              <strong style='color:#3B82F6;'>&#9654; Electronics Enclosure:</strong>
              Modified Dell computer chassis<br>
            </div>
            <div style='color:#10B981; font-size:13px; margin-top:12px; padding-top:12px;
                        border-top:1px solid #334155;'>
              &#10003; Technical SVG schematic included &nbsp;&nbsp;
              &#10003; Full assembly sequence &nbsp;&nbsp;
              &#10003; Safety notes &nbsp;&nbsp;
              &#10003; Testing procedures &nbsp;&nbsp;
              &#10003; Honest assessment &amp; gap-filler shopping list</div>
            <div style='color:#F59E0B; font-size:12px; margin-top:8px;'>
              Estimated commercial equivalent: $2,500 - $4,000</div>
          </div>
        </div>
    """, unsafe_allow_html=True)

    # ── FEATURES ──
    st.markdown("""
        <div style='max-width:900px; margin:30px auto; padding:0 20px;'>
          <div style='display:flex; gap:16px; flex-wrap:wrap; justify-content:center;'>
            <div style='background:#1E293B; border-radius:6px; padding:16px 20px;
                        flex:1; min-width:200px; max-width:280px; text-align:center;'>
              <div style='font-size:24px;'>&#128208;</div>
              <div style='color:#E2E8F0; font-size:13px; font-weight:bold; margin-top:4px;'>
                Technical Schematics</div>
              <div style='color:#64748B; font-size:11px; margin-top:4px;'>
                Auto-generated SVG engineering drawings with every blueprint</div>
            </div>
            <div style='background:#1E293B; border-radius:6px; padding:16px 20px;
                        flex:1; min-width:200px; max-width:280px; text-align:center;'>
              <div style='font-size:24px;'>&#128248;</div>
              <div style='color:#E2E8F0; font-size:13px; font-weight:bold; margin-top:4px;'>
                Equipment Scanner</div>
              <div style='color:#64748B; font-size:11px; margin-top:4px;'>
                Upload a photo. Gemini Vision identifies every component automatically.</div>
            </div>
            <div style='background:#1E293B; border-radius:6px; padding:16px 20px;
                        flex:1; min-width:200px; max-width:280px; text-align:center;'>
              <div style='font-size:24px;'>&#129504;</div>
              <div style='color:#E2E8F0; font-size:13px; font-weight:bold; margin-top:4px;'>
                Conception DNA</div>
              <div style='color:#64748B; font-size:11px; margin-top:4px;'>
                Every blueprint trains our AI. The more you build, the smarter it gets.</div>
            </div>
          </div>
        </div>
    """, unsafe_allow_html=True)

    # ── FREE TRIAL (above pricing — first thing visitors see after the pitch) ──
    st.markdown("---")
    st.markdown("""
        <div style='text-align:center; margin:20px 0 12px;'>
          <h2 style='color:#10B981; font-size:28px;'>Try 1 Free Build</h2>
          <p style='color:#64748B; font-size:14px;'>No credit card. Just your email. See what the Foundry can do.</p>
        </div>
    """, unsafe_allow_html=True)

    t1, t2, t3 = st.columns([1, 1.2, 1])
    with t2:
        trial_email = st.text_input("Email Address", placeholder="you@example.com",
                                    key="trial_email")
        email_optin = st.checkbox(
            "I agree to receive updates, tips, and new feature announcements from The Builder Foundry.",
            value=True, key="trial_optin"
        )
        st.markdown(
            "<div style='color:#475569; font-size:10px; margin-top:-8px; margin-bottom:8px;'>"
            "We respect your inbox. Unsubscribe anytime.</div>",
            unsafe_allow_html=True
        )
        if st.button("🚀 GET MY FREE BUILD", use_container_width=True):
            if not trial_email or "@" not in trial_email:
                st.warning("Enter a valid email address.")
            elif not email_optin:
                st.warning("Please agree to receive updates to activate your free trial.")
            else:
                with st.spinner("Creating your trial license..."):
                    result = api_post(
                        f"{AUTH_URL}/auth/trial",
                        {"email": trial_email.strip().lower(), "email_optin": True}
                    )
                    if isinstance(result, APIError):
                        if result.status == 409:
                            st.warning(result.detail)
                        elif result.status == 429:
                            st.warning("Too many trial requests. Please wait a few minutes.")
                        else:
                            st.error(result.detail)
                    else:
                        trial_key = result.get("key", "")
                        st.success(f"Your license key: **{trial_key}**")
                        st.info("Copy this key and use it to log in below. You have 1 free build and 7 days!")

    # ── PRICING (below free trial — for people ready to buy) ──
    st.markdown("""
        <div style='text-align:center; margin:40px 0 20px;'>
          <h2 style='color:#E2E8F0; font-size:28px;'>Want More Builds?</h2>
          <p style='color:#64748B; font-size:14px;'>Every tier includes full Round Table access</p>
        </div>
    """, unsafe_allow_html=True)

    p1, p2, p3 = st.columns(3)
    with p1:
        st.markdown("""
            <div style='background:#1E293B; padding:28px 20px; border-radius:8px;
                        border:1px solid #94A3B8; text-align:center;'>
              <div style='color:#94A3B8; font-size:12px; font-weight:bold;
                          letter-spacing:2px;'>STARTER</div>
              <div style='color:white; font-size:36px; font-weight:bold; margin:12px 0;'>
                $25<span style='font-size:16px; color:#94A3B8;'>/mo</span></div>
              <div style='color:#64748B; font-size:13px; margin-bottom:16px;'>
                25 blueprint builds per month<br>Full Round Table access<br>
                Technical schematics<br>Equipment scanner<br>Blueprint downloads</div>
            </div>
        """, unsafe_allow_html=True)
        st.link_button("⚡ GET STARTER", STRIPE_STARTER, use_container_width=True)
    with p2:
        st.markdown("""
            <div style='background:#1E293B; padding:28px 20px; border-radius:8px;
                        border:2px solid #FF4500; text-align:center;
                        box-shadow:0 0 20px rgba(255,69,0,0.15);'>
              <div style='color:#FF4500; font-size:12px; font-weight:bold;
                          letter-spacing:2px;'>PRO &#9733; MOST POPULAR</div>
              <div style='color:white; font-size:36px; font-weight:bold; margin:12px 0;'>
                $100<span style='font-size:16px; color:#94A3B8;'>/mo</span></div>
              <div style='color:#64748B; font-size:13px; margin-bottom:16px;'>
                100 blueprint builds per month<br>Everything in Starter<br>
                Priority processing<br>Conception DNA insights<br>Best value per build</div>
            </div>
        """, unsafe_allow_html=True)
        st.link_button("🔥 GET PRO", STRIPE_PRO, use_container_width=True)
    with p3:
        st.markdown("""
            <div style='background:#1E293B; padding:28px 20px; border-radius:8px;
                        border:1px solid #FFD700; text-align:center;'>
              <div style='color:#FFD700; font-size:12px; font-weight:bold;
                          letter-spacing:2px;'>MASTER</div>
              <div style='color:white; font-size:36px; font-weight:bold; margin:12px 0;'>
                $999<span style='font-size:16px; color:#94A3B8;'>/yr</span></div>
              <div style='color:#64748B; font-size:13px; margin-bottom:16px;'>
                Unlimited builds forever<br>Everything in Pro<br>
                Schools &amp; makerspaces<br>Direct Conception access<br>Annual lock-in savings</div>
            </div>
        """, unsafe_allow_html=True)
        st.link_button("👑 GET MASTER", STRIPE_MASTER, use_container_width=True)

    # ── THE STORY ──
    st.markdown("""
        <div style='max-width:700px; margin:40px auto; text-align:center; padding:0 20px;'>
          <h2 style='color:#E2E8F0; font-size:24px; margin-bottom:12px;'>Built From Scraps. Literally.</h2>
          <p style='color:#94A3B8; font-size:14px; line-height:1.8;'>
            The Builder Foundry was created by a self-taught developer who pieces together
            computers from parts and builds things from scrap. No CS degree. No funding.
            Just a passion for engineering and a refusal to stop learning.<br><br>
            This is Phase 1 of <strong style='color:#FF4500;'>Conception</strong> —
            an advanced AI being built to learn from every blueprint, protect families,
            run businesses, and eventually walk in a physical body.<br><br>
            Every blueprint you forge makes Conception smarter.</p>
        </div>
    """, unsafe_allow_html=True)

    # ── LOGIN ──
    st.markdown("---")
    st.markdown("""
        <div style='text-align:center; margin-bottom:12px;'>
          <h3 style='color:#FF4500;'>Already Have a License?</h3>
        </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        license_key = st.text_input("License Key", type="password",
                                    placeholder="BOB-XXXX-XXXX-XXXX")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("AUTHORIZE", use_container_width=True):
                if not license_key:
                    st.warning("Enter a license key.")
                else:
                    with st.spinner("Verifying credentials..."):
                        result = api_post(
                            f"{AUTH_URL}/verify-license",
                            {"license_key": license_key}
                        )
                        if isinstance(result, APIError):
                            if result.status == 429:
                                st.warning("Too many login attempts. Wait a few minutes.")
                            else:
                                st.error(result.detail)
                        else:
                            st.session_state.logged_in  = True
                            st.session_state.user_email = result["email"]
                            st.session_state.user_name  = result["name"]
                            st.session_state.tier       = result["tier"]
                            st.session_state.jwt_token  = result["token"]
                            st.rerun()
        with col_b:
            st.link_button("GET A LICENSE", STRIPE_STARTER, use_container_width=True)

    # ── FOOTER ──
    st.markdown("""
        <div style='text-align:center; padding:40px 0 20px; color:#475569; font-size:12px;'>
          AoC3P0 Systems &nbsp;|&nbsp; The Builder Foundry &nbsp;|&nbsp; Conception DNA Architecture<br>
          <span style='color:#334155;'>bobtherobotbuilder.com</span>
        </div>
    """, unsafe_allow_html=True)
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# LOGGED-IN APP
# ══════════════════════════════════════════════════════════════════════════════

st.markdown(FORGE_HEADER_HTML, unsafe_allow_html=True)

# Warm up AI service
if not st.session_state.services_warmed:
    ping_service(f"{AI_URL}/health", timeout=5.0)
    st.session_state.services_warmed = True


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    if os.path.exists("aoc3po_logo.png"):
        st.image("aoc3po_logo.png", width=200)

    st.markdown("---")
    tier_colors = {"master": "#FFD700", "pro": "#FF4500", "starter": "#94A3B8", "trial": "#10B981"}
    tc = tier_colors.get(st.session_state.tier, "#94A3B8")
    safe_name  = html.escape(st.session_state.user_name or "Unknown")
    safe_email = html.escape(st.session_state.user_email or "")
    safe_tier  = html.escape(st.session_state.tier.upper() if st.session_state.tier else "")
    st.markdown(f"""
        <div style='background:#1E293B; padding:12px; border-radius:6px;
                    border-left:4px solid {tc};'>
          <div style='color:#94A3B8; font-size:12px;'>OPERATOR</div>
          <div style='color:white; font-weight:bold;'>{safe_name}</div>
          <div style='color:#94A3B8; font-size:11px; margin-top:4px;'>
            {safe_email}</div>
          <div style='color:{tc}; font-size:11px; font-weight:bold; margin-top:4px;'>
            {safe_tier} CLEARANCE</div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    if st.button("⚙️  FORGE BLUEPRINT",   use_container_width=True):
        st.session_state.active_tab = "forge"
    if st.button("🗄️  CONCEPTION VAULT",  use_container_width=True):
        st.session_state.active_tab = "vault"
        st.session_state.vault_data = None
    if st.button("🔬  EQUIPMENT SCANNER", use_container_width=True):
        st.session_state.active_tab = "scanner"
    if st.button("🔧  FIELD MECHANIC",  use_container_width=True):
        st.session_state.active_tab = "mechanic"
    if st.button("🧠  CONCEPTION DNA",    use_container_width=True):
        st.session_state.active_tab = "conception"
    if st.button("💬  ARENA CHAT",        use_container_width=True):
        st.session_state.active_tab = "chat"

    st.markdown("---")

    # Quota meter
    q = api_get(f"{BILLING_URL}/billing/quota/{st.session_state.user_email}", timeout=5.0)
    if not isinstance(q, APIError):
        used  = q.get("build_count", 0)
        limit = q.get("build_limit", 25)
        pct   = min(used / max(limit, 1), 1.0)
        bar_color = "#FF4500" if pct > 0.8 else "#1D9E75"
        st.markdown(f"""
            <div style='font-size:11px; color:#94A3B8; margin-bottom:4px;'>
              BUILD QUOTA: {used} / {limit}</div>
            <div style='background:#1E293B; border-radius:4px; height:8px;'>
              <div style='background:{bar_color}; width:{pct*100:.0f}%;
                          height:8px; border-radius:4px;'></div>
            </div>
        """, unsafe_allow_html=True)
        if pct >= 1.0:
            st.error("Quota exhausted.")
            if st.session_state.tier == "trial":
                st.markdown("""
                    <div style='background:#1E293B; padding:12px; border-radius:6px;
                                border:1px solid #10B981; text-align:center; margin:8px 0;'>
                      <div style='color:#10B981; font-size:12px; font-weight:bold;'>
                        Your free build is used!</div>
                      <div style='color:#94A3B8; font-size:11px; margin-top:4px;'>
                        Upgrade to keep forging blueprints</div>
                    </div>
                """, unsafe_allow_html=True)
                st.link_button("GET STARTER $25/mo", STRIPE_STARTER, use_container_width=True)
            elif st.session_state.tier == "starter":
                st.link_button("UPGRADE TO PRO", STRIPE_PRO, use_container_width=True)
            elif st.session_state.tier == "pro":
                st.link_button("UPGRADE TO MASTER", STRIPE_MASTER, use_container_width=True)

    st.markdown("---")
    if st.button("LOGOUT", use_container_width=True):
        st.session_state.clear()
        for k, v in _defaults.items():
            st.session_state[k] = v
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB: FORGE BLUEPRINT
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.active_tab == "forge":
    st.markdown("### ACTIVE ENGINEERING AGENTS")
    cols = st.columns(3)
    with cols[0]:
        st.markdown("#### 🟠 GROK-3")
        st.caption("MECHANICAL / METALLURGY / HYDRAULICS")
        st.status("READY", state="complete")
    with cols[1]:
        st.markdown("#### 🔵 CLAUDE SONNET")
        st.caption("SYSTEMS ARCHITECTURE / EMBEDDED LOGIC")
        st.status("READY", state="complete")
    with cols[2]:
        st.markdown("#### 🟢 GEMINI 2.5 FLASH")
        st.caption("SYNTHESIS ENGINE / CONCEPTION VAULT")
        st.status("READY", state="complete")

    st.markdown("---")
    col_left, col_right = st.columns([2, 1])

    with col_left:
        project_name = st.text_input(
            "PROJECT IDENTIFIER",
            placeholder="e.g., Hydraulic Log Splitter, Cat Litter Robot, Go-Kart",
            max_chars=200
        )
        inventory_input = st.text_area(
            "INVENTORY MANIFEST / JUNK DESCRIPTION",
            placeholder="List every item you have — motors, machines, scrap metal, electronics...",
            height=260, max_chars=5000
        )

    with col_right:
        st.markdown("### BUILD PARAMETERS")
        detail_level = st.select_slider(
            "SPECIFICATION DEPTH",
            options=["Standard", "Industrial", "Experimental"]
        )
        st.markdown("&nbsp;")
        forge = st.button("🚀 FORGE BLUEPRINT", use_container_width=True)

        if forge:
            if not project_name or not project_name.strip():
                st.error("Project identifier is required.")
            elif not inventory_input or not inventory_input.strip():
                st.error("Inventory manifest is required.")
            elif len(inventory_input.strip()) < 10:
                st.error("Describe your inventory in more detail.")
            else:
                with st.spinner("Waking AI agents..."):
                    # Wake AI service if sleeping (Render cold-start)
                    awake = ping_service(f"{AI_URL}/health", timeout=10.0)
                    if not awake:
                        # Give it a second try — Render needs ~5-10s to wake
                        import time as _t
                        _t.sleep(3)
                        awake = ping_service(f"{AI_URL}/health", timeout=15.0)

                if not awake:
                    st.warning("AI service is starting up. Click FORGE again in 10 seconds.")
                else:
                    with st.spinner("Initiating Round Table protocols..."):
                        result = api_post(f"{AI_URL}/generate", {
                            "junk_desc":    inventory_input.strip(),
                            "project_type": project_name.strip(),
                            "detail_level": detail_level,
                            "user_email":   st.session_state.user_email,
                        }, timeout=60.0)

                        if isinstance(result, APIError):
                            if result.status == 429:
                                st.warning("Too many forge requests. Wait a few minutes.")
                            else:
                                st.error(result.detail)
                        else:
                            st.session_state.active_task = result.get("task_id")
                            st.session_state.forge_attempts = 0
                            st.success("Agents deployed. Blueprint forging...")

    # ── TASK POLLING ──
    if st.session_state.active_task:
        max_forge_attempts = 40  # 40 x 3s = 2 minutes max

        if st.session_state.forge_attempts >= max_forge_attempts:
            st.error("Forge timed out. The server may be under heavy load. Try again.")
            st.session_state.active_task = None
            st.session_state.forge_attempts = 0
        else:
            st.markdown("---")
            st.markdown("### CURRENT BUILD LOG")
            task_id = st.session_state.active_task

            result = api_get(f"{AI_URL}/generate/status/{task_id}", timeout=15.0)

            if isinstance(result, APIError):
                st.warning(f"Polling interrupted: {result.detail}")
                st.session_state.forge_attempts += 1
                time.sleep(5)
                st.rerun()
            else:
                state = result.get("status")

                if state == "complete":
                    st.balloons()
                    st.markdown("#### SYNTHESIS COMPLETE")

                    res       = result.get("result", {})
                    blueprint = res.get("content", "")
                    build_id  = res.get("build_id", "")
                    schematic = res.get("schematic_svg", "")

                    _show_schematic(schematic, build_id)
                    st.markdown(blueprint)
                    if build_id:
                        _download_buttons(build_id)
                    st.info("Blueprint archived in Conception DNA Vault.")
                    st.session_state.active_task = None
                    st.session_state.forge_attempts = 0

                elif state == "failed":
                    error_msg = result.get("error", "")
                    if "TimeLimitExceeded" in error_msg:
                        st.error("Blueprint timed out. Try Standard depth or a simpler project.")
                    else:
                        st.error("The Round Table failed to reach consensus. Check your manifest.")
                    st.session_state.active_task = None
                    st.session_state.forge_attempts = 0

                else:
                    msg = result.get("message", "Initializing Round Table protocols...")
                    elapsed = st.session_state.forge_attempts * 3
                    st.markdown(f"""
                        <div style='background:#1E293B; padding:16px; border-radius:8px;
                                    border-left:4px solid #FF4500; margin:8px 0;'>
                          <div style='color:#FF4500; font-size:13px; font-weight:bold;
                                      font-family:monospace; letter-spacing:1px;'>
                            ROUND TABLE ACTIVE ({elapsed}s)</div>
                          <div style='color:#E2E8F0; font-size:15px; margin-top:8px;'>
                            {html.escape(msg)}</div>
                        </div>
                    """, unsafe_allow_html=True)
                    st.session_state.forge_attempts += 1
                    time.sleep(3)
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB: CONCEPTION VAULT
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.active_tab == "vault":
    st.markdown("### CONCEPTION DNA VAULT")
    st.caption("All blueprints archived for Conception's learning and your reference.")

    if st.session_state.vault_data is None:
        with st.spinner("Loading your vault..."):
            result = api_get(f"{EXPORT_URL}/export/vault/{st.session_state.user_email}")
            st.session_state.vault_data = result if not isinstance(result, APIError) else {}

    vault  = st.session_state.vault_data
    builds = vault.get("builds", [])

    # Stats
    stats = api_get(f"{EXPORT_URL}/export/stats/{st.session_state.user_email}", timeout=8.0)
    if not isinstance(stats, APIError):
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Total Builds",     stats.get("total_builds", 0))
        s2.metric("Tokens Consumed",  f"{stats.get('total_tokens', 0):,}")
        s3.metric("Conception Ready", stats.get("conception_ready", 0))
        s4.metric("In Vault",         vault.get("count", 0))

    st.markdown("---")

    if not builds:
        st.info("No blueprints in your vault yet. Forge your first blueprint in the FORGE tab.")
    else:
        search = st.text_input("🔍 Search vault", placeholder="Filter by project name...")

        for b in builds:
            proj    = b.get("project_type", "Untitled")
            bid     = b.get("id")
            preview = b.get("blueprint_preview", "")
            tokens  = b.get("tokens_used", 0)
            date    = b.get("created_at", "")[:10] if b.get("created_at") else ""
            ready   = b.get("conception_ready", False)

            if search and search.lower() not in proj.lower():
                continue

            with st.expander(f"{'🧠' if ready else '📄'}  {proj}  —  {date}  |  {tokens:,} tokens"):
                st.caption(preview)
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("📖 LOAD FULL BLUEPRINT", key=f"load_{bid}"):
                        full = api_get(f"{EXPORT_URL}/export/blueprint/{bid}")
                        if not isinstance(full, APIError):
                            st.markdown("---")
                            st.markdown(full.get("blueprint", ""))
                        else:
                            st.error(f"Failed to load: {full.detail}")
                with col2:
                    data, ok = _cached_download(f"{EXPORT_URL}/export/download/{bid}?fmt=md")
                    if ok:
                        st.download_button("📥 .md", data=data,
                                          file_name=f"blueprint_{bid}.md",
                                          mime="text/markdown", key=f"dlmd_{bid}",
                                          use_container_width=True)
                with col3:
                    data, ok = _cached_download(f"{EXPORT_URL}/export/download/{bid}?fmt=txt")
                    if ok:
                        st.download_button("📥 .txt", data=data,
                                          file_name=f"blueprint_{bid}.txt",
                                          mime="text/plain", key=f"dltxt_{bid}",
                                          use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB: EQUIPMENT SCANNER
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.active_tab == "scanner":
    st.markdown("### EQUIPMENT SCANNER")
    st.caption("Upload a photo of any hardware. Gemini Vision identifies every component.")

    col_left, col_right = st.columns([1, 1])
    with col_left:
        uploaded = st.file_uploader("Upload equipment photo", type=["jpg", "jpeg", "png", "webp"])
        context  = st.text_input("Scan context", placeholder="e.g., underwater ROV motor assembly")

        if st.button("🔬 RUN SCAN", use_container_width=True):
            if not uploaded:
                st.error("Upload an image first.")
            else:
                with st.spinner("Compressing image for analysis..."):
                    # Compress image before sending — prevents 15MB iPhone photos
                    # from crashing the backend with 413 Payload Too Large
                    if _PIL_AVAILABLE:
                        img = Image.open(uploaded)
                        if img.mode in ("RGBA", "P"):
                            img = img.convert("RGB")
                        img.thumbnail((1024, 1024))
                        buf = _io.BytesIO()
                        img.save(buf, format="JPEG", quality=85)
                        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                        data_url = f"data:image/jpeg;base64,{b64}"
                    else:
                        # PIL not available — send raw (less safe but functional)
                        b64 = base64.b64encode(uploaded.read()).decode("utf-8")
                        mime = uploaded.type or "image/jpeg"
                        data_url = f"data:{mime};base64,{b64}"

                with st.spinner("Running computer vision analysis..."):
                    result = api_post(f"{WORKSHOP_URL}/scan/base64", {
                        "image_base64": data_url,
                        "user_email":   st.session_state.user_email,
                        "context":      context or "general hardware scan",
                    }, timeout=15.0)

                    if isinstance(result, APIError):
                        st.error(f"Scanner error: {result.detail}")
                    else:
                        st.session_state.scan_task = result.get("task_id")
                        st.session_state.scan_attempts = 0
                        st.rerun()

    with col_right:
        if st.session_state.scan_task:
            task_id = st.session_state.scan_task
            max_scan_attempts = 20  # 20 x 3s = 60s max wait

            if st.session_state.scan_attempts >= max_scan_attempts:
                st.error("Scan timed out. Try again or use a different image.")
                st.session_state.scan_task = None
                st.session_state.scan_attempts = 0
            else:
                # Show progress
                progress = st.session_state.scan_attempts / max_scan_attempts
                remaining = max_scan_attempts - st.session_state.scan_attempts
                st.progress(progress, text=f"Analyzing... ({remaining * 3}s remaining)")

                result = api_get(f"{WORKSHOP_URL}/task/status/{task_id}")

                if isinstance(result, APIError):
                    st.info("Waiting for scan result...")
                    st.session_state.scan_attempts += 1
                    time.sleep(3)
                    st.rerun()
                elif result.get("status") == "complete":
                    scan_data = result.get("result", {}).get("scan_result", {})
                    ident = scan_data.get("identification", {})
                    comps = scan_data.get("components", [])
                    st.success(f"**{ident.get('equipment_name', 'Unknown Equipment')}**")
                    st.markdown("#### Identified Components")
                    for c in comps:
                        st.markdown(f"- **{c.get('name', '?')}** x {c.get('quantity', '?')}")
                    st.session_state.scan_task = None
                    st.session_state.scan_attempts = 0
                elif result.get("status") == "failed":
                    st.error("Scan failed. Try another image.")
                    st.session_state.scan_task = None
                    st.session_state.scan_attempts = 0
                else:
                    st.info("Gemini Vision analyzing... please wait.")
                    st.session_state.scan_attempts += 1
                    time.sleep(3)
                    st.rerun()

    # Scan history
    st.markdown("---")
    st.markdown("#### Past Scans")
    scans = api_get(f"{EXPORT_URL}/export/scan/{st.session_state.user_email}", timeout=8.0)
    if not isinstance(scans, APIError):
        for s in scans.get("scans", [])[:10]:
            with st.expander(f"🔩 {s.get('equipment_name','Unknown')} — {str(s.get('created_at',''))[:10]}"):
                for comp in s.get("scan_result", {}).get("components", []):
                    st.markdown(f"- {comp.get('name','?')} x {comp.get('quantity','?')}")
    else:
        st.caption("Scan history unavailable.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: CONCEPTION DNA
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.active_tab == "conception":
    st.markdown("### CONCEPTION DNA — LEARNING CORE")
    st.caption("Conception learns from every blueprint forged. The more you build, the smarter he gets.")

    stats = api_get(f"{EXPORT_URL}/export/stats/{st.session_state.user_email}", timeout=8.0)

    if isinstance(stats, APIError):
        st.error(f"Could not load Conception data: {stats.detail}")
    else:
        total  = stats.get("total_builds", 0)
        tokens = stats.get("total_tokens", 0)
        ready  = stats.get("conception_ready", 0)
        pct    = round((ready / max(total, 1)) * 100, 1)

        c1, c2, c3 = st.columns(3)
        c1.metric("Blueprints Absorbed", total)
        c2.metric("Tokens Processed",    f"{tokens:,}")
        c3.metric("Conception Ready",    f"{pct}%")

        st.markdown("---")
        st.markdown("#### CONCEPTION KNOWLEDGE INDEX")
        knowledge_pct = min(total / 500, 1.0)
        st.progress(knowledge_pct,
                    text=f"{total} / 500 blueprints — {knowledge_pct*100:.1f}% knowledge saturation")

        st.markdown("#### TOP ENGINEERING DOMAINS LEARNED")
        top = stats.get("top_projects", [])
        if top:
            for p in top:
                proj  = p.get("project", "Unknown")
                count = p.get("count", 0)
                bar   = min(count / max(top[0].get("count", 1), 1), 1.0)
                st.markdown(f"**{proj}**")
                st.progress(bar, text=f"{count} blueprints")
        else:
            st.info("No blueprints forged yet. Start building to train Conception.")

        st.markdown("---")
        st.markdown("#### CONCEPTION STATUS")
        if total == 0:
            st.warning("Offline — No training data yet.")
        elif total < 10:
            st.warning(f"Initializing — {total} blueprints absorbed. Keep forging.")
        elif total < 50:
            st.info(f"Learning — {total} blueprints in memory.")
        elif total < 200:
            st.success(f"Active — {total} blueprints. Conception is developing.")
        else:
            st.success(f"ADVANCED — {total} blueprints. Conception is growing rapidly.")

        st.markdown("---")
        st.markdown("#### NEXT MILESTONE")
        milestones = [10, 50, 100, 200, 500]
        next_m = next((m for m in milestones if m > total), 500)
        st.info(f"**{next_m - total} more blueprints** until the next evolution milestone ({next_m} total).")


# ══════════════════════════════════════════════════════════════════════════════
# TAB: FIELD MECHANIC
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.active_tab == "mechanic":
    st.markdown("### 🔧 FIELD MECHANIC — AI REPAIR ASSISTANT")
    st.markdown("""
        <div style='background:#1E293B; padding:16px; border-radius:8px;
                    border-left:4px solid #F59E0B; margin-bottom:16px;'>
          <div style='color:#F59E0B; font-size:13px; font-weight:bold;'>
            BUILT FOR THE FIELD</div>
          <div style='color:#94A3B8; font-size:13px; margin-top:4px;'>
            Stranded on the ocean? Remote job site? No parts store for 100 miles?<br>
            Tell us your engine, the problem, and what tools you have. We'll give you
            a step-by-step repair procedure using ONLY what's available — plus an
            emergency jury-rig to get you home safe.</div>
        </div>
    """, unsafe_allow_html=True)

    col_left, col_right = st.columns([2, 1])

    with col_left:
        # Row 1: Vehicle + Engine side by side
        r1a, r1b = st.columns(2)
        with r1a:
            vehicle_input = st.text_input(
                "YEAR / MAKE / MODEL",
                placeholder="e.g., 2014 Honda Civic, 42ft Hatteras, John Deere 8400R",
                max_chars=200
            )
        with r1b:
            engine_input = st.text_input(
                "ENGINE / POWERPLANT",
                placeholder="e.g., Cummins 6BTA 5.9, K24A2, CAT C7, Yanmar 6LY",
                max_chars=200
            )

        # Row 2: Mileage + Environment side by side
        r2a, r2b = st.columns(2)
        with r2a:
            mileage_input = st.text_input(
                "MILEAGE / HOURS",
                placeholder="e.g., 142,000 miles, 3,200 hours, unknown",
                max_chars=100
            )
        with r2b:
            environment = st.selectbox(
                "ENVIRONMENT",
                ["Marine / Boat", "Automotive", "Heavy Equipment", "Agricultural",
                 "Generator / Stationary", "HVAC / Refrigeration", "Motorcycle / Powersport", "Other"]
            )

        symptom_input = st.text_area(
            "SYMPTOM / FAULT CODE / WHAT'S WRONG",
            placeholder=(
                "Describe exactly what's happening — be specific...\n"
                "e.g., Low oil pressure alarm at idle, clears above 1200 RPM.\n"
                "Black smoke under load. P0171 lean code. Engine cranks but won't fire.\n"
                "Overheating at 2000 RPM. Raw water pump leaking from weep hole.\n"
                "Grinding noise from starter. Transmission slipping in 3rd gear."
            ),
            height=150, max_chars=3000
        )
        tried_input = st.text_area(
            "WHAT HAVE YOU ALREADY TRIED?",
            placeholder=(
                "This prevents the AI from suggesting things you've already ruled out...\n"
                "e.g., Changed oil and filter — no change. Checked coolant level — full.\n"
                "Swapped fuel filter — same problem. Tested batteries — 12.6V each."
            ),
            height=100, max_chars=2000
        )
        tools_input = st.text_area(
            "TOOLS & SPARE PARTS ON HAND",
            placeholder=(
                "List what you physically have available RIGHT NOW...\n"
                "e.g., Basic hand tools, multimeter, spare oil filter, 15W-40 oil,\n"
                "marine sealant, zip ties, hose clamps, JB Weld, spare impeller, heat gun"
            ),
            height=100, max_chars=3000
        )

    with col_right:
        st.markdown("### REPAIR PARAMETERS")
        mech_detail = st.select_slider(
            "DIAGNOSTIC DEPTH",
            options=["Standard", "Industrial", "Experimental"]
        )
        st.markdown("&nbsp;")

        st.markdown("""
            <div style='background:#1E293B; padding:12px; border-radius:6px;
                        border:1px solid #334155; margin-bottom:12px;'>
              <div style='color:#F59E0B; font-size:11px; font-weight:bold;
                          letter-spacing:1px;'>WHAT YOU GET</div>
              <div style='color:#94A3B8; font-size:12px; margin-top:6px; line-height:1.6;'>
                &#9654; Diagnostic flowchart<br>
                &#9654; Step-by-step field repair<br>
                &#9654; Torque specs &amp; measurements<br>
                &#9654; Emergency jury-rig option<br>
                &#9654; "Do NOT do this" warnings<br>
                &#9654; Parts list for when you reach port</div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("""
            <div style='background:#1E293B; padding:12px; border-radius:6px;
                        border:1px solid #F59E0B; margin-bottom:12px;'>
              <div style='color:#F59E0B; font-size:11px; font-weight:bold;
                          letter-spacing:1px;'>WORKS FOR EVERYTHING</div>
              <div style='color:#94A3B8; font-size:12px; margin-top:6px; line-height:1.6;'>
                Marine diesels &#9679; Cars &amp; trucks<br>
                Heavy equipment &#9679; Tractors<br>
                Generators &#9679; HVAC systems<br>
                Motorcycles &#9679; Anything with an engine</div>
            </div>
        """, unsafe_allow_html=True)

        diagnose = st.button("🔧 DIAGNOSE & REPAIR", use_container_width=True)

        if diagnose:
            if not vehicle_input.strip() and not engine_input.strip():
                st.error("Enter a vehicle or engine — we need at least one to diagnose.")
            elif not symptom_input or not symptom_input.strip():
                st.error("Describe the symptom or fault.")
            elif len(symptom_input.strip()) < 10:
                st.error("Give more detail about the problem.")
            else:
                # Build rich context string from all fields
                vehicle_str = vehicle_input.strip() or "Not specified"
                engine_str = engine_input.strip() or "Not specified"
                mileage_str = mileage_input.strip() or "Not specified"
                tried_str = tried_input.strip() if tried_input else "Nothing yet"

                project_desc = (
                    f"VEHICLE: {vehicle_str}\n"
                    f"ENGINE: {engine_str}\n"
                    f"MILEAGE/HOURS: {mileage_str}\n"
                    f"ENVIRONMENT: {environment}\n"
                    f"SYMPTOM: {symptom_input.strip()}\n"
                    f"ALREADY TRIED: {tried_str}"
                )
                tools_desc = tools_input.strip() if tools_input else "Basic hand tools only"

                with st.spinner("Waking diagnostic agents..."):
                    awake = ping_service(f"{AI_URL}/health", timeout=10.0)
                    if not awake:
                        import time as _t
                        _t.sleep(3)
                        awake = ping_service(f"{AI_URL}/health", timeout=15.0)

                if not awake:
                    st.warning("AI service is starting up. Click DIAGNOSE again in 10 seconds.")
                else:
                    with st.spinner("Initiating diagnostic protocols..."):
                        result = api_post(f"{AI_URL}/generate", {
                            "junk_desc":    tools_desc,
                            "project_type": project_desc,
                            "detail_level": mech_detail,
                            "user_email":   st.session_state.user_email,
                            "mode":         "mechanic",
                        }, timeout=60.0)

                        if isinstance(result, APIError):
                            if result.status == 429:
                                st.warning("Too many requests. Wait a few minutes.")
                            else:
                                st.error(result.detail)
                        else:
                            st.session_state.mechanic_task = result.get("task_id")
                            st.session_state.mechanic_attempts = 0
                            st.success("Diagnostic agents deployed...")

    # ── MECHANIC TASK POLLING ──
    if st.session_state.mechanic_task:
        max_mech_attempts = 40

        if st.session_state.mechanic_attempts >= max_mech_attempts:
            st.error("Diagnosis timed out. Try again or simplify the symptoms.")
            st.session_state.mechanic_task = None
            st.session_state.mechanic_attempts = 0
        else:
            st.markdown("---")
            st.markdown("### DIAGNOSTIC LOG")
            task_id = st.session_state.mechanic_task

            result = api_get(f"{AI_URL}/generate/status/{task_id}", timeout=15.0)

            if isinstance(result, APIError):
                st.warning(f"Polling interrupted: {result.detail}")
                st.session_state.mechanic_attempts += 1
                time.sleep(5)
                st.rerun()
            else:
                state = result.get("status")

                if state == "complete":
                    st.balloons()
                    st.markdown("#### REPAIR PROCEDURE READY")

                    res       = result.get("result", {})
                    procedure = res.get("content", "")
                    build_id  = res.get("build_id", "")

                    st.markdown(procedure)
                    if build_id:
                        _download_buttons(build_id, key_suffix="_mech")
                    st.info("Repair procedure archived in Conception DNA Vault.")
                    st.session_state.mechanic_task = None
                    st.session_state.mechanic_attempts = 0

                elif state == "failed":
                    st.error("Diagnostic agents could not reach consensus. Try simplifying the symptoms.")
                    st.session_state.mechanic_task = None
                    st.session_state.mechanic_attempts = 0

                else:
                    msg = result.get("message", "Analyzing engine data...")
                    elapsed = st.session_state.mechanic_attempts * 3
                    st.markdown(f"""
                        <div style='background:#1E293B; padding:16px; border-radius:8px;
                                    border-left:4px solid #F59E0B; margin:8px 0;'>
                          <div style='color:#F59E0B; font-size:13px; font-weight:bold;
                                      font-family:monospace; letter-spacing:1px;'>
                            DIAGNOSTIC ACTIVE ({elapsed}s)</div>
                          <div style='color:#E2E8F0; font-size:15px; margin-top:8px;'>
                            {html.escape(msg)}</div>
                        </div>
                    """, unsafe_allow_html=True)
                    st.session_state.mechanic_attempts += 1
                    time.sleep(3)
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB: ARENA CHAT
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.active_tab == "chat":
    st.markdown("### FOUNDRY ARENA CHAT")
    st.caption("Live global channel. All operators. All tiers.")

    with st.form("chat_form", clear_on_submit=True):
        msg_text = st.text_input("Message", placeholder="Speak, operator...")
        sent = st.form_submit_button("TRANSMIT", use_container_width=True)
        if sent and msg_text.strip():
            api_post(f"{AI_URL}/arena/chat/send", {
                "user_name": st.session_state.user_name or "Anonymous",
                "tier":      st.session_state.tier,
                "message":   msg_text.strip(),
            }, timeout=5.0)

    messages = api_get(f"{AI_URL}/arena/chat/recent", timeout=5.0)
    if not isinstance(messages, APIError):
        tier_badge = {"master": "🥇", "pro": "🟠", "starter": "⚪", "trial": "🟢"}
        for m in messages:
            badge = tier_badge.get(m.get("tier", ""), "⚪")
            st.markdown(
                f"`{m.get('time', '')}` {badge} **{m.get('user', '?')}** — {m.get('text', '')}",
                unsafe_allow_html=False
            )
    else:
        st.caption("Chat unavailable.")

    if st.button("🔄 REFRESH", use_container_width=True):
        st.rerun()


# ── FOOTER ─────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption("AoC3P0 Systems | The Builder Foundry | Conception DNA Architecture")

# ── GLOBAL ERROR DISPLAY ──────────────────────────────────────────────────────
# If any unhandled exception occurred during rendering, Streamlit shows its own
# error widget. This is a safety net for the developer — in production, each
# section already handles errors via isinstance(result, APIError) checks.
# To see raw exceptions during development, set: SHOW_DEBUG=1 in env vars.
if os.getenv("SHOW_DEBUG"):
    st.markdown("---")
    with st.expander("🔧 DEBUG INFO"):
        st.json({
            "session_state": {k: str(v)[:100] for k, v in st.session_state.items()},
            "services": {
                "auth": AUTH_URL,
                "ai": AI_URL,
                "workshop": WORKSHOP_URL,
                "export": EXPORT_URL,
                "billing": BILLING_URL,
            },
        })
