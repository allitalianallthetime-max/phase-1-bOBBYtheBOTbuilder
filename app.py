import streamlit as st
import os, httpx, time, json
from dotenv import load_dotenv

try:
    from builder_styles import BUILDER_CSS, FORGE_HEADER_HTML
except ImportError:
    BUILDER_CSS = ""
    FORGE_HEADER_HTML = "<h1 style='color:#FF4500; text-align:center;'>⚙️ THE BUILDER FOUNDRY</h1>"

# ── CONFIGURATION ──
load_dotenv()
st.set_page_config(
    page_title="AoC3P0 | THE BUILDER",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

AUTH_URL      = os.getenv("AUTH_SERVICE_URL",      "http://localhost:8001")
AI_URL        = os.getenv("AI_SERVICE_URL",         "http://localhost:8002")
WORKSHOP_URL  = os.getenv("WORKSHOP_SERVICE_URL",   "http://localhost:8003")
EXPORT_URL    = os.getenv("EXPORT_SERVICE_URL",     "http://localhost:8004")
ANALYTICS_URL = os.getenv("ANALYTICS_SERVICE_URL",  "http://localhost:8005")
BILLING_URL   = os.getenv("BILLING_SERVICE_URL",    "http://localhost:8006")
STRIPE_STARTER = os.getenv("STRIPE_URL_STARTER",    "#")
STRIPE_PRO     = os.getenv("STRIPE_URL_PRO",        "#")
STRIPE_MASTER  = os.getenv("STRIPE_URL_MASTER",     "#")
INTERNAL_KEY   = os.getenv("INTERNAL_API_KEY",       "")

def _h():
    return {"x-internal-key": INTERNAL_KEY}

if BUILDER_CSS:
    st.markdown(BUILDER_CSS, unsafe_allow_html=True)
st.markdown(FORGE_HEADER_HTML, unsafe_allow_html=True)

# ── SESSION STATE ──
for k, v in {
    "logged_in":  False,
    "user_email": "",
    "user_name":  "",
    "tier":       "",
    "jwt_token":  "",
    "active_task": None,
    "vault_data": None,
    "active_tab": "forge",
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────
# AUTH GATE
# ─────────────────────────────────────────────
if not st.session_state.logged_in:
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.markdown("""
            <div style='background:#1E293B; padding:28px; border-radius:8px;
                        border:1px solid #FF4500;'>
            <h3 style='text-align:center; color:#FF4500;'>RESTRICTED ACCESS</h3>
            <p style='text-align:center; color:#94A3B8; font-size:14px;'>
            Enter your Foundry License Key to access the Round Table.</p>
        """, unsafe_allow_html=True)

        license_key = st.text_input("License Key", type="password",
                                    placeholder="BOB-XXXX-XXXX-XXXX")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("AUTHORIZE", use_container_width=True):
                if not license_key:
                    st.warning("Enter a license key.")
                else:
                    with st.spinner("Verifying credentials..."):
                        try:
                            resp = httpx.post(
                                f"{AUTH_URL}/verify-license",
                                json={"license_key": license_key},
                                headers=_h(), timeout=10.0
                            )
                            if resp.status_code == 200:
                                d = resp.json()
                                st.session_state.logged_in  = True
                                st.session_state.user_email = d["email"]
                                st.session_state.user_name  = d["name"]
                                st.session_state.tier       = d["tier"]
                                st.session_state.jwt_token  = d["token"]
                                st.rerun()
                            elif resp.status_code == 403:
                                st.error("License invalid, expired, or revoked.")
                            else:
                                st.error(f"Auth failed: {resp.status_code}")
                        except Exception as e:
                            st.error(f"Auth service offline: {e}")
        with col_b:
            st.link_button("GET A LICENSE", STRIPE_STARTER, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # ── PRICING TIERS ──
        st.markdown("<br>", unsafe_allow_html=True)
        t1, t2, t3 = st.columns(3)
        with t1:
            st.markdown("""
                <div style='background:#1E293B; padding:18px; border-radius:8px;
                            border:1px solid #94A3B8; text-align:center;'>
                <div style='color:#94A3B8; font-size:12px; font-weight:bold;'>STARTER</div>
                <div style='color:white; font-size:28px; font-weight:bold;'>$25<span style='font-size:14px;color:#94A3B8;'>/mo</span></div>
                <div style='color:#64748B; font-size:12px; margin-top:4px;'>25 builds/month</div>
                </div>
            """, unsafe_allow_html=True)
            st.link_button("⚡ STARTER", STRIPE_STARTER, use_container_width=True)
        with t2:
            st.markdown("""
                <div style='background:#1E293B; padding:18px; border-radius:8px;
                            border:1px solid #FF4500; text-align:center;'>
                <div style='color:#FF4500; font-size:12px; font-weight:bold;'>PRO ★</div>
                <div style='color:white; font-size:28px; font-weight:bold;'>$100<span style='font-size:14px;color:#94A3B8;'>/mo</span></div>
                <div style='color:#64748B; font-size:12px; margin-top:4px;'>100 builds/month</div>
                </div>
            """, unsafe_allow_html=True)
            st.link_button("🔥 PRO", STRIPE_PRO, use_container_width=True)
        with t3:
            st.markdown("""
                <div style='background:#1E293B; padding:18px; border-radius:8px;
                            border:1px solid #FFD700; text-align:center;'>
                <div style='color:#FFD700; font-size:12px; font-weight:bold;'>MASTER</div>
                <div style='color:white; font-size:28px; font-weight:bold;'>$999<span style='font-size:14px;color:#94A3B8;'>/yr</span></div>
                <div style='color:#64748B; font-size:12px; margin-top:4px;'>Unlimited builds</div>
                </div>
            """, unsafe_allow_html=True)
            st.link_button("👑 MASTER", STRIPE_MASTER, use_container_width=True)
    st.stop()

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    if os.path.exists("aoc3po_logo.png"):
        st.image("aoc3po_logo.png", width=200)

    st.markdown("---")
    tier_colors = {"master": "#FFD700", "pro": "#FF4500", "starter": "#94A3B8"}
    tc = tier_colors.get(st.session_state.tier, "#94A3B8")
    st.markdown(f"""
        <div style='background:#1E293B; padding:12px; border-radius:6px;
                    border-left:4px solid {tc};'>
          <div style='color:#94A3B8; font-size:12px;'>OPERATOR</div>
          <div style='color:white; font-weight:bold;'>{st.session_state.user_name or "Unknown"}</div>
          <div style='color:#94A3B8; font-size:11px; margin-top:4px;'>
            {st.session_state.user_email}</div>
          <div style='color:{tc}; font-size:11px; font-weight:bold; margin-top:4px;'>
            ⬡ {st.session_state.tier.upper()} CLEARANCE</div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Nav buttons
    if st.button("⚙️  FORGE BLUEPRINT",    use_container_width=True):
        st.session_state.active_tab = "forge"
    if st.button("🗄️  CONCEPTION VAULT",   use_container_width=True):
        st.session_state.active_tab = "vault"
        st.session_state.vault_data = None  # force refresh
    if st.button("🔬  EQUIPMENT SCANNER",  use_container_width=True):
        st.session_state.active_tab = "scanner"
    if st.button("🧠  CONCEPTION DNA",     use_container_width=True):
        st.session_state.active_tab = "conception"
    if st.button("💬  ARENA CHAT",         use_container_width=True):
        st.session_state.active_tab = "chat"

    st.markdown("---")

    # Quota meter
    try:
        q = httpx.get(
            f"{BILLING_URL}/billing/quota/{st.session_state.user_email}",
            headers=_h(), timeout=5.0
        ).json()
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
            if st.session_state.tier == "starter":
                st.link_button("UPGRADE TO PRO", STRIPE_PRO, use_container_width=True)
            elif st.session_state.tier == "pro":
                st.link_button("UPGRADE TO MASTER", STRIPE_MASTER, use_container_width=True)
    except Exception:
        pass

    st.markdown("---")
    st.markdown("### 🛠️ MAINTENANCE FUND")
    st.markdown(f"<a href='{STRIPE_STARTER}' target='_blank' style='color:#FF4500;'>☕ TIP THE TECH CUP</a>",
                unsafe_allow_html=True)
    st.markdown("---")

    if st.button("LOGOUT", use_container_width=True):
        for k in ["logged_in","user_email","user_name","tier","jwt_token","active_task","vault_data"]:
            st.session_state[k] = "" if k != "logged_in" else False
        st.rerun()


# ─────────────────────────────────────────────
# TAB: FORGE BLUEPRINT
# ─────────────────────────────────────────────
if st.session_state.active_tab == "forge":
    st.markdown("### 🛡️ ACTIVE ENGINEERING AGENTS")
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
        st.markdown("#### 🟢 GEMINI 2.0")
        st.caption("SYNTHESIS ENGINE / CONCEPTION VAULT")
        st.status("READY", state="complete")

    st.markdown("---")
    col_left, col_right = st.columns([2, 1])

    with col_left:
        project_name   = st.text_input("PROJECT IDENTIFIER",
                                       placeholder="e.g., Heavy-Duty Hydraulic Submersible Arm")
        inventory_input = st.text_area("INVENTORY MANIFEST / JUNK DESCRIPTION",
                                       placeholder="List every motor, sensor, and scrap metal piece...",
                                       height=260)
    with col_right:
        st.markdown("### BUILD PARAMETERS")
        detail_level = st.select_slider("SPECIFICATION DEPTH",
                                        options=["Standard", "Industrial", "Experimental"])
        st.markdown("&nbsp;")
        forge = st.button("🚀 FORGE BLUEPRINT", use_container_width=True)

        if forge:
            if not project_name or not inventory_input:
                st.error("Project identifier and inventory manifest are required.")
            else:
                try:
                    with st.spinner("Initiating Round Table protocols..."):
                        payload = {
                            "junk_desc":   inventory_input,
                            "project_type": project_name,
                            "detail_level": detail_level,
                            "user_email":   st.session_state.user_email,
                        }
                        resp = httpx.post(
                            f"{AI_URL}/generate",
                            json=payload, headers=_h(), timeout=60.0
                        )
                        if resp.status_code == 200:
                            st.session_state.active_task = resp.json().get("task_id")
                            st.success("Agents deployed. Blueprint forging...")
                        elif resp.status_code == 402:
                            st.error("Build quota exceeded. Upgrade your license.")
                        else:
                            st.error(f"Forge refused: {resp.text}")
                except Exception as e:
                    st.error(f"Connection failure: {e}")

    # ── TASK POLLING ──
    if st.session_state.active_task:
        st.markdown("---")
        st.markdown("### 🏗️ CURRENT BUILD LOG")
        task_id = st.session_state.active_task
        try:
            sr = httpx.get(f"{AI_URL}/generate/status/{task_id}",
                           headers=_h(), timeout=15.0)
            if sr.status_code == 200:
                data  = sr.json()
                state = data.get("status")

                if state == "complete":
                    st.balloons()
                    st.markdown("#### ✅ SYNTHESIS COMPLETE")
                    blueprint = data.get("result", {}).get("content", "")
                    build_id  = data.get("result", {}).get("build_id", "")
                    schematic = data.get("result", {}).get("schematic_svg", "")

                    # Display schematic drawing if available
                    if schematic and schematic.startswith("<svg"):
                        st.markdown("#### 📐 TECHNICAL SCHEMATIC")
                        st.markdown(
                            f'<div style="background:white; padding:16px; '
                            f'border-radius:8px; border:1px solid #334155; '
                            f'overflow-x:auto;">{schematic}</div>',
                            unsafe_allow_html=True
                        )
                        st.download_button(
                            "📐 DOWNLOAD SCHEMATIC (.svg)",
                            data=schematic,
                            file_name=f"schematic_{build_id or 'draft'}.svg",
                            mime="image/svg+xml",
                            use_container_width=True
                        )
                        st.markdown("---")

                    st.markdown(blueprint)

                    if build_id:
                        col1, col2 = st.columns(2)
                        with col1:
                            try:
                                dl = httpx.get(
                                    f"{EXPORT_URL}/export/download/{build_id}?fmt=md",
                                    headers=_h(), timeout=10.0
                                )
                                st.download_button(
                                    "📥 DOWNLOAD BLUEPRINT (.md)",
                                    data=dl.content,
                                    file_name=f"blueprint_{build_id}.md",
                                    mime="text/markdown",
                                    use_container_width=True
                                )
                            except Exception:
                                pass
                        with col2:
                            try:
                                dl = httpx.get(
                                    f"{EXPORT_URL}/export/download/{build_id}?fmt=txt",
                                    headers=_h(), timeout=10.0
                                )
                                st.download_button(
                                    "📥 DOWNLOAD BLUEPRINT (.txt)",
                                    data=dl.content,
                                    file_name=f"blueprint_{build_id}.txt",
                                    mime="text/plain",
                                    use_container_width=True
                                )
                            except Exception:
                                pass

                    st.info("Blueprint archived in Conception DNA Vault.")
                    st.session_state.active_task = None

                elif state == "failed":
                    st.error("The Round Table failed to reach consensus. Check your manifest.")
                    st.session_state.active_task = None
                else:
                    msg = data.get("message", "Agents are forging your blueprint...")
                    st.info(f"⚙️ {msg}")
                    time.sleep(2)
                    st.rerun()
        except Exception as e:
            st.warning(f"Polling interrupted: {e}")


# ─────────────────────────────────────────────
# TAB: CONCEPTION VAULT
# ─────────────────────────────────────────────
elif st.session_state.active_tab == "vault":
    st.markdown("### 🗄️ CONCEPTION DNA VAULT")
    st.caption("All blueprints archived for Conception's learning and your reference.")

    # Load vault data
    if st.session_state.vault_data is None:
        with st.spinner("Loading your vault..."):
            try:
                resp = httpx.get(
                    f"{EXPORT_URL}/export/vault/{st.session_state.user_email}",
                    headers=_h(), timeout=10.0
                )
                st.session_state.vault_data = resp.json() if resp.status_code == 200 else {}
            except Exception:
                st.session_state.vault_data = {}

    vault = st.session_state.vault_data
    builds = vault.get("builds", [])

    # Stats row
    try:
        stats = httpx.get(
            f"{EXPORT_URL}/export/stats/{st.session_state.user_email}",
            headers=_h(), timeout=8.0
        ).json()
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Total Builds",      stats.get("total_builds", 0))
        s2.metric("Tokens Consumed",   f"{stats.get('total_tokens', 0):,}")
        s3.metric("Conception Ready",  stats.get("conception_ready", 0))
        s4.metric("In Vault",          vault.get("count", 0))
    except Exception:
        pass

    st.markdown("---")

    if not builds:
        st.info("No blueprints in your vault yet. Forge your first blueprint in the FORGE tab.")
    else:
        # Search filter
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

            with st.expander(
                f"{'🧠' if ready else '📄'}  {proj}  —  {date}  |  {tokens:,} tokens"
            ):
                st.caption(preview)
                col1, col2, col3 = st.columns(3)

                with col1:
                    if st.button("📖 LOAD FULL BLUEPRINT", key=f"load_{bid}"):
                        try:
                            full = httpx.get(
                                f"{EXPORT_URL}/export/blueprint/{bid}",
                                headers=_h(), timeout=10.0
                            ).json()
                            st.markdown("---")
                            st.markdown(full.get("blueprint", ""))
                        except Exception as e:
                            st.error(f"Failed to load: {e}")

                with col2:
                    try:
                        dl = httpx.get(
                            f"{EXPORT_URL}/export/download/{bid}?fmt=md",
                            headers=_h(), timeout=10.0
                        )
                        st.download_button(
                            "📥 .md",
                            data=dl.content,
                            file_name=f"blueprint_{bid}.md",
                            mime="text/markdown",
                            key=f"dlmd_{bid}",
                            use_container_width=True
                        )
                    except Exception:
                        pass

                with col3:
                    try:
                        dl = httpx.get(
                            f"{EXPORT_URL}/export/download/{bid}?fmt=txt",
                            headers=_h(), timeout=10.0
                        )
                        st.download_button(
                            "📥 .txt",
                            data=dl.content,
                            file_name=f"blueprint_{bid}.txt",
                            mime="text/plain",
                            key=f"dltxt_{bid}",
                            use_container_width=True
                        )
                    except Exception:
                        pass


# ─────────────────────────────────────────────
# TAB: EQUIPMENT SCANNER
# ─────────────────────────────────────────────
elif st.session_state.active_tab == "scanner":
    st.markdown("### 🔬 EQUIPMENT SCANNER")
    st.caption("Upload a photo of any hardware. Gemini Vision identifies every component.")

    col_left, col_right = st.columns([1, 1])
    with col_left:
        uploaded = st.file_uploader("Upload equipment photo", type=["jpg", "jpeg", "png", "webp"])
        context  = st.text_input("Scan context", placeholder="e.g., underwater ROV motor assembly")

        if st.button("🔬 RUN SCAN", use_container_width=True):
            if not uploaded:
                st.error("Upload an image first.")
            else:
                import base64
                b64 = base64.b64encode(uploaded.read()).decode("utf-8")
                mime = uploaded.type or "image/jpeg"
                data_url = f"data:{mime};base64,{b64}"

                try:
                    with st.spinner("Running computer vision analysis..."):
                        resp = httpx.post(
                            f"{WORKSHOP_URL}/scan/base64",
                            json={
                                "image_base64": data_url,
                                "user_email":   st.session_state.user_email,
                                "context":      context or "general hardware scan",
                            },
                            headers=_h(), timeout=15.0
                        )
                        if resp.status_code == 200:
                            st.session_state["scan_task"] = resp.json().get("task_id")
                        else:
                            st.error(f"Scanner refused: {resp.text}")
                except Exception as e:
                    st.error(f"Scanner offline: {e}")

    with col_right:
        if "scan_task" in st.session_state and st.session_state["scan_task"]:
            task_id = st.session_state["scan_task"]
            with st.spinner("Gemini Vision analyzing..."):
                for _ in range(30):
                    try:
                        sr = httpx.get(
                            f"{WORKSHOP_URL}/task/status/{task_id}",
                            headers=_h(), timeout=10.0
                        ).json()
                        if sr.get("status") == "complete":
                            result = sr.get("result", {}).get("scan_result", {})
                            ident  = result.get("identification", {})
                            comps  = result.get("components", [])

                            st.success(f"**{ident.get('equipment_name', 'Unknown Equipment')}**")
                            st.markdown("#### Identified Components")
                            for c in comps:
                                st.markdown(f"- **{c.get('name', '?')}** × {c.get('quantity', '?')}")

                            st.session_state["scan_task"] = None
                            break
                        elif sr.get("status") == "failed":
                            st.error("Scan failed. Try another image.")
                            st.session_state["scan_task"] = None
                            break
                        time.sleep(2)
                    except Exception:
                        time.sleep(2)

    # Scan history
    st.markdown("---")
    st.markdown("#### Past Scans")
    try:
        scans = httpx.get(
            f"{EXPORT_URL}/export/scan/{st.session_state.user_email}",
            headers=_h(), timeout=8.0
        ).json().get("scans", [])
        for s in scans[:10]:
            with st.expander(f"🔩 {s.get('equipment_name','Unknown')} — {str(s.get('created_at',''))[:10]}"):
                result = s.get("scan_result", {})
                for comp in result.get("components", []):
                    st.markdown(f"- {comp.get('name','?')} × {comp.get('quantity','?')}")
    except Exception:
        st.caption("Scan history unavailable.")


# ─────────────────────────────────────────────
# TAB: CONCEPTION DNA
# ─────────────────────────────────────────────
elif st.session_state.active_tab == "conception":
    st.markdown("### 🧠 CONCEPTION DNA — LEARNING CORE")
    st.caption(
        "Conception learns from every blueprint forged. "
        "The more you build, the smarter he gets."
    )

    try:
        stats = httpx.get(
            f"{EXPORT_URL}/export/stats/{st.session_state.user_email}",
            headers=_h(), timeout=8.0
        ).json()

        total   = stats.get("total_builds", 0)
        tokens  = stats.get("total_tokens", 0)
        ready   = stats.get("conception_ready", 0)
        pct     = round((ready / max(total, 1)) * 100, 1)

        c1, c2, c3 = st.columns(3)
        c1.metric("Blueprints Absorbed", total)
        c2.metric("Tokens Processed",    f"{tokens:,}")
        c3.metric("Conception Ready",    f"{pct}%")

        st.markdown("---")

        # DNA progress bar
        st.markdown("#### CONCEPTION KNOWLEDGE INDEX")
        knowledge_pct = min(total / 500, 1.0)  # 500 blueprints = full knowledge base
        st.progress(knowledge_pct,
                    text=f"{total} / 500 blueprints — {knowledge_pct*100:.1f}% knowledge saturation")

        # Top project types Conception has learned
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
            st.warning("🔴 Offline — No training data yet.")
        elif total < 10:
            st.warning(f"🟡 Initializing — {total} blueprints absorbed. Keep forging.")
        elif total < 50:
            st.info(f"🔵 Learning — {total} blueprints in memory.")
        elif total < 200:
            st.success(f"🟢 Active — {total} blueprints. Conception is developing.")
        else:
            st.success(f"⚡ ADVANCED — {total} blueprints. Conception is growing rapidly.")

        st.markdown("---")
        st.markdown("#### NEXT MILESTONE")
        milestones = [10, 50, 100, 200, 500]
        next_m = next((m for m in milestones if m > total), 500)
        needed = next_m - total
        st.info(f"**{needed} more blueprints** until the next Conception evolution milestone ({next_m} total).")

    except Exception as e:
        st.error(f"Could not load Conception data: {e}")


# ─────────────────────────────────────────────
# TAB: ARENA CHAT
# ─────────────────────────────────────────────
elif st.session_state.active_tab == "chat":
    st.markdown("### 💬 FOUNDRY ARENA CHAT")
    st.caption("Live global channel. All operators. All tiers.")

    # Send message
    with st.form("chat_form", clear_on_submit=True):
        msg_text = st.text_input("Message", placeholder="Speak, operator...")
        sent = st.form_submit_button("TRANSMIT", use_container_width=True)
        if sent and msg_text.strip():
            try:
                httpx.post(
                    f"{AI_URL}/arena/chat/send",
                    json={
                        "user_name": st.session_state.user_name or "Anonymous",
                        "tier":      st.session_state.tier,
                        "message":   msg_text.strip(),
                    },
                    headers=_h(), timeout=5.0
                )
            except Exception:
                pass

    # Display messages
    try:
        messages = httpx.get(
            f"{AI_URL}/arena/chat/recent",
            headers=_h(), timeout=5.0
        ).json()

        tier_badge = {"master": "🥇", "pro": "🟠", "starter": "⚪"}
        for m in messages:
            badge = tier_badge.get(m.get("tier", ""), "⚪")
            st.markdown(
                f"`{m.get('time','')}` {badge} **{m.get('user','?')}** — {m.get('text','')}",
                unsafe_allow_html=False
            )
    except Exception:
        st.caption("Chat unavailable.")

    if st.button("🔄 REFRESH", use_container_width=True):
        st.rerun()

# ── FOOTER ──
st.markdown("---")
st.caption("AoC3P0 Systems | The Builder Foundry | Conception DNA Architecture")
