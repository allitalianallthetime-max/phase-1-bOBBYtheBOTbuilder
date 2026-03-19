"""Tab: Arena Chat"""
import streamlit as st
from app_config import AI_URL, api_get, api_post, APIError


def render():
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
