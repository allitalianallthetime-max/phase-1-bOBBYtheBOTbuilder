"""
APP_CONFIG — Shared configuration for all tab modules.
Every tab imports from here. Single source of truth.
"""

import os
import base64
import time
import html
import streamlit as st
from dotenv import load_dotenv
from app_helpers import api_get, api_post, api_get_raw, ping_service, APIError

load_dotenv()

# ── SERVICE URLs ──
AUTH_URL       = os.getenv("AUTH_SERVICE_URL",      "http://localhost:8001")
AI_URL         = os.getenv("AI_SERVICE_URL",        "http://localhost:8002")
WORKSHOP_URL   = os.getenv("WORKSHOP_SERVICE_URL",  "http://localhost:8003")
EXPORT_URL     = os.getenv("EXPORT_SERVICE_URL",    "http://localhost:8004")
BILLING_URL    = os.getenv("BILLING_SERVICE_URL",   "http://localhost:8006")

# ── STRIPE PAYMENT LINKS ──
STRIPE_SPARK      = os.getenv("STRIPE_URL_SPARK",       "#")
STRIPE_BUILDER    = os.getenv("STRIPE_URL_BUILDER",     "#")
STRIPE_FOUNDRY    = os.getenv("STRIPE_URL_FOUNDRY",     "#")
STRIPE_SHOPPASS   = os.getenv("STRIPE_URL_SHOPPASS",     "#")
STRIPE_PRO_SUB    = os.getenv("STRIPE_URL_PRO_SUB",     "#")
STRIPE_MASTER_SUB = os.getenv("STRIPE_URL_MASTER_SUB",  "#")

# ── SESSION DEFAULTS ──
SESSION_DEFAULTS = {
    "logged_in": False, "user_email": "", "user_name": "", "tier": "",
    "jwt_token": "", "active_task": None, "vault_data": None,
    "active_tab": "forge", "scan_task": None, "scan_attempts": 0,
    "forge_attempts": 0, "mechanic_task": None, "mechanic_attempts": 0,
    "quote_task": None, "quote_attempts": 0,
    "landing_warmed": False, "services_warmed": False,
}

# ── PIL (optional) ──
try:
    from PIL import Image
    import io as _io
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False
    Image = None
    _io = None


# ══════════════════════════════════════════════════════════════════════════════
# REUSABLE UI HELPERS
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False, ttl=3600)
def cached_download(url: str):
    return api_get_raw(url)


def download_buttons(build_id: str, key_suffix: str = ""):
    col1, col2 = st.columns(2)
    with col1:
        data, ok = cached_download(f"{EXPORT_URL}/export/download/{build_id}?fmt=md")
        if ok:
            st.download_button(
                "📥 DOWNLOAD (.md)", data=data,
                file_name=f"blueprint_{build_id}.md", mime="text/markdown",
                key=f"dlmd_{build_id}{key_suffix}", use_container_width=True
            )
    with col2:
        data, ok = cached_download(f"{EXPORT_URL}/export/download/{build_id}?fmt=txt")
        if ok:
            st.download_button(
                "📥 DOWNLOAD (.txt)", data=data,
                file_name=f"blueprint_{build_id}.txt", mime="text/plain",
                key=f"dltxt_{build_id}{key_suffix}", use_container_width=True
            )


def show_schematic(schematic: str, build_id: str):
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


def poll_task(task_key, attempts_key, status_base_url, max_attempts=40,
              label="PROCESSING", color="#FF4500", complete_title="COMPLETE",
              dl_suffix="", show_schematic_flag=False,
              timeout_msg="Task timed out. Try again.",
              fail_msg="Task failed. Try again.",
              archive_msg="Archived in Conception DNA Vault.",
              on_complete=None):
    task_id = st.session_state.get(task_key)
    if not task_id:
        return
    attempts = st.session_state.get(attempts_key, 0)
    if attempts >= max_attempts:
        st.error(timeout_msg)
        st.session_state[task_key] = None
        st.session_state[attempts_key] = 0
        return
    st.markdown("---")
    result = api_get(f"{status_base_url}{task_id}", timeout=15.0)
    if isinstance(result, APIError):
        st.warning(f"Polling interrupted: {result.detail}")
        st.session_state[attempts_key] = attempts + 1
        time.sleep(5)
        st.rerun()
        return
    state = result.get("status")
    if state == "complete":
        st.balloons()
        if on_complete:
            on_complete(result)
        else:
            st.markdown(f"#### {complete_title}")
            res = result.get("result", {})
            content = res.get("content", "")
            build_id = res.get("build_id", "")
            schem = res.get("schematic_svg", "") if show_schematic_flag else None
            if show_schematic_flag and schem:
                show_schematic(schem, build_id)
            st.markdown(content)
            if build_id:
                download_buttons(build_id, key_suffix=dl_suffix)
            st.info(archive_msg)
        st.session_state[task_key] = None
        st.session_state[attempts_key] = 0
    elif state == "failed":
        error_msg = result.get("error", "")
        if "TimeLimitExceeded" in error_msg:
            st.error("Timed out. Try Standard depth or simplify the input.")
        else:
            st.error(fail_msg)
        st.session_state[task_key] = None
        st.session_state[attempts_key] = 0
    else:
        msg = result.get("message", "Processing...")
        elapsed = attempts * 3
        st.markdown(f"""
            <div style='background:#1E293B; padding:16px; border-radius:8px;
                        border-left:4px solid {color}; margin:8px 0;'>
              <div style='color:{color}; font-size:13px; font-weight:bold;
                          font-family:monospace; letter-spacing:1px;'>
                {html.escape(label)} ({elapsed}s)</div>
              <div style='color:#E2E8F0; font-size:15px; margin-top:8px;'>
                {html.escape(msg)}</div>
            </div>
        """, unsafe_allow_html=True)
        st.session_state[attempts_key] = attempts + 1
        time.sleep(3)
        st.rerun()
