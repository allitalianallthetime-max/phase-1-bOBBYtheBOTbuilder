"""
APP.PY — BUILDER FOUNDRY STREAMLIT FRONTEND (Router)
=====================================================
Thin router: config, session, sidebar, tab dispatch.
Each tab is in its own file. Landing page is separate.
"""

import streamlit as st
import os
import html
from dotenv import load_dotenv

from app_config import (
    AUTH_URL, AI_URL, BILLING_URL, STRIPE_SPARK,
    api_get, ping_service, APIError, SESSION_DEFAULTS,
)

try:
    from builder_styles import BUILDER_CSS, FORGE_HEADER_HTML
except ImportError:
    BUILDER_CSS = ""
    FORGE_HEADER_HTML = "<h1 style='color:#FF4500; text-align:center;'>THE BUILDER FOUNDRY</h1>"

# ── Tab modules ──
import landing_page
import tab_forge
import tab_vault
import tab_scanner
import tab_mechanic
import tab_quote_check
import tab_conception
import tab_profile
import tab_chat

# ── Page config ──
load_dotenv()
st.set_page_config(
    page_title="AoC3P0 | THE BUILDER FOUNDRY",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Apply theme ──
if BUILDER_CSS:
    st.markdown(BUILDER_CSS, unsafe_allow_html=True)

# ── Session state ──
for k, v in SESSION_DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Auto-login from query params (survives browser refresh) ──
if not st.session_state.logged_in:
    qp = st.query_params
    saved_key = qp.get("k", "")
    if saved_key and saved_key.startswith("BOB-"):
        # Only try auto-login ONCE per session — don't hammer the auth service
        if not st.session_state.get("_auto_login_done"):
            st.session_state["_auto_login_done"] = True
            try:
                result = api_post(f"{AUTH_URL}/verify-license",
                                  {"license_key": saved_key}, timeout=8.0)
                if not isinstance(result, APIError):
                    st.session_state.logged_in  = True
                    st.session_state.user_email = result["email"]
                    st.session_state.user_name  = result.get("name", "")
                    st.session_state.tier       = result["tier"]
                    st.session_state.jwt_token  = result["token"]
            except Exception:
                pass


# ══════════════════════════════════════════════════════════════════════════════
# LANDING PAGE (not logged in)
# ══════════════════════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    landing_page.render()
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# LOGGED-IN APP
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(FORGE_HEADER_HTML, unsafe_allow_html=True)

# Warm up AI service
if not st.session_state.services_warmed:
    awake = ping_service(f"{AI_URL}/health", timeout=15.0)
    if awake:
        st.session_state.services_warmed = True


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    if os.path.exists("aoc3po_logo.png"):
        st.image("aoc3po_logo.png", width=200)

    st.markdown("---")
    tier_colors = {"master": "#FFD700", "pro": "#FF4500", "starter": "#94A3B8",
                   "trial": "#10B981", "token": "#3B82F6"}
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
        st.query_params.clear()
        st.session_state.clear()
        for k, v in SESSION_DEFAULTS.items():
            st.session_state[k] = v
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB ROUTING
# ══════════════════════════════════════════════════════════════════════════════
TAB_MAP = {
    "forge":       tab_forge.render,
    "vault":       tab_vault.render,
    "scanner":     tab_scanner.render,
    "conception":  tab_conception.render,
    "mechanic":    tab_mechanic.render,
    "quote_check": tab_quote_check.render,
    "profile":     tab_profile.render,
    "chat":        tab_chat.render,
}

active = st.session_state.active_tab
render_fn = TAB_MAP.get(active, tab_forge.render)
render_fn()


# ── FOOTER ──
st.markdown("---")
st.caption("AoC3P0 Systems | The Builder Foundry | Conception DNA Architecture")

# ── DEBUG (dev only) ──
if os.getenv("SHOW_DEBUG") == "1" and st.session_state.get("logged_in"):
    with st.expander("🔧 DEBUG INFO (dev only)"):
        safe_state = {k: "***" if k in ("jwt_token", "user_email") else str(v)[:100]
                      for k, v in st.session_state.items()}
        st.json({"session_state": safe_state})
