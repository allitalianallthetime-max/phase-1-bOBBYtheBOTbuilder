"""Tab: tab_forge"""
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
    _poll_task(
        task_key="active_task", attempts_key="forge_attempts",
        status_base_url=f"{AI_URL}/generate/status/",
        max_attempts=40, label="ROUND TABLE ACTIVE", color="#FF4500",
        complete_title="SYNTHESIS COMPLETE", show_schematic=True,
        timeout_msg="Forge timed out. The server may be under heavy load. Try again.",
        fail_msg="The Round Table failed to reach consensus. Check your manifest.",
        archive_msg="Blueprint archived in Conception DNA Vault."
    )
