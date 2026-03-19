"""Tab: tab_quote_check"""
import streamlit as st
import time
import html
from app_config import (
    AUTH_URL, AI_URL, WORKSHOP_URL, EXPORT_URL, BILLING_URL,
    STRIPE_SPARK, STRIPE_BUILDER, STRIPE_FOUNDRY, STRIPE_SHOPPASS,
    STRIPE_PRO_SUB, STRIPE_MASTER_SUB,
    api_get, api_post, ping_service, APIError,
    download_buttons, show_schematic, poll_task, cached_download,
    _PIL_AVAILABLE, Image, _io,
    SESSION_DEFAULTS,
)


def render():
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

                with st.spinner("Waking AI agents..."):
                    awake = False
                    for attempt in range(3):
                        awake = ping_service(f"{AI_URL}/health", timeout=15.0)
                        if awake:
                            break
                        import time as _t
                        _t.sleep(5)

                if not awake:
                    st.warning("AI service is waking up — Render cold starts can take 30 seconds. Click again.")
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
    poll_task(
        task_key="quote_task", attempts_key="quote_attempts",
        status_base_url=f"{AI_URL}/generate/status/",
        max_attempts=60, label="QUOTE ANALYSIS", color="#10B981",
        complete_title="QUOTE ANALYSIS COMPLETE", dl_suffix="_qc",
        timeout_msg="Analysis timed out. Try again.",
        fail_msg="Quote analysis failed. Try again.",
        archive_msg="Quote analysis archived."
    )
