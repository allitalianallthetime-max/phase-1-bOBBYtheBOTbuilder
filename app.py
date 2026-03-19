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
# Token packs (one-time purchase)
STRIPE_SPARK    = os.getenv("STRIPE_URL_SPARK",     "#")
STRIPE_BUILDER  = os.getenv("STRIPE_URL_BUILDER",   "#")
STRIPE_FOUNDRY  = os.getenv("STRIPE_URL_FOUNDRY",   "#")
STRIPE_SHOPPASS = os.getenv("STRIPE_URL_SHOPPASS",   "#")
# Subscriptions
STRIPE_PRO_SUB    = os.getenv("STRIPE_URL_PRO_SUB",     "#")
STRIPE_MASTER_SUB = os.getenv("STRIPE_URL_MASTER_SUB",  "#")

# ── APPLY THEME ────────────────────────────────────────────────────────────────
if BUILDER_CSS:
    st.markdown(BUILDER_CSS, unsafe_allow_html=True)

# ── SESSION STATE ──────────────────────────────────────────────────────────────
_defaults = {
    "logged_in": False, "user_email": "", "user_name": "", "tier": "",
    "jwt_token": "", "active_task": None, "vault_data": None,
    "active_tab": "forge", "scan_task": None, "scan_attempts": 0,
    "forge_attempts": 0, "mechanic_task": None, "mechanic_attempts": 0,
    "quote_task": None, "quote_attempts": 0,
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
        <div style='text-align:center; padding:30px 20px 10px;'>
          <h1 style='color:#FF4500; font-size:48px; margin:0; letter-spacing:3px;
                      text-shadow: 0 0 30px rgba(255,69,0,0.3);'>
            THE BUILDER FOUNDRY</h1>
          <p style='color:#E2E8F0; font-size:22px; margin-top:12px; max-width:750px;
                    margin-left:auto; margin-right:auto; line-height:1.5;'>
            Three AI agents. Real web research. Real results.<br>
            <span style='color:#94A3B8; font-size:16px;'>
              Build from scrap. Diagnose any engine. Verify any repair quote.</span></p>
        </div>
    """, unsafe_allow_html=True)

    if os.path.exists("hero_banner.jpg"):
        st.image("hero_banner.jpg", use_container_width=True)

    # ── THREE MODES ──
    st.markdown("""
        <div style='text-align:center; margin:30px 0 20px;'>
          <h2 style='color:#E2E8F0; font-size:30px;'>One Platform. Three Superpowers.</h2>
        </div>
    """, unsafe_allow_html=True)

    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown("""
            <div style='background:linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
                        border-radius:12px; padding:28px 20px; border:1px solid #FF4500;
                        text-align:center; min-height:320px;
                        box-shadow: 0 4px 20px rgba(255,69,0,0.1);'>
              <div style='font-size:48px; margin-bottom:12px;'>&#9881;&#65039;</div>
              <div style='color:#FF4500; font-weight:bold; font-size:20px;
                          letter-spacing:1px;'>BLUEPRINT FORGE</div>
              <div style='color:#64748B; font-size:11px; letter-spacing:2px;
                          margin-bottom:16px;'>FOR BUILDERS &amp; MAKERS</div>
              <div style='color:#CBD5E1; font-size:14px; line-height:1.7;'>
                Tell us what junk you have and what you want to build.
                Three AI agents analyze every component, search real maker projects,
                and generate a complete blueprint with technical schematics — using
                <strong style='color:#FF4500;'>only your parts</strong>.</div>
              <div style='color:#F59E0B; font-size:12px; margin-top:16px;
                          border-top:1px solid #334155; padding-top:12px;'>
                Robots &#8226; Go-karts &#8226; Solar rigs &#8226; Shop tools
                &#8226; Home automation &#8226; Anything</div>
            </div>
        """, unsafe_allow_html=True)
    with m2:
        st.markdown("""
            <div style='background:linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
                        border-radius:12px; padding:28px 20px; border:1px solid #10B981;
                        text-align:center; min-height:320px;
                        box-shadow: 0 4px 20px rgba(16,185,129,0.1);'>
              <div style='font-size:48px; margin-bottom:12px;'>&#128295;</div>
              <div style='color:#10B981; font-weight:bold; font-size:20px;
                          letter-spacing:1px;'>FIELD MECHANIC</div>
              <div style='color:#64748B; font-size:11px; letter-spacing:2px;
                          margin-bottom:16px;'>FOR MECHANICS &amp; TECHS</div>
              <div style='color:#CBD5E1; font-size:14px; line-height:1.7;'>
                Enter your vehicle, engine, symptoms, and tools on hand.
                AI diagnoses the problem, searches real forums for verified fixes,
                finds TSBs and recalls, and writes a step-by-step repair procedure
                with <strong style='color:#10B981;'>real torque specs and part prices</strong>.</div>
              <div style='color:#F59E0B; font-size:12px; margin-top:16px;
                          border-top:1px solid #334155; padding-top:12px;'>
                Marine &#8226; Automotive &#8226; Heavy equipment
                &#8226; Agricultural &#8226; Any engine</div>
            </div>
        """, unsafe_allow_html=True)
    with m3:
        st.markdown("""
            <div style='background:linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
                        border-radius:12px; padding:28px 20px; border:1px solid #3B82F6;
                        text-align:center; min-height:320px;
                        box-shadow: 0 4px 20px rgba(59,130,246,0.1);'>
              <div style='font-size:48px; margin-bottom:12px;'>&#128737;&#65039;</div>
              <div style='color:#3B82F6; font-weight:bold; font-size:20px;
                          letter-spacing:1px;'>QUOTE CHECKER</div>
              <div style='color:#64748B; font-size:11px; letter-spacing:2px;
                          margin-bottom:16px;'>FOR EVERY VEHICLE OWNER</div>
              <div style='color:#CBD5E1; font-size:14px; line-height:1.7;'>
                Got a repair quote? We check it against real repair data,
                search for recalls and extended warranties, and tell you
                if the price is <strong style='color:#3B82F6;'>fair or a ripoff</strong>.
                Know what to say before you go back to the shop.</div>
              <div style='color:#F59E0B; font-size:12px; margin-top:16px;
                          border-top:1px solid #334155; padding-top:12px;'>
                Cars &#8226; Trucks &#8226; Boats &#8226; RVs
                &#8226; Any vehicle &#8226; Any repair</div>
            </div>
        """, unsafe_allow_html=True)

    # ── ALLDATA KILLER STAT ──
    st.markdown("""
        <div style='max-width:900px; margin:30px auto; padding:20px;
                    background:linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                    border-radius:12px; border:1px solid #334155; text-align:center;'>
          <div style='display:flex; justify-content:center; gap:40px; flex-wrap:wrap;'>
            <div>
              <div style='color:#EF4444; font-size:36px; font-weight:bold;'>$199/mo</div>
              <div style='color:#64748B; font-size:13px;'>AllData charges this.<br>Static data. Annual lock-in.</div>
            </div>
            <div style='border-left:1px solid #334155; padding-left:40px;'>
              <div style='color:#10B981; font-size:36px; font-weight:bold;'>$3.33</div>
              <div style='color:#64748B; font-size:13px;'>We charge per diagnosis.<br>AI-powered. Live web research.</div>
            </div>
            <div style='border-left:1px solid #334155; padding-left:40px;'>
              <div style='color:#F59E0B; font-size:36px; font-weight:bold;'>3</div>
              <div style='color:#64748B; font-size:13px;'>AI agents working<br>on YOUR specific problem.</div>
            </div>
          </div>
        </div>
    """, unsafe_allow_html=True)

    # ── FIELD MECHANIC DEEP DIVE ──
    st.markdown("""
        <div style='text-align:center; margin:40px 0 20px;'>
          <h2 style='color:#10B981; font-size:28px;'>Field Mechanic — Your AI Repair Crew</h2>
          <p style='color:#94A3B8; font-size:15px; max-width:700px; margin:8px auto;'>
            Stranded on a boat? Stuck on a job site? Dead engine and no cell signal to Google?
            Run a diagnosis with the tools you have. Get a real repair procedure — not generic advice.</p>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div style='max-width:900px; margin:0 auto;'>
          <div style='display:flex; gap:12px; flex-wrap:wrap; justify-content:center;'>
            <div style='background:#1E293B; border-radius:8px; padding:16px; flex:1;
                        min-width:250px; max-width:280px; border-left:3px solid #10B981;'>
              <div style='color:#10B981; font-size:13px; font-weight:bold;'>&#9654; Diagnostic Flowchart</div>
              <div style='color:#94A3B8; font-size:12px; margin-top:4px;'>
                Failure tree analysis — "if X, check Y. If Y fails, it's Z."</div>
            </div>
            <div style='background:#1E293B; border-radius:8px; padding:16px; flex:1;
                        min-width:250px; max-width:280px; border-left:3px solid #10B981;'>
              <div style='color:#10B981; font-size:13px; font-weight:bold;'>&#9654; Step-by-Step Repair</div>
              <div style='color:#94A3B8; font-size:12px; margin-top:4px;'>
                Written for YOUR tools and parts — not a shop manual.</div>
            </div>
            <div style='background:#1E293B; border-radius:8px; padding:16px; flex:1;
                        min-width:250px; max-width:280px; border-left:3px solid #10B981;'>
              <div style='color:#10B981; font-size:13px; font-weight:bold;'>&#9654; Torque Specs &amp; Measurements</div>
              <div style='color:#94A3B8; font-size:12px; margin-top:4px;'>
                Real specs for the exact engine. Marked [KNOWN] or [EST].</div>
            </div>
            <div style='background:#1E293B; border-radius:8px; padding:16px; flex:1;
                        min-width:250px; max-width:280px; border-left:3px solid #F59E0B;'>
              <div style='color:#F59E0B; font-size:13px; font-weight:bold;'>&#9654; Emergency Jury-Rig</div>
              <div style='color:#94A3B8; font-size:12px; margin-top:4px;'>
                Temp fix to get home safe. Includes risks of the workaround.</div>
            </div>
            <div style='background:#1E293B; border-radius:8px; padding:16px; flex:1;
                        min-width:250px; max-width:280px; border-left:3px solid #EF4444;'>
              <div style='color:#EF4444; font-size:13px; font-weight:bold;'>&#9654; "Do NOT Do This"</div>
              <div style='color:#94A3B8; font-size:12px; margin-top:4px;'>
                Common mistakes that make the problem WORSE.</div>
            </div>
            <div style='background:#1E293B; border-radius:8px; padding:16px; flex:1;
                        min-width:250px; max-width:280px; border-left:3px solid #3B82F6;'>
              <div style='color:#3B82F6; font-size:13px; font-weight:bold;'>&#9654; Real Parts &amp; Prices</div>
              <div style='color:#94A3B8; font-size:12px; margin-top:4px;'>
                Part numbers + live pricing from RockAuto, Amazon, dealer sites.</div>
            </div>
            <div style='background:#1E293B; border-radius:8px; padding:16px; flex:1;
                        min-width:250px; max-width:280px; border-left:3px solid #A855F7;'>
              <div style='color:#A855F7; font-size:13px; font-weight:bold;'>&#9654; Forum Fixes &amp; TSBs</div>
              <div style='color:#94A3B8; font-size:12px; margin-top:4px;'>
                Gemini searches real mechanic forums and finds verified fixes.</div>
            </div>
            <div style='background:#1E293B; border-radius:8px; padding:16px; flex:1;
                        min-width:250px; max-width:280px; border-left:3px solid #06B6D4;'>
              <div style='color:#06B6D4; font-size:13px; font-weight:bold;'>&#9654; YouTube Walkthroughs</div>
              <div style='color:#94A3B8; font-size:12px; margin-top:4px;'>
                Links to actual repair videos for your specific engine and problem.</div>
            </div>
          </div>
        </div>
    """, unsafe_allow_html=True)

    # ── QUOTE CHECKER PITCH ──
    st.markdown("""
        <div style='text-align:center; margin:40px 0 20px;'>
          <h2 style='color:#3B82F6; font-size:28px;'>Quote Checker — Stop Overpaying For Repairs</h2>
          <p style='color:#94A3B8; font-size:15px; max-width:700px; margin:8px auto;'>
            Your mechanic says $2,400 for an AC repair. Is that fair? Or are you getting robbed?
            We check it in 60 seconds for $3.33.</p>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div style='max-width:800px; margin:0 auto;'>
          <div style='background:linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
                      border-radius:12px; padding:28px; border:1px solid #3B82F6;'>
            <div style='display:flex; gap:24px; flex-wrap:wrap; justify-content:center;'>
              <div style='flex:1; min-width:280px;'>
                <div style='color:#EF4444; font-size:11px; font-weight:bold;
                            letter-spacing:2px; margin-bottom:8px;'>THE QUOTE</div>
                <div style='color:#E2E8F0; font-size:20px;'>2022 Toyota Highlander — AC Repair</div>
                <div style='color:#EF4444; font-size:32px; font-weight:bold; margin:4px 0;'>$2,400</div>
              </div>
              <div style='flex:1; min-width:280px;'>
                <div style='color:#10B981; font-size:11px; font-weight:bold;
                            letter-spacing:2px; margin-bottom:8px;'>OUR ANALYSIS</div>
                <div style='color:#10B981; font-size:16px; font-weight:bold;'>
                  &#128680; THIS QUOTE IS HIGH</div>
                <div style='color:#E2E8F0; font-size:15px; margin-top:4px;'>
                  Fair range: <strong style='color:#10B981;'>$650 — $950</strong></div>
                <div style='color:#F59E0B; font-size:14px; margin-top:8px;'>
                  &#9888;&#65039; Toyota covers this free under 60K miles!</div>
                <div style='color:#94A3B8; font-size:13px; margin-top:8px; line-height:1.6;'>
                  &#10003; Recall &amp; warranty check<br>
                  &#10003; Fair cost breakdown with real part prices<br>
                  &#10003; What to say when you call the shop back<br>
                  &#10003; NHTSA complaint data (187 complaints filed)</div>
              </div>
            </div>
          </div>
        </div>
    """, unsafe_allow_html=True)

    # ── HOW THE AI WORKS ──
    st.markdown("""
        <div style='text-align:center; margin:40px 0 20px;'>
          <h2 style='color:#E2E8F0; font-size:28px;'>The AI Round Table</h2>
          <p style='color:#64748B; font-size:15px;'>Three agents. Working in parallel. Real web research.</p>
        </div>
    """, unsafe_allow_html=True)

    a1, a2, a3 = st.columns(3)
    with a1:
        st.markdown("""
            <div style='background:linear-gradient(180deg, #1E293B 0%, #0F172A 100%);
                        border-radius:12px; padding:24px;
                        border-top:3px solid #F97316; text-align:center; min-height:280px;'>
              <div style='font-size:36px; margin-bottom:8px;'>&#129504;</div>
              <div style='color:#F97316; font-weight:bold; font-size:18px;'>GROK-4.2</div>
              <div style='color:#64748B; font-size:11px; letter-spacing:1px;
                          margin-bottom:12px;'>THE BRAIN</div>
              <div style='color:#94A3B8; font-size:13px; line-height:1.6;'>
                Deep technical analysis. Failure tree diagnosis. Full spec sheets
                for your exact engine. Cross-references what you already tried.
                Identifies every harvestable component from your junk.</div>
              <div style='color:#F97316; font-size:11px; margin-top:12px;
                          padding-top:8px; border-top:1px solid #334155;'>
                Powered by xAI Grok 4.2</div>
            </div>
        """, unsafe_allow_html=True)
    with a2:
        st.markdown("""
            <div style='background:linear-gradient(180deg, #1E293B 0%, #0F172A 100%);
                        border-radius:12px; padding:24px;
                        border-top:3px solid #10B981; text-align:center; min-height:280px;'>
              <div style='font-size:36px; margin-bottom:8px;'>&#128269;</div>
              <div style='color:#10B981; font-weight:bold; font-size:18px;'>GEMINI 2.5</div>
              <div style='color:#64748B; font-size:11px; letter-spacing:1px;
                          margin-bottom:12px;'>THE SEARCHER</div>
              <div style='color:#94A3B8; font-size:13px; line-height:1.6;'>
                Searches the ACTUAL web — forums, TSBs, NHTSA recalls,
                YouTube repair videos, parts pricing from RockAuto and Amazon,
                Instructables projects, and real mechanic-verified fixes.</div>
              <div style='color:#10B981; font-size:11px; margin-top:12px;
                          padding-top:8px; border-top:1px solid #334155;'>
                Google Search Grounding + Gemini Flash</div>
            </div>
        """, unsafe_allow_html=True)
    with a3:
        st.markdown("""
            <div style='background:linear-gradient(180deg, #1E293B 0%, #0F172A 100%);
                        border-radius:12px; padding:24px;
                        border-top:3px solid #3B82F6; text-align:center; min-height:280px;'>
              <div style='font-size:36px; margin-bottom:8px;'>&#128221;</div>
              <div style='color:#3B82F6; font-weight:bold; font-size:18px;'>CLAUDE SONNET</div>
              <div style='color:#64748B; font-size:11px; letter-spacing:1px;
                          margin-bottom:12px;'>THE WRITER</div>
              <div style='color:#94A3B8; font-size:13px; line-height:1.6;'>
                Synthesizes everything from Grok and Gemini into a complete
                document — blueprints with schematics, repair procedures with
                torque specs, or quote analyses with fair pricing breakdowns.</div>
              <div style='color:#3B82F6; font-size:11px; margin-top:12px;
                          padding-top:8px; border-top:1px solid #334155;'>
                Anthropic Claude Sonnet 4</div>
            </div>
        """, unsafe_allow_html=True)

    # ── FEATURES GRID ──
    st.markdown("""
        <div style='text-align:center; margin:40px 0 20px;'>
          <h2 style='color:#E2E8F0; font-size:28px;'>Everything Included</h2>
        </div>
        <div style='max-width:900px; margin:0 auto; padding:0 20px;'>
          <div style='display:flex; gap:16px; flex-wrap:wrap; justify-content:center;'>
            <div style='background:#1E293B; border-radius:8px; padding:20px;
                        flex:1; min-width:250px; max-width:280px; text-align:center;'>
              <div style='font-size:28px;'>&#128208;</div>
              <div style='color:#E2E8F0; font-size:14px; font-weight:bold; margin-top:8px;'>
                Technical Schematics</div>
              <div style='color:#64748B; font-size:12px; margin-top:4px;'>
                Auto-generated SVG engineering drawings with every blueprint build.</div>
            </div>
            <div style='background:#1E293B; border-radius:8px; padding:20px;
                        flex:1; min-width:250px; max-width:280px; text-align:center;'>
              <div style='font-size:28px;'>&#128248;</div>
              <div style='color:#E2E8F0; font-size:14px; font-weight:bold; margin-top:8px;'>
                Equipment Scanner</div>
              <div style='color:#64748B; font-size:12px; margin-top:4px;'>
                Upload a photo. Gemini Vision identifies every harvestable component.</div>
            </div>
            <div style='background:#1E293B; border-radius:8px; padding:20px;
                        flex:1; min-width:250px; max-width:280px; text-align:center;'>
              <div style='font-size:28px;'>&#128100;</div>
              <div style='color:#E2E8F0; font-size:14px; font-weight:bold; margin-top:8px;'>
                Save Your Vehicles</div>
              <div style='color:#64748B; font-size:12px; margin-top:4px;'>
                Profile with saved vehicles and garage inventory. One-tap re-diagnosis.</div>
            </div>
            <div style='background:#1E293B; border-radius:8px; padding:20px;
                        flex:1; min-width:250px; max-width:280px; text-align:center;'>
              <div style='font-size:28px;'>&#128203;</div>
              <div style='color:#E2E8F0; font-size:14px; font-weight:bold; margin-top:8px;'>
                Free Invoice Generator</div>
              <div style='color:#64748B; font-size:12px; margin-top:4px;'>
                Generate professional repair estimates from any diagnosis. Free with every build.</div>
            </div>
            <div style='background:#1E293B; border-radius:8px; padding:20px;
                        flex:1; min-width:250px; max-width:280px; text-align:center;'>
              <div style='font-size:28px;'>&#128200;</div>
              <div style='color:#E2E8F0; font-size:14px; font-weight:bold; margin-top:8px;'>
                Community Intelligence</div>
              <div style='color:#64748B; font-size:12px; margin-top:4px;'>
                See how many others had this problem. Average costs. Most common root causes.</div>
            </div>
            <div style='background:#1E293B; border-radius:8px; padding:20px;
                        flex:1; min-width:250px; max-width:280px; text-align:center;'>
              <div style='font-size:28px;'>&#129504;</div>
              <div style='color:#E2E8F0; font-size:14px; font-weight:bold; margin-top:8px;'>
                Conception DNA</div>
              <div style='color:#64748B; font-size:12px; margin-top:4px;'>
                Every build trains the AI. The more people use it, the smarter it gets.</div>
            </div>
          </div>
        </div>
    """, unsafe_allow_html=True)

    # ── E-WASTE / SUSTAINABILITY ──
    st.markdown("""
        <div style='max-width:800px; margin:40px auto; padding:24px;
                    background:linear-gradient(135deg, #064e3b 0%, #0F172A 100%);
                    border-radius:12px; border:1px solid #10B981; text-align:center;'>
          <div style='color:#10B981; font-size:13px; font-weight:bold; letter-spacing:2px;
                      margin-bottom:8px;'>REDUCE. REUSE. REBUILD.</div>
          <div style='color:#E2E8F0; font-size:22px; font-weight:bold; margin-bottom:12px;'>
            Fight E-Waste With Every Build</div>
          <div style='color:#94A3B8; font-size:14px; line-height:1.8; max-width:650px;
                      margin:0 auto;'>
            53 million tons of e-waste are generated every year. Only 17% gets recycled.
            The rest sits in landfills leaching lead, mercury, and cadmium into the ground.<br><br>
            Every blueprint from The Builder Foundry turns trash into something useful.
            That old treadmill isn't garbage — it's a motor, a frame, a belt drive system,
            and a linear actuator waiting to become something new.<br><br>
            <strong style='color:#10B981;'>Stop throwing things away. Start building.</strong></div>
        </div>
    """, unsafe_allow_html=True)

    # ── FREE TRIAL ──
    st.markdown("---")
    st.markdown("""
        <div style='text-align:center; margin:20px 0 12px;'>
          <h2 style='color:#10B981; font-size:30px;'>Try 1 Free Build</h2>
          <p style='color:#94A3B8; font-size:15px;'>No credit card. Just your email.
            Build a blueprint, diagnose an engine, or check a quote — free.</p>
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

    # ── TOKEN PACKS ──
    st.markdown("""
        <div style='text-align:center; margin:40px 0 12px;'>
          <h2 style='color:#E2E8F0; font-size:28px;'>Buy Tokens — Pay Per Build</h2>
          <p style='color:#64748B; font-size:14px;'>No subscription. No commitment. Tokens never expire.</p>
          <p style='color:#94A3B8; font-size:12px; margin-top:4px;'>
            Standard builds = 1⚡ &nbsp;|&nbsp; Industrial = 3⚡ &nbsp;|&nbsp; Experimental = 5⚡</p>
        </div>
    """, unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown("""
            <div style='background:#1E293B; padding:24px 16px; border-radius:8px;
                        border:1px solid #334155; text-align:center;'>
              <div style='color:#94A3B8; font-size:11px; font-weight:bold;
                          letter-spacing:2px;'>SPARK</div>
              <div style='color:white; font-size:32px; font-weight:bold; margin:8px 0;'>
                3⚡</div>
              <div style='color:#FF4500; font-size:24px; font-weight:bold;'>$9.99</div>
              <div style='color:#64748B; font-size:12px; margin-top:4px;'>$3.33 per token</div>
            </div>
        """, unsafe_allow_html=True)
        st.link_button("⚡ GET SPARK", STRIPE_SPARK, use_container_width=True)
    with k2:
        st.markdown("""
            <div style='background:#1E293B; padding:24px 16px; border-radius:8px;
                        border:2px solid #FF4500; text-align:center;
                        box-shadow:0 0 20px rgba(255,69,0,0.15);'>
              <div style='color:#FF4500; font-size:11px; font-weight:bold;
                          letter-spacing:2px;'>BUILDER ★</div>
              <div style='color:white; font-size:32px; font-weight:bold; margin:8px 0;'>
                10⚡</div>
              <div style='color:#FF4500; font-size:24px; font-weight:bold;'>$24.99</div>
              <div style='color:#64748B; font-size:12px; margin-top:4px;'>$2.50 per token</div>
            </div>
        """, unsafe_allow_html=True)
        st.link_button("🔥 GET BUILDER", STRIPE_BUILDER, use_container_width=True)
    with k3:
        st.markdown("""
            <div style='background:#1E293B; padding:24px 16px; border-radius:8px;
                        border:1px solid #334155; text-align:center;'>
              <div style='color:#10B981; font-size:11px; font-weight:bold;
                          letter-spacing:2px;'>FOUNDRY</div>
              <div style='color:white; font-size:32px; font-weight:bold; margin:8px 0;'>
                30⚡</div>
              <div style='color:#10B981; font-size:24px; font-weight:bold;'>$59.99</div>
              <div style='color:#64748B; font-size:12px; margin-top:4px;'>$2.00 per token</div>
            </div>
        """, unsafe_allow_html=True)
        st.link_button("🔧 GET FOUNDRY", STRIPE_FOUNDRY, use_container_width=True)
    with k4:
        st.markdown("""
            <div style='background:#1E293B; padding:24px 16px; border-radius:8px;
                        border:1px solid #FFD700; text-align:center;'>
              <div style='color:#FFD700; font-size:11px; font-weight:bold;
                          letter-spacing:2px;'>SHOP PASS</div>
              <div style='color:white; font-size:32px; font-weight:bold; margin:8px 0;'>
                100⚡</div>
              <div style='color:#FFD700; font-size:24px; font-weight:bold;'>$149.99</div>
              <div style='color:#64748B; font-size:12px; margin-top:4px;'>$1.50 per token</div>
            </div>
        """, unsafe_allow_html=True)
        st.link_button("👑 GET SHOP PASS", STRIPE_SHOPPASS, use_container_width=True)

    # ── SUBSCRIPTIONS ──
    st.markdown("""
        <div style='text-align:center; margin:30px 0 12px;'>
          <h3 style='color:#94A3B8; font-size:20px;'>Build All The Time? Subscribe &amp; Save</h3>
          <p style='color:#64748B; font-size:13px;'>Monthly token refill. Unused tokens roll over forever. Cancel anytime.</p>
        </div>
    """, unsafe_allow_html=True)

    s1, s2, s3 = st.columns([1, 1, 1])
    with s1:
        st.markdown("&nbsp;")
    with s2:
        st.markdown("""
            <div style='background:#1E293B; padding:20px; border-radius:8px;
                        border:1px solid #3B82F6; text-align:center;'>
              <div style='color:#3B82F6; font-size:11px; font-weight:bold;
                          letter-spacing:2px;'>PRO — 20⚡/MONTH</div>
              <div style='color:white; font-size:28px; font-weight:bold; margin:8px 0;'>
                $29.99<span style='font-size:14px; color:#94A3B8;'>/mo</span></div>
              <div style='color:#64748B; font-size:12px;'>$1.50/token &bull; Unlimited rollover</div>
            </div>
        """, unsafe_allow_html=True)
        st.link_button("📋 SUBSCRIBE PRO", STRIPE_PRO_SUB, use_container_width=True)
    with s3:
        st.markdown("""
            <div style='background:#1E293B; padding:20px; border-radius:8px;
                        border:1px solid #A855F7; text-align:center;'>
              <div style='color:#A855F7; font-size:11px; font-weight:bold;
                          letter-spacing:2px;'>MASTER — 60⚡/MONTH</div>
              <div style='color:white; font-size:28px; font-weight:bold; margin:8px 0;'>
                $74.99<span style='font-size:14px; color:#94A3B8;'>/mo</span></div>
              <div style='color:#64748B; font-size:12px;'>$1.25/token &bull; Unlimited rollover</div>
            </div>
        """, unsafe_allow_html=True)
        st.link_button("🚀 SUBSCRIBE MASTER", STRIPE_MASTER_SUB, use_container_width=True)

    # ── THE STORY ──
    st.markdown("""
        <div style='max-width:750px; margin:40px auto; text-align:center; padding:0 20px;'>
          <h2 style='color:#E2E8F0; font-size:24px; margin-bottom:12px;'>Built From Scraps. Literally.</h2>
          <p style='color:#94A3B8; font-size:14px; line-height:1.8;'>
            The Builder Foundry was created by a self-taught developer who pieces together
            computers from salvaged parts and builds things from scrap. No CS degree. No VC funding.
            Just a garage, a vision, and a refusal to stop learning.<br><br>
            As a mechanic, I watched people get overcharged every day for repairs they didn't
            understand. As a builder, I watched perfectly good parts get thrown in landfills.
            This tool fixes both problems.<br><br>
            This is Phase 1 of <strong style='color:#FF4500;'>Conception</strong> —
            an advanced AI being built to learn from every blueprint, every diagnosis,
            and every repair. Every time you use the Foundry, Conception gets smarter.
            It learns what works, what doesn't, and what things really cost.<br><br>
            <span style='color:#10B981; font-weight:bold;'>
              Builders. Mechanics. Vehicle owners. We're all on the same team.</span></p>
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
            st.link_button("BUY TOKENS", STRIPE_SPARK, use_container_width=True)

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
    if st.button("🛡️  QUOTE CHECK",    use_container_width=True):
        st.session_state.active_tab = "quote_check"
    if st.button("🧠  CONCEPTION DNA",    use_container_width=True):
        st.session_state.active_tab = "conception"
    if st.button("👤  MY PROFILE",      use_container_width=True):
        st.session_state.active_tab = "profile"
    if st.button("💬  ARENA CHAT",        use_container_width=True):
        st.session_state.active_tab = "chat"

    st.markdown("---")

    # Token balance
    q = api_get(f"{BILLING_URL}/billing/tokens/{st.session_state.user_email}", timeout=5.0)
    if not isinstance(q, APIError):
        balance  = q.get("token_balance", 0)
        sub_tier = q.get("sub_tier")
        token_color = "#10B981" if balance > 5 else "#F59E0B" if balance > 0 else "#EF4444"
        st.markdown(f"""
            <div style='text-align:center; margin:8px 0;'>
              <div style='color:#94A3B8; font-size:10px; letter-spacing:2px;'>TOKENS</div>
              <div style='color:{token_color}; font-size:36px; font-weight:bold;'>
                {balance}⚡</div>
              {f"<div style='color:#F59E0B; font-size:10px;'>{sub_tier.upper()} SUBSCRIBER</div>" if sub_tier else ""}
            </div>
        """, unsafe_allow_html=True)
        if balance == 0:
            st.markdown("""
                <div style='background:#1E293B; padding:12px; border-radius:6px;
                            border:1px solid #EF4444; text-align:center; margin:8px 0;'>
                  <div style='color:#EF4444; font-size:12px; font-weight:bold;'>
                    No tokens remaining</div>
                  <div style='color:#94A3B8; font-size:11px; margin-top:4px;'>
                    Buy tokens to keep forging</div>
                </div>
            """, unsafe_allow_html=True)
        st.link_button("⚡ BUY TOKENS", STRIPE_SPARK, use_container_width=True)

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
        st.markdown("#### 🟠 GROK-4.2")
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
        _forge_cost = {"Standard": 1, "Industrial": 3, "Experimental": 5}
        _fc = _forge_cost.get(detail_level, 1)
        st.markdown(f"""
            <div style='background:#1E293B; padding:10px; border-radius:6px;
                        text-align:center; margin:8px 0;'>
              <span style='color:#F59E0B; font-size:18px; font-weight:bold;'>{_fc}⚡</span>
              <span style='color:#94A3B8; font-size:12px;'> tokens for {detail_level}</span>
            </div>
        """, unsafe_allow_html=True)
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
        _mech_cost = {"Standard": 1, "Industrial": 3, "Experimental": 5}
        _mc = _mech_cost.get(mech_detail, 1)
        st.markdown(f"""
            <div style='background:#1E293B; padding:10px; border-radius:6px;
                        text-align:center; margin:8px 0;'>
              <span style='color:#F59E0B; font-size:18px; font-weight:bold;'>{_mc}⚡</span>
              <span style='color:#94A3B8; font-size:12px;'> tokens for {mech_detail}</span>
            </div>
        """, unsafe_allow_html=True)

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
# TAB: QUOTE CHECK
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.active_tab == "quote_check":
    st.markdown("### 🛡️ QUOTE CHECK — IS YOUR MECHANIC'S PRICE FAIR?")
    st.markdown("""
        <div style='background:#1E293B; padding:16px; border-radius:8px;
                    border-left:4px solid #10B981; margin-bottom:16px;'>
          <div style='color:#10B981; font-size:13px; font-weight:bold;'>
            PROTECT YOUR WALLET</div>
          <div style='color:#94A3B8; font-size:13px; margin-top:4px;'>
            Got a repair quote? We'll check it against real repair data, find
            recalls and extended warranties, and tell you if the price is fair —
            or if you're getting ripped off.</div>
        </div>
    """, unsafe_allow_html=True)

    col_left, col_right = st.columns([2, 1])

    with col_left:
        r1a, r1b = st.columns(2)
        with r1a:
            qc_vehicle = st.text_input("YEAR / MAKE / MODEL",
                placeholder="e.g., 2022 Toyota Highlander", max_chars=200, key="qc_vehicle")
        with r1b:
            qc_mileage = st.text_input("MILEAGE",
                placeholder="e.g., 42,000 miles", max_chars=100, key="qc_mileage")

        qc_repair = st.text_input("WHAT THEY SAID IS WRONG",
            placeholder="e.g., AC condenser leak, needs full replacement", max_chars=500, key="qc_repair")

        r2a, r2b = st.columns(2)
        with r2a:
            qc_quoted = st.text_input("WHAT THEY QUOTED YOU ($)",
                placeholder="e.g., 2400", max_chars=20, key="qc_quoted")
        with r2b:
            qc_shop = st.text_input("SHOP TYPE (optional)",
                placeholder="e.g., Dealer, Independent, Chain", max_chars=100, key="qc_shop")

        qc_estimate = st.text_area("PASTE THEIR ESTIMATE (optional)",
            placeholder="If they gave you an itemized list, paste it here...",
            height=100, max_chars=3000, key="qc_estimate")

    with col_right:
        st.markdown("""
            <div style='background:#1E293B; padding:12px; border-radius:6px;
                        border:1px solid #10B981; margin-bottom:12px;'>
              <div style='color:#10B981; font-size:11px; font-weight:bold;
                          letter-spacing:1px;'>WHAT YOU GET</div>
              <div style='color:#94A3B8; font-size:12px; margin-top:6px; line-height:1.6;'>
                &#9654; Fair price range for your repair<br>
                &#9654; Recall &amp; warranty check<br>
                &#9654; Real parts pricing from suppliers<br>
                &#9654; What to say to push back<br>
                &#9654; Community data from real repairs<br>
                &#9654; NHTSA complaint history</div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("""
            <div style='background:#1E293B; padding:10px; border-radius:6px;
                        text-align:center; margin:8px 0;'>
              <span style='color:#F59E0B; font-size:18px; font-weight:bold;'>1⚡</span>
              <span style='color:#94A3B8; font-size:12px;'> token per quote check</span>
            </div>
        """, unsafe_allow_html=True)

        qc_go = st.button("🛡️ CHECK THIS QUOTE", use_container_width=True)

        if qc_go:
            if not qc_vehicle or not qc_vehicle.strip():
                st.error("Enter the vehicle year, make, and model.")
            elif not qc_repair or not qc_repair.strip():
                st.error("Describe what the mechanic said is wrong.")
            elif not qc_quoted or not qc_quoted.strip():
                st.error("Enter the dollar amount they quoted you.")
            else:
                project_desc = (
                    f"VEHICLE: {qc_vehicle.strip()}\n"
                    f"MILEAGE: {qc_mileage.strip() or 'Not specified'}\n"
                    f"REPAIR: {qc_repair.strip()}\n"
                    f"QUOTED: ${qc_quoted.strip()}\n"
                    f"SHOP TYPE: {qc_shop.strip() or 'Not specified'}\n"
                    + (f"ITEMIZED ESTIMATE:\n{qc_estimate.strip()}" if qc_estimate else "")
                )

                with st.spinner("Checking quote against real repair data..."):
                    awake = ping_service(f"{AI_URL}/health", timeout=10.0)
                    if not awake:
                        import time as _t
                        _t.sleep(3)
                        awake = ping_service(f"{AI_URL}/health", timeout=15.0)

                if not awake:
                    st.warning("AI service starting up. Click again in 10 seconds.")
                else:
                    with st.spinner("Analyzing quote..."):
                        result = api_post(f"{AI_URL}/generate", {
                            "junk_desc": "", "project_type": project_desc,
                            "detail_level": "Standard",
                            "user_email": st.session_state.user_email,
                            "mode": "quote_check",
                        }, timeout=60.0)
                        if isinstance(result, APIError):
                            st.error(result.detail)
                        else:
                            st.session_state.quote_task = result.get("task_id")
                            st.session_state.quote_attempts = 0
                            st.success("Analyzing your quote...")

    # ── QUOTE CHECK POLLING ──
    if st.session_state.quote_task:
        max_qc_attempts = 40
        if st.session_state.quote_attempts >= max_qc_attempts:
            st.error("Analysis timed out. Try again.")
            st.session_state.quote_task = None
            st.session_state.quote_attempts = 0
        else:
            st.markdown("---")
            task_id = st.session_state.quote_task
            result = api_get(f"{AI_URL}/generate/status/{task_id}", timeout=15.0)

            if isinstance(result, APIError):
                st.session_state.quote_attempts += 1
                time.sleep(5)
                st.rerun()
            else:
                state = result.get("status")
                if state == "complete":
                    st.balloons()
                    res = result.get("result", {})
                    st.markdown(res.get("content", ""))
                    if res.get("build_id"):
                        _download_buttons(res["build_id"], key_suffix="_qc")
                    st.session_state.quote_task = None
                    st.session_state.quote_attempts = 0
                elif state == "failed":
                    st.error("Quote analysis failed. Try again.")
                    st.session_state.quote_task = None
                    st.session_state.quote_attempts = 0
                else:
                    msg = result.get("message", "Analyzing quote...")
                    elapsed = st.session_state.quote_attempts * 3
                    st.markdown(f"""
                        <div style='background:#1E293B; padding:16px; border-radius:8px;
                                    border-left:4px solid #10B981; margin:8px 0;'>
                          <div style='color:#10B981; font-size:13px; font-weight:bold;'>
                            QUOTE ANALYSIS ({elapsed}s)</div>
                          <div style='color:#E2E8F0; font-size:15px; margin-top:8px;'>
                            {html.escape(msg)}</div>
                        </div>
                    """, unsafe_allow_html=True)
                    st.session_state.quote_attempts += 1
                    time.sleep(3)
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB: MY PROFILE
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.active_tab == "profile":
    st.markdown("### 👤 MY PROFILE")

    # Load profile data
    profile_data = api_get(f"{AUTH_URL}/profile/{st.session_state.user_email}")
    if isinstance(profile_data, APIError):
        profile = None
        vehicles = []
        inventory = []
    else:
        profile = profile_data.get("profile")
        vehicles = profile_data.get("vehicles", [])
        inventory = profile_data.get("inventory", [])

    # ── PROFILE INFO ──
    st.markdown("#### Business Information")
    st.caption("Required for invoice generation.")

    p_col1, p_col2 = st.columns(2)
    with p_col1:
        p_display = st.text_input("Display Name", value=(profile or {}).get("display_name", ""),
                                  key="p_display")
        p_business = st.text_input("Business Name", value=(profile or {}).get("business_name", ""),
                                   key="p_business")
        p_phone = st.text_input("Phone", value=(profile or {}).get("phone", ""), key="p_phone")
    with p_col2:
        p_location = st.text_input("Location", value=(profile or {}).get("location", ""), key="p_location")
        p_cert = st.text_input("Certification (ASE, etc.)", value=(profile or {}).get("certification", ""),
                               key="p_cert")
        p_rate = st.text_input("Default Labor Rate ($/hr)", value=str((profile or {}).get("default_labor_rate", "")),
                               key="p_rate")

    if st.button("💾 SAVE PROFILE", use_container_width=True):
        rate_val = None
        try:
            rate_val = float(p_rate) if p_rate else None
        except ValueError:
            pass
        result = api_post(f"{AUTH_URL}/profile/{st.session_state.user_email}", {
            "display_name": p_display, "business_name": p_business,
            "phone": p_phone, "location": p_location,
            "certification": p_cert, "default_labor_rate": rate_val,
        })
        if isinstance(result, APIError):
            st.error(result.detail)
        else:
            st.success("Profile saved!")

    # ── MY VEHICLES ──
    st.markdown("---")
    st.markdown("#### 🚗 My Vehicles / Equipment")
    st.caption("Save your vehicles for one-tap diagnostics.")

    if vehicles:
        for v in vehicles:
            default_badge = " ⭐ DEFAULT" if v.get("is_default") else ""
            with st.expander(f"{v.get('nickname') or v.get('make', '?')} — {v.get('year', '')} {v.get('make', '')} {v.get('model', '')}{default_badge}"):
                st.caption(f"Engine: {v.get('engine', 'N/A')} | Mileage: {v.get('mileage', 'N/A')} | {v.get('environment', '')}")
                if v.get("notes"):
                    st.caption(v["notes"])
                if st.button("🗑️ Remove", key=f"del_v_{v['id']}"):
                    api_post(f"{AUTH_URL}/profile/{st.session_state.user_email}/vehicle/{v['id']}/delete", {})
                    st.rerun()
    else:
        st.info("No vehicles saved yet.")

    with st.expander("➕ Add Vehicle"):
        v_nick = st.text_input("Nickname", placeholder="e.g., My Hatteras, Work Truck", key="v_nick")
        va, vb = st.columns(2)
        with va:
            v_year = st.text_input("Year", key="v_year")
            v_make = st.text_input("Make", key="v_make")
            v_model = st.text_input("Model", key="v_model")
        with vb:
            v_engine = st.text_input("Engine", key="v_engine")
            v_miles = st.text_input("Mileage/Hours", key="v_miles")
            v_env = st.selectbox("Environment", ["Marine / Boat", "Automotive", "Heavy Equipment",
                "Agricultural", "Generator / Stationary", "Other"], key="v_env")
        v_default = st.checkbox("Set as default vehicle", key="v_default")
        if st.button("💾 Save Vehicle", key="save_vehicle"):
            if v_make or v_model:
                result = api_post(f"{AUTH_URL}/profile/{st.session_state.user_email}/vehicle", {
                    "nickname": v_nick, "year": v_year, "make": v_make,
                    "model": v_model, "engine": v_engine, "mileage": v_miles,
                    "environment": v_env, "is_default": v_default,
                })
                if not isinstance(result, APIError):
                    st.success("Vehicle saved!")
                    st.rerun()

    # ── MY GARAGE (inventory) ──
    st.markdown("---")
    st.markdown("#### 🏠 My Garage — Saved Inventory")
    st.caption("Save your junk/parts for quick forge builds.")

    if inventory:
        for item in inventory:
            with st.expander(f"🔧 {item.get('item_name', '?')} — {item.get('category', '')}"):
                st.caption(f"Condition: {item.get('condition', 'N/A')}")
                if item.get("description"):
                    st.caption(item["description"])
                if st.button("🗑️ Remove", key=f"del_i_{item['id']}"):
                    api_post(f"{AUTH_URL}/profile/{st.session_state.user_email}/inventory/{item['id']}/delete", {})
                    st.rerun()
    else:
        st.info("No inventory items saved. Add items or use the Equipment Scanner.")

    with st.expander("➕ Add Inventory Item"):
        i_name = st.text_input("Item Name", placeholder="e.g., Old NordicTrack Treadmill", key="i_name")
        i_desc = st.text_area("Description / Specs", placeholder="Working motor, broken belt, steel frame intact", key="i_desc", height=80)
        ia, ib = st.columns(2)
        with ia:
            i_cat = st.selectbox("Category", ["Motors", "Frames", "Electronics", "Vehicles",
                "Appliances", "Tools", "Raw Materials", "Other"], key="i_cat")
        with ib:
            i_cond = st.selectbox("Condition", ["Working", "Needs Repair", "For Parts Only",
                "Unknown"], key="i_cond")
        if st.button("💾 Save Item", key="save_inventory"):
            if i_name:
                result = api_post(f"{AUTH_URL}/profile/{st.session_state.user_email}/inventory", {
                    "item_name": i_name, "description": i_desc,
                    "category": i_cat, "condition": i_cond,
                })
                if not isinstance(result, APIError):
                    st.success("Item saved to garage!")
                    st.rerun()

    # ── TOKEN BALANCE ──
    st.markdown("---")
    st.markdown("#### ⚡ Token Balance")
    tok = api_get(f"{BILLING_URL}/billing/tokens/{st.session_state.user_email}", timeout=5.0)
    if not isinstance(tok, APIError):
        t_balance = tok.get("token_balance", 0)
        t_purchased = tok.get("tokens_purchased", 0)
        t_used = tok.get("tokens_used", 0)
        t_sub = tok.get("sub_tier")
        tc1, tc2, tc3 = st.columns(3)
        tc1.metric("Balance", f"{t_balance}⚡")
        tc2.metric("Total Purchased", t_purchased)
        tc3.metric("Total Used", t_used)
        if t_sub:
            st.info(f"Active subscription: **{t_sub.upper()}** ({tok.get('sub_tokens_monthly', 0)} tokens/month)")
        st.link_button("⚡ BUY MORE TOKENS", STRIPE_SPARK, use_container_width=True)


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
