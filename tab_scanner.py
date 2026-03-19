"""Tab: tab_scanner"""
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
        def _on_scan_complete(result):
            scan_data = result.get("result", {}).get("scan_result", {})
            ident = scan_data.get("identification", {})
            comps = scan_data.get("components", [])
            st.success(f"**{ident.get('equipment_name', 'Unknown Equipment')}**")
            st.markdown("#### Identified Components")
            for c in comps:
                st.markdown(f"- **{c.get('name', '?')}** x {c.get('quantity', '?')}")

        poll_task(
            task_key="scan_task", attempts_key="scan_attempts",
            status_base_url=f"{WORKSHOP_URL}/task/status/",
            max_attempts=20, label="GEMINI VISION ANALYSIS", color="#10B981",
            timeout_msg="Scan timed out. Try again or use a different image.",
            fail_msg="Scan failed. Try another image.",
            on_complete=_on_scan_complete
        )

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
