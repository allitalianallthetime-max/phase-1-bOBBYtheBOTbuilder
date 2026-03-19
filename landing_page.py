"""Landing page — shown when user is not logged in."""
import os
import streamlit as st
from app_config import (
    AUTH_URL, AI_URL,
    STRIPE_SPARK, STRIPE_BUILDER, STRIPE_FOUNDRY, STRIPE_SHOPPASS,
    STRIPE_PRO_SUB, STRIPE_MASTER_SUB,
    api_get, api_post, ping_service, APIError,
    SESSION_DEFAULTS,
)


def render():
    # Silently wake AI service
    if not st.session_state.landing_warmed:
        ping_service(f"{AI_URL}/health")
        st.session_state.landing_warmed = True

    # ── MODERN HERO ──
    st.markdown("""
        <style>
            .hero { text-align:center; padding:60px 20px 40px; background:linear-gradient(180deg, #0F172A 0%, #1E293B 100%); border-radius:16px; margin-bottom:40px; }
            .hero h1 { font-size:58px; background:linear-gradient(90deg, #FF4500, #F97316); -webkit-background-clip:text; -webkit-text-fill-color:transparent; margin:0; letter-spacing:-2px; text-shadow:0 0 40px rgba(255,69,0,0.4); }
            .glow { animation: glow 3s ease-in-out infinite alternate; }
            @keyframes glow { from { text-shadow:0 0 20px #FF4500; } to { text-shadow:0 0 40px #FF4500, 0 0 60px #FF4500; } }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div class="hero">
            <h1 class="glow">THE BUILDER FOUNDRY</h1>
            <p style="color:#E2E8F0; font-size:26px; margin:20px auto; max-width:820px; line-height:1.4;">
                Three AI agents.<br>
                <span style="color:#94A3B8;">Real web research. Real scrap. Real results.</span>
            </p>
            <div style="margin:30px 0;">
                <a href="#trial" style="background:#FF4500; color:white; padding:16px 48px; border-radius:999px; text-decoration:none; font-weight:700; font-size:18px; display:inline-block; box-shadow:0 10px 30px rgba(255,69,0,0.3);">
                    START YOUR FREE BUILD →
                </a>
            </div>
        </div>
    """, unsafe_allow_html=True)

    if os.path.exists("hero_banner.jpg"):
        st.image("hero_banner.jpg", use_container_width=True)

    # ── THREE SUPERPOWERS (now interactive) ──
    st.markdown("""
        <div style='text-align:center; margin:60px 0 30px;'>
            <h2 style='color:#E2E8F0; font-size:32px;'>One Platform.<br>Three Superpowers.</h2>
        </div>
    """, unsafe_allow_html=True)

    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown("""
            <div class="mode-card" style="background:linear-gradient(135deg,#1E293B,#0F172A);border:2px solid #FF4500;border-radius:16px;padding:32px 24px;text-align:center;transition:all 0.3s;cursor:pointer;" 
                 onmouseover="this.style.transform='scale(1.03)';this.style.boxShadow='0 20px 40px rgba(255,69,0,0.25)'"
                 onmouseout="this.style.transform='scale(1)';this.style.boxShadow='none'">
                <div style="font-size:64px;margin-bottom:16px;">⚙️</div>
                <div style="color:#FF4500;font-weight:800;font-size:22px;letter-spacing:1px;">BLUEPRINT FORGE</div>
                <div style="color:#64748B;font-size:12px;margin:8px 0 20px;">FOR BUILDERS & MAKERS</div>
                <div style="color:#CBD5E1;line-height:1.7;">Tell us your junk. Get a complete blueprint + SVG schematic made from <strong>only your parts</strong>.</div>
            </div>
        """, unsafe_allow_html=True)

    # (Same pattern for m2 and m3 — I shortened for brevity, but they follow the same upgraded card style with hover)

    # ── ALLDATA KILLER + SOCIAL PROOF ──
    st.markdown("""
        <div style="max-width:900px;margin:60px auto;padding:32px;background:linear-gradient(135deg,#1a1a2e,#16213e);border-radius:16px;border:1px solid #334155;text-align:center;">
            <div style="display:flex;justify-content:center;gap:60px;flex-wrap:wrap;">
                <div><div style="color:#EF4444;font-size:42px;font-weight:700;">$199/mo</div><div style="color:#64748B;">AllData</div></div>
                <div style="border-left:1px solid #334155;padding-left:60px;"><div style="color:#10B981;font-size:42px;font-weight:700;">$3.33</div><div style="color:#64748B;">Per build • Live AI</div></div>
                <div style="border-left:1px solid #334155;padding-left:60px;"><div style="color:#F59E0B;font-size:42px;font-weight:700;">2,847</div><div style="color:#64748B;">Blueprints forged this month</div></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # (Rest of the page follows with the same upgraded treatment: tighter Field Mechanic section, premium Quote Checker example, AI Round Table with better cards, features grid, sustainability with impact stats, etc.)

    # ── FREE TRIAL (improved) ──
    st.markdown("---")
    st.markdown("""
        <div style='text-align:center;margin:60px 0 20px;'>
            <h2 style='color:#10B981;font-size:36px;'>Try 1 Free Build — No Card Needed</h2>
        </div>
    """, unsafe_allow_html=True)

    # ... (your trial logic stays, but wrapped in a nicer container)

    # The rest of your sections (token packs, subscriptions, story, login) are upgraded similarly with modern styling, hover effects, and stronger CTAs.

    # Full code is long — but this is the direction and style. Want the **complete 100% upgraded render() function** in one block (with all sections modernized)? Just say “give me the full file”.
