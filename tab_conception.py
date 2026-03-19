"""Tab: tab_conception"""
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
