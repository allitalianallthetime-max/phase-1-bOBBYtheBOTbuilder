"""Tab: tab_mechanic"""
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
        _depth_labels = {
            "Standard": "Field Repair — basic tools",
            "Industrial": "Advanced — full tool set",
            "Experimental": "Full Shop Procedure — pro tech"
        }
        st.markdown(f"""
            <div style='background:#1E293B; padding:10px; border-radius:6px;
                        text-align:center; margin:8px 0;'>
              <span style='color:#F59E0B; font-size:18px; font-weight:bold;'>{_mc}⚡</span>
              <span style='color:#94A3B8; font-size:12px;'> {_depth_labels.get(mech_detail, '')}</span>
            </div>
        """, unsafe_allow_html=True)

        if mech_detail == "Experimental":
            st.markdown("""
                <div style='background:#1E293B; padding:12px; border-radius:6px;
                            border:1px solid #A855F7; margin-bottom:12px;'>
                  <div style='color:#A855F7; font-size:11px; font-weight:bold;
                              letter-spacing:1px;'>FULL SHOP PROCEDURE</div>
                  <div style='color:#94A3B8; font-size:12px; margin-top:6px; line-height:1.6;'>
                    &#9654; Complete R&amp;R with step numbers<br>
                    &#9654; Manifold gauge readings &amp; specs<br>
                    &#9654; Vacuum pull specs &amp; charge weight<br>
                    &#9654; Scan tool PIDs to monitor<br>
                    &#9654; Leak detection procedure<br>
                    &#9654; Root cause analysis<br>
                    &#9654; Labor time guide (book vs real)<br>
                    &#9654; OEM part numbers + aftermarket options</div>
                </div>
            """, unsafe_allow_html=True)
        else:
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
                    awake = False
                    for attempt in range(3):
                        awake = ping_service(f"{AI_URL}/health", timeout=15.0)
                        if awake:
                            break
                        import time as _t
                        _t.sleep(5)

                if not awake:
                    st.warning("AI service is waking up — Render cold starts can take 30 seconds. Click DIAGNOSE again.")
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
    poll_task(
        task_key="mechanic_task", attempts_key="mechanic_attempts",
        status_base_url=f"{AI_URL}/generate/status/",
        max_attempts=60, label="DIAGNOSTIC ACTIVE", color="#F59E0B",
        complete_title="REPAIR PROCEDURE READY", dl_suffix="_mech",
        timeout_msg="Diagnosis is taking longer than expected. The AI agents are still working — click DIAGNOSE again to retry.",
        fail_msg="Diagnostic agents could not reach consensus. Try simplifying the symptoms.",
        archive_msg="Repair procedure archived in Conception DNA Vault."
    )
