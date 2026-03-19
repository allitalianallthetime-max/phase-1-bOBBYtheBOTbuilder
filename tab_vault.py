"""Tab: tab_vault"""
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
                    data, ok = cached_download(f"{EXPORT_URL}/export/download/{bid}?fmt=md")
                    if ok:
                        st.download_button("📥 .md", data=data,
                                          file_name=f"blueprint_{bid}.md",
                                          mime="text/markdown", key=f"dlmd_{bid}",
                                          use_container_width=True)
                with col3:
                    data, ok = cached_download(f"{EXPORT_URL}/export/download/{bid}?fmt=txt")
                    if ok:
                        st.download_button("📥 .txt", data=data,
                                          file_name=f"blueprint_{bid}.txt",
                                          mime="text/plain", key=f"dltxt_{bid}",
                                          use_container_width=True)
