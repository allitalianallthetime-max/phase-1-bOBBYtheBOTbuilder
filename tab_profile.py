"""Tab: tab_profile"""
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
    st.markdown("### 👤 MY PROFILE")

    # Load profile data
    profile_data = api_get(f"{AUTH_URL}/profile/{st.session_state.user_email}")
    if isinstance(profile_data, APIError):
        profile = None
        vehicles = []
        inventory = []
    else:
        profile = profile_data.get("profile")
        vehicles = profile_data.get("vehicles", [])
        inventory = profile_data.get("inventory", [])

    # ── PROFILE INFO ──
    st.markdown("#### Business Information")
    st.caption("Required for invoice generation.")

    p_col1, p_col2 = st.columns(2)
    with p_col1:
        p_display = st.text_input("Display Name", value=(profile or {}).get("display_name", ""),
                                  key="p_display")
        p_business = st.text_input("Business Name", value=(profile or {}).get("business_name", ""),
                                   key="p_business")
        p_phone = st.text_input("Phone", value=(profile or {}).get("phone", ""), key="p_phone")
    with p_col2:
        p_location = st.text_input("Location", value=(profile or {}).get("location", ""), key="p_location")
        p_cert = st.text_input("Certification (ASE, etc.)", value=(profile or {}).get("certification", ""),
                               key="p_cert")
        p_rate = st.text_input("Default Labor Rate ($/hr)", value=str((profile or {}).get("default_labor_rate", "")),
                               key="p_rate")

    if st.button("💾 SAVE PROFILE", use_container_width=True):
        rate_val = None
        try:
            rate_val = float(p_rate) if p_rate else None
        except ValueError:
            pass
        result = api_post(f"{AUTH_URL}/profile/{st.session_state.user_email}", {
            "display_name": p_display, "business_name": p_business,
            "phone": p_phone, "location": p_location,
            "certification": p_cert, "default_labor_rate": rate_val,
        })
        if isinstance(result, APIError):
            st.error(result.detail)
        else:
            st.success("Profile saved!")

    # ── MY VEHICLES ──
    st.markdown("---")
    st.markdown("#### 🚗 My Vehicles / Equipment")
    st.caption("Save your vehicles for one-tap diagnostics.")

    if vehicles:
        for v in vehicles:
            default_badge = " ⭐ DEFAULT" if v.get("is_default") else ""
            with st.expander(f"{v.get('nickname') or v.get('make', '?')} — {v.get('year', '')} {v.get('make', '')} {v.get('model', '')}{default_badge}"):
                st.caption(f"Engine: {v.get('engine', 'N/A')} | Mileage: {v.get('mileage', 'N/A')} | {v.get('environment', '')}")
                if v.get("notes"):
                    st.caption(v["notes"])
                if st.button("🗑️ Remove", key=f"del_v_{v['id']}"):
                    api_post(f"{AUTH_URL}/profile/{st.session_state.user_email}/vehicle/{v['id']}/delete", {})
                    st.rerun()
    else:
        st.info("No vehicles saved yet.")

    with st.expander("➕ Add Vehicle"):
        v_nick = st.text_input("Nickname", placeholder="e.g., My Hatteras, Work Truck", key="v_nick")
        va, vb = st.columns(2)
        with va:
            v_year = st.text_input("Year", key="v_year")
            v_make = st.text_input("Make", key="v_make")
            v_model = st.text_input("Model", key="v_model")
        with vb:
            v_engine = st.text_input("Engine", key="v_engine")
            v_miles = st.text_input("Mileage/Hours", key="v_miles")
            v_env = st.selectbox("Environment", ["Marine / Boat", "Automotive", "Heavy Equipment",
                "Agricultural", "Generator / Stationary", "Other"], key="v_env")
        v_default = st.checkbox("Set as default vehicle", key="v_default")
        if st.button("💾 Save Vehicle", key="save_vehicle"):
            if v_make or v_model:
                result = api_post(f"{AUTH_URL}/profile/{st.session_state.user_email}/vehicle", {
                    "nickname": v_nick, "year": v_year, "make": v_make,
                    "model": v_model, "engine": v_engine, "mileage": v_miles,
                    "environment": v_env, "is_default": v_default,
                })
                if not isinstance(result, APIError):
                    st.success("Vehicle saved!")
                    st.rerun()

    # ── MY GARAGE (inventory) ──
    st.markdown("---")
    st.markdown("#### 🏠 My Garage — Saved Inventory")
    st.caption("Save your junk/parts for quick forge builds.")

    if inventory:
        for item in inventory:
            with st.expander(f"🔧 {item.get('item_name', '?')} — {item.get('category', '')}"):
                st.caption(f"Condition: {item.get('condition', 'N/A')}")
                if item.get("description"):
                    st.caption(item["description"])
                if st.button("🗑️ Remove", key=f"del_i_{item['id']}"):
                    api_post(f"{AUTH_URL}/profile/{st.session_state.user_email}/inventory/{item['id']}/delete", {})
                    st.rerun()
    else:
        st.info("No inventory items saved. Add items or use the Equipment Scanner.")

    with st.expander("➕ Add Inventory Item"):
        i_name = st.text_input("Item Name", placeholder="e.g., Old NordicTrack Treadmill", key="i_name")
        i_desc = st.text_area("Description / Specs", placeholder="Working motor, broken belt, steel frame intact", key="i_desc", height=80)
        ia, ib = st.columns(2)
        with ia:
            i_cat = st.selectbox("Category", ["Motors", "Frames", "Electronics", "Vehicles",
                "Appliances", "Tools", "Raw Materials", "Other"], key="i_cat")
        with ib:
            i_cond = st.selectbox("Condition", ["Working", "Needs Repair", "For Parts Only",
                "Unknown"], key="i_cond")
        if st.button("💾 Save Item", key="save_inventory"):
            if i_name:
                result = api_post(f"{AUTH_URL}/profile/{st.session_state.user_email}/inventory", {
                    "item_name": i_name, "description": i_desc,
                    "category": i_cat, "condition": i_cond,
                })
                if not isinstance(result, APIError):
                    st.success("Item saved to garage!")
                    st.rerun()

    # ── TOKEN BALANCE ──
    st.markdown("---")
    st.markdown("#### ⚡ Token Balance")
    tok = api_get(f"{BILLING_URL}/billing/tokens/{st.session_state.user_email}", timeout=5.0)
    if not isinstance(tok, APIError):
        t_balance = tok.get("token_balance", 0)
        t_purchased = tok.get("tokens_purchased", 0)
        t_used = tok.get("tokens_used", 0)
        t_sub = tok.get("sub_tier")
        tc1, tc2, tc3 = st.columns(3)
        tc1.metric("Balance", f"{t_balance}⚡")
        tc2.metric("Total Purchased", t_purchased)
        tc3.metric("Total Used", t_used)
        if t_sub:
            st.info(f"Active subscription: **{t_sub.upper()}** ({tok.get('sub_tokens_monthly', 0)} tokens/month)")
        st.link_button("⚡ BUY MORE TOKENS", STRIPE_SPARK, use_container_width=True)
