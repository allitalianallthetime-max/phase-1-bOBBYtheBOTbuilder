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

    # ── HERO ──
    st.markdown("""
        <style>
            .bf-hero { text-align:center; padding:50px 20px 40px;
                       background:linear-gradient(180deg, #0F172A 0%, #1E293B 50%, #0F172A 100%);
                       border-radius:16px; margin-bottom:30px; border:1px solid #1E293B; }
            .bf-hero h1 { font-size:56px; margin:0; letter-spacing:2px;
                          background:linear-gradient(90deg, #FF4500, #F97316, #FF4500);
                          -webkit-background-clip:text; -webkit-text-fill-color:transparent;
                          animation: bf-glow 3s ease-in-out infinite alternate; }
            @keyframes bf-glow {
                from { filter: drop-shadow(0 0 12px rgba(255,69,0,0.4)); }
                to   { filter: drop-shadow(0 0 30px rgba(255,69,0,0.7)); }
            }
            .bf-cta { display:inline-block; background:#FF4500; color:white !important;
                      padding:14px 44px; border-radius:999px; text-decoration:none;
                      font-weight:700; font-size:17px;
                      box-shadow:0 8px 25px rgba(255,69,0,0.35);
                      transition: all 0.3s ease; }
            .bf-cta:hover { transform:translateY(-2px);
                            box-shadow:0 12px 35px rgba(255,69,0,0.5); }
            .bf-mode-card { background:linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
                            border-radius:16px; padding:32px 22px; text-align:center;
                            min-height:340px; transition:all 0.3s ease; }
            .bf-mode-card:hover { transform:translateY(-4px); }
            .bf-feature-card { background:#1E293B; border-radius:10px; padding:18px;
                               flex:1; min-width:250px; max-width:280px;
                               transition:all 0.25s ease; }
            .bf-feature-card:hover { transform:translateY(-2px);
                                     box-shadow:0 8px 20px rgba(0,0,0,0.3); }
        </style>

        <div class="bf-hero">
            <h1>THE BUILDER FOUNDRY</h1>
            <p style="color:#E2E8F0; font-size:24px; margin:20px auto 0; max-width:780px; line-height:1.5;">
                Three AI agents. Real web research. Real results.</p>
            <p style="color:#94A3B8; font-size:16px; margin:8px auto 28px; max-width:650px;">
                Build from scrap. Diagnose any engine. Verify any repair quote.</p>
            <a href="#trial-section" class="bf-cta">START YOUR FREE BUILD →</a>
        </div>
    """, unsafe_allow_html=True)

    if os.path.exists("hero_banner.jpg"):
        st.image("hero_banner.jpg", use_container_width=True)

    # ── THREE MODES ──
    st.markdown("""
        <div style='text-align:center; margin:50px 0 24px;'>
          <h2 style='color:#E2E8F0; font-size:34px; letter-spacing:-1px;'>One Platform. Three Superpowers.</h2>
        </div>
    """, unsafe_allow_html=True)

    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown("""
            <div class="bf-mode-card" style="border:2px solid #FF4500;
                        box-shadow: 0 4px 20px rgba(255,69,0,0.1);">
              <div style='font-size:56px; margin-bottom:16px;'>&#9881;&#65039;</div>
              <div style='color:#FF4500; font-weight:800; font-size:22px;
                          letter-spacing:1px;'>BLUEPRINT FORGE</div>
              <div style='color:#64748B; font-size:11px; letter-spacing:2px;
                          margin:8px 0 20px;'>FOR BUILDERS &amp; MAKERS</div>
              <div style='color:#CBD5E1; font-size:14px; line-height:1.7;'>
                Tell us what junk you have and what you want to build.
                Three AI agents analyze every component, search real maker projects,
                and generate a complete blueprint with technical schematics — using
                <strong style='color:#FF4500;'>only your parts</strong>.</div>
              <div style='color:#F59E0B; font-size:12px; margin-top:20px;
                          border-top:1px solid #334155; padding-top:12px;'>
                Robots &#8226; Go-karts &#8226; Solar rigs &#8226; Shop tools
                &#8226; Home automation &#8226; Anything</div>
            </div>
        """, unsafe_allow_html=True)
    with m2:
        st.markdown("""
            <div class="bf-mode-card" style="border:2px solid #10B981;
                        box-shadow: 0 4px 20px rgba(16,185,129,0.1);">
              <div style='font-size:56px; margin-bottom:16px;'>&#128295;</div>
              <div style='color:#10B981; font-weight:800; font-size:22px;
                          letter-spacing:1px;'>FIELD MECHANIC</div>
              <div style='color:#64748B; font-size:11px; letter-spacing:2px;
                          margin:8px 0 20px;'>FOR MECHANICS &amp; TECHS</div>
              <div style='color:#CBD5E1; font-size:14px; line-height:1.7;'>
                Enter your vehicle, engine, symptoms, and tools on hand.
                AI diagnoses the problem, searches real forums for verified fixes,
                finds TSBs and recalls, and writes a step-by-step repair procedure
                with <strong style='color:#10B981;'>real torque specs and part prices</strong>.</div>
              <div style='color:#F59E0B; font-size:12px; margin-top:20px;
                          border-top:1px solid #334155; padding-top:12px;'>
                Marine &#8226; Automotive &#8226; Heavy equipment
                &#8226; Agricultural &#8226; Any engine</div>
            </div>
        """, unsafe_allow_html=True)
    with m3:
        st.markdown("""
            <div class="bf-mode-card" style="border:2px solid #3B82F6;
                        box-shadow: 0 4px 20px rgba(59,130,246,0.1);">
              <div style='font-size:56px; margin-bottom:16px;'>&#128737;&#65039;</div>
              <div style='color:#3B82F6; font-weight:800; font-size:22px;
                          letter-spacing:1px;'>QUOTE CHECKER</div>
              <div style='color:#64748B; font-size:11px; letter-spacing:2px;
                          margin:8px 0 20px;'>FOR EVERY VEHICLE OWNER</div>
              <div style='color:#CBD5E1; font-size:14px; line-height:1.7;'>
                Got a repair quote? We check it against real repair data,
                search for recalls and extended warranties, and tell you
                if the price is <strong style='color:#3B82F6;'>fair or a ripoff</strong>.
                Know what to say before you go back to the shop.</div>
              <div style='color:#F59E0B; font-size:12px; margin-top:20px;
                          border-top:1px solid #334155; padding-top:12px;'>
                Cars &#8226; Trucks &#8226; Boats &#8226; RVs
                &#8226; Any vehicle &#8226; Any repair</div>
            </div>
        """, unsafe_allow_html=True)

    # ── ALLDATA KILLER STAT ──
    st.markdown("""
        <div style='max-width:900px; margin:50px auto; padding:36px;
                    background:linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                    border-radius:16px; border:1px solid #334155; text-align:center;'>
          <div style='display:flex; justify-content:center; gap:50px; flex-wrap:wrap;'>
            <div>
              <div style='color:#EF4444; font-size:44px; font-weight:800;'>$199/mo</div>
              <div style='color:#64748B; font-size:14px; margin-top:4px;'>AllData charges this.<br>Static data. Annual lock-in.</div>
            </div>
            <div style='border-left:1px solid #334155; padding-left:50px;'>
              <div style='color:#10B981; font-size:44px; font-weight:800;'>$3.33</div>
              <div style='color:#64748B; font-size:14px; margin-top:4px;'>We charge per diagnosis.<br>AI-powered. Live web research.</div>
            </div>
            <div style='border-left:1px solid #334155; padding-left:50px;'>
              <div style='color:#F59E0B; font-size:44px; font-weight:800;'>4</div>
              <div style='color:#64748B; font-size:14px; margin-top:4px;'>Frontier AI models<br>on YOUR specific problem.</div>
            </div>
          </div>
        </div>
    """, unsafe_allow_html=True)

    # ── FIELD MECHANIC DEEP DIVE ──
    st.markdown("""
        <div style='text-align:center; margin:50px 0 24px;'>
          <h2 style='color:#10B981; font-size:32px;'>Field Mechanic — Your AI Repair Crew</h2>
          <p style='color:#94A3B8; font-size:16px; max-width:720px; margin:10px auto;'>
            Stranded on a boat? Stuck on a job site? Dead engine and no cell signal to Google?
            Run a diagnosis with the tools you have. Get a real repair procedure — not generic advice.</p>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div style='max-width:900px; margin:0 auto;'>
          <div style='display:flex; gap:12px; flex-wrap:wrap; justify-content:center;'>
            <div style='background:#1E293B; border-radius:10px; padding:18px; flex:1;
                        min-width:250px; max-width:280px; border-left:3px solid #10B981;'>
              <div style='color:#10B981; font-size:13px; font-weight:bold;'>&#9654; Diagnostic Flowchart</div>
              <div style='color:#94A3B8; font-size:12px; margin-top:4px;'>
                Failure tree analysis — "if X, check Y. If Y fails, it's Z."</div>
            </div>
            <div style='background:#1E293B; border-radius:10px; padding:18px; flex:1;
                        min-width:250px; max-width:280px; border-left:3px solid #10B981;'>
              <div style='color:#10B981; font-size:13px; font-weight:bold;'>&#9654; Step-by-Step Repair</div>
              <div style='color:#94A3B8; font-size:12px; margin-top:4px;'>
                Written for YOUR tools and parts — not a shop manual.</div>
            </div>
            <div style='background:#1E293B; border-radius:10px; padding:18px; flex:1;
                        min-width:250px; max-width:280px; border-left:3px solid #10B981;'>
              <div style='color:#10B981; font-size:13px; font-weight:bold;'>&#9654; Torque Specs &amp; Measurements</div>
              <div style='color:#94A3B8; font-size:12px; margin-top:4px;'>
                Real specs for the exact engine. Marked [KNOWN] or [EST].</div>
            </div>
            <div style='background:#1E293B; border-radius:10px; padding:18px; flex:1;
                        min-width:250px; max-width:280px; border-left:3px solid #F59E0B;'>
              <div style='color:#F59E0B; font-size:13px; font-weight:bold;'>&#9654; Emergency Jury-Rig</div>
              <div style='color:#94A3B8; font-size:12px; margin-top:4px;'>
                Temp fix to get home safe. Includes risks of the workaround.</div>
            </div>
            <div style='background:#1E293B; border-radius:10px; padding:18px; flex:1;
                        min-width:250px; max-width:280px; border-left:3px solid #EF4444;'>
              <div style='color:#EF4444; font-size:13px; font-weight:bold;'>&#9654; "Do NOT Do This"</div>
              <div style='color:#94A3B8; font-size:12px; margin-top:4px;'>
                Common mistakes that make the problem WORSE.</div>
            </div>
            <div style='background:#1E293B; border-radius:10px; padding:18px; flex:1;
                        min-width:250px; max-width:280px; border-left:3px solid #3B82F6;'>
              <div style='color:#3B82F6; font-size:13px; font-weight:bold;'>&#9654; Real Parts &amp; Prices</div>
              <div style='color:#94A3B8; font-size:12px; margin-top:4px;'>
                Part numbers + live pricing from RockAuto, Amazon, dealer sites.</div>
            </div>
            <div style='background:#1E293B; border-radius:10px; padding:18px; flex:1;
                        min-width:250px; max-width:280px; border-left:3px solid #A855F7;'>
              <div style='color:#A855F7; font-size:13px; font-weight:bold;'>&#9654; Forum Fixes &amp; TSBs</div>
              <div style='color:#94A3B8; font-size:12px; margin-top:4px;'>
                Gemini searches real mechanic forums and finds verified fixes.</div>
            </div>
            <div style='background:#1E293B; border-radius:10px; padding:18px; flex:1;
                        min-width:250px; max-width:280px; border-left:3px solid #06B6D4;'>
              <div style='color:#06B6D4; font-size:13px; font-weight:bold;'>&#9654; YouTube Walkthroughs</div>
              <div style='color:#94A3B8; font-size:12px; margin-top:4px;'>
                Links to actual repair videos for your specific engine and problem.</div>
            </div>
          </div>
        </div>
    """, unsafe_allow_html=True)

    # ── QUOTE CHECKER PITCH ──
    st.markdown("""
        <div style='text-align:center; margin:40px 0 20px;'>
          <h2 style='color:#3B82F6; font-size:32px;'>Quote Checker — Stop Overpaying For Repairs</h2>
          <p style='color:#94A3B8; font-size:15px; max-width:700px; margin:8px auto;'>
            Your mechanic says $2,400 for an AC repair. Is that fair? Or are you getting robbed?
            We check it in 60 seconds for $3.33.</p>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div style='max-width:800px; margin:0 auto;'>
          <div style='background:linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
                      border-radius:12px; padding:28px; border:1px solid #3B82F6;'>
            <div style='display:flex; gap:24px; flex-wrap:wrap; justify-content:center;'>
              <div style='flex:1; min-width:280px;'>
                <div style='color:#EF4444; font-size:11px; font-weight:bold;
                            letter-spacing:2px; margin-bottom:8px;'>THE QUOTE</div>
                <div style='color:#E2E8F0; font-size:20px;'>2022 Toyota Highlander — AC Repair</div>
                <div style='color:#EF4444; font-size:32px; font-weight:bold; margin:4px 0;'>$2,400</div>
              </div>
              <div style='flex:1; min-width:280px;'>
                <div style='color:#10B981; font-size:11px; font-weight:bold;
                            letter-spacing:2px; margin-bottom:8px;'>OUR ANALYSIS</div>
                <div style='color:#10B981; font-size:16px; font-weight:bold;'>
                  &#128680; THIS QUOTE IS HIGH</div>
                <div style='color:#E2E8F0; font-size:15px; margin-top:4px;'>
                  Fair range: <strong style='color:#10B981;'>$650 — $950</strong></div>
                <div style='color:#F59E0B; font-size:14px; margin-top:8px;'>
                  &#9888;&#65039; Toyota covers this free under 60K miles!</div>
                <div style='color:#94A3B8; font-size:13px; margin-top:8px; line-height:1.6;'>
                  &#10003; Recall &amp; warranty check<br>
                  &#10003; Fair cost breakdown with real part prices<br>
                  &#10003; What to say when you call the shop back<br>
                  &#10003; NHTSA complaint data (187 complaints filed)</div>
              </div>
            </div>
          </div>
        </div>
    """, unsafe_allow_html=True)

    # ── HOW THE AI WORKS ──
    st.markdown("""
        <div style='text-align:center; margin:40px 0 20px;'>
          <h2 style='color:#E2E8F0; font-size:32px;'>The AI Round Table</h2>
          <p style='color:#64748B; font-size:15px;'>Three agents. Working in parallel. Real web research.</p>
        </div>
    """, unsafe_allow_html=True)

    a1, a2, a3 = st.columns(3)
    with a1:
        st.markdown("""
            <div style='background:linear-gradient(180deg, #1E293B 0%, #0F172A 100%);
                        border-radius:12px; padding:24px;
                        border-top:3px solid #F97316; text-align:center; min-height:280px;'>
              <div style='font-size:36px; margin-bottom:8px;'>&#129504;</div>
              <div style='color:#F97316; font-weight:bold; font-size:18px;'>GROK-4.2</div>
              <div style='color:#64748B; font-size:11px; letter-spacing:1px;
                          margin-bottom:12px;'>THE BRAIN</div>
              <div style='color:#94A3B8; font-size:13px; line-height:1.6;'>
                Deep technical analysis. Failure tree diagnosis. Full spec sheets
                for your exact engine. Cross-references what you already tried.
                Identifies every harvestable component from your junk.</div>
              <div style='color:#F97316; font-size:11px; margin-top:12px;
                          padding-top:8px; border-top:1px solid #334155;'>
                Powered by xAI Grok 4.2</div>
            </div>
        """, unsafe_allow_html=True)
    with a2:
        st.markdown("""
            <div style='background:linear-gradient(180deg, #1E293B 0%, #0F172A 100%);
                        border-radius:12px; padding:24px;
                        border-top:3px solid #10B981; text-align:center; min-height:280px;'>
              <div style='font-size:36px; margin-bottom:8px;'>&#128269;</div>
              <div style='color:#10B981; font-weight:bold; font-size:18px;'>GEMINI 2.5</div>
              <div style='color:#64748B; font-size:11px; letter-spacing:1px;
                          margin-bottom:12px;'>THE SEARCHER</div>
              <div style='color:#94A3B8; font-size:13px; line-height:1.6;'>
                Searches the ACTUAL web — forums, TSBs, NHTSA recalls,
                YouTube repair videos, parts pricing from RockAuto and Amazon,
                Instructables projects, and real mechanic-verified fixes.</div>
              <div style='color:#10B981; font-size:11px; margin-top:12px;
                          padding-top:8px; border-top:1px solid #334155;'>
                Google Search Grounding + Gemini Flash</div>
            </div>
        """, unsafe_allow_html=True)
    with a3:
        st.markdown("""
            <div style='background:linear-gradient(180deg, #1E293B 0%, #0F172A 100%);
                        border-radius:12px; padding:24px;
                        border-top:3px solid #3B82F6; text-align:center; min-height:280px;'>
              <div style='font-size:36px; margin-bottom:8px;'>&#128221;</div>
              <div style='color:#3B82F6; font-weight:bold; font-size:18px;'>CLAUDE SONNET</div>
              <div style='color:#64748B; font-size:11px; letter-spacing:1px;
                          margin-bottom:12px;'>THE WRITER</div>
              <div style='color:#94A3B8; font-size:13px; line-height:1.6;'>
                Synthesizes everything from Grok and Gemini into a complete
                document — blueprints with schematics, repair procedures with
                torque specs, or quote analyses with fair pricing breakdowns.</div>
              <div style='color:#3B82F6; font-size:11px; margin-top:12px;
                          padding-top:8px; border-top:1px solid #334155;'>
                Anthropic Claude Sonnet 4</div>
            </div>
        """, unsafe_allow_html=True)

    # ── FEATURES GRID ──
    st.markdown("""
        <div style='text-align:center; margin:40px 0 20px;'>
          <h2 style='color:#E2E8F0; font-size:32px;'>Everything Included</h2>
        </div>
        <div style='max-width:900px; margin:0 auto; padding:0 20px;'>
          <div style='display:flex; gap:16px; flex-wrap:wrap; justify-content:center;'>
            <div style='background:#1E293B; border-radius:8px; padding:20px;
                        flex:1; min-width:250px; max-width:280px; text-align:center;'>
              <div style='font-size:28px;'>&#128208;</div>
              <div style='color:#E2E8F0; font-size:14px; font-weight:bold; margin-top:8px;'>
                Technical Schematics</div>
              <div style='color:#64748B; font-size:12px; margin-top:4px;'>
                Auto-generated SVG engineering drawings with every blueprint build.</div>
            </div>
            <div style='background:#1E293B; border-radius:8px; padding:20px;
                        flex:1; min-width:250px; max-width:280px; text-align:center;'>
              <div style='font-size:28px;'>&#128248;</div>
              <div style='color:#E2E8F0; font-size:14px; font-weight:bold; margin-top:8px;'>
                Equipment Scanner</div>
              <div style='color:#64748B; font-size:12px; margin-top:4px;'>
                Upload a photo. Gemini Vision identifies every harvestable component.</div>
            </div>
            <div style='background:#1E293B; border-radius:8px; padding:20px;
                        flex:1; min-width:250px; max-width:280px; text-align:center;'>
              <div style='font-size:28px;'>&#128100;</div>
              <div style='color:#E2E8F0; font-size:14px; font-weight:bold; margin-top:8px;'>
                Save Your Vehicles</div>
              <div style='color:#64748B; font-size:12px; margin-top:4px;'>
                Profile with saved vehicles and garage inventory. One-tap re-diagnosis.</div>
            </div>
            <div style='background:#1E293B; border-radius:8px; padding:20px;
                        flex:1; min-width:250px; max-width:280px; text-align:center;'>
              <div style='font-size:28px;'>&#128203;</div>
              <div style='color:#E2E8F0; font-size:14px; font-weight:bold; margin-top:8px;'>
                Free Invoice Generator</div>
              <div style='color:#64748B; font-size:12px; margin-top:4px;'>
                Generate professional repair estimates from any diagnosis. Free with every build.</div>
            </div>
            <div style='background:#1E293B; border-radius:8px; padding:20px;
                        flex:1; min-width:250px; max-width:280px; text-align:center;'>
              <div style='font-size:28px;'>&#128200;</div>
              <div style='color:#E2E8F0; font-size:14px; font-weight:bold; margin-top:8px;'>
                Community Intelligence</div>
              <div style='color:#64748B; font-size:12px; margin-top:4px;'>
                See how many others had this problem. Average costs. Most common root causes.</div>
            </div>
            <div style='background:#1E293B; border-radius:8px; padding:20px;
                        flex:1; min-width:250px; max-width:280px; text-align:center;'>
              <div style='font-size:28px;'>&#129504;</div>
              <div style='color:#E2E8F0; font-size:14px; font-weight:bold; margin-top:8px;'>
                Conception DNA</div>
              <div style='color:#64748B; font-size:12px; margin-top:4px;'>
                Every build trains the AI. The more people use it, the smarter it gets.</div>
            </div>
          </div>
        </div>
    """, unsafe_allow_html=True)

    # ── E-WASTE / SUSTAINABILITY ──
    st.markdown("""
        <div style='max-width:820px; margin:50px auto; padding:28px;
                    background:linear-gradient(135deg, #064e3b 0%, #0F172A 100%);
                    border-radius:16px; border:1px solid #10B981; text-align:center;'>
          <div style='color:#10B981; font-size:14px; font-weight:bold; letter-spacing:3px;
                      margin-bottom:10px;'>REDUCE. REUSE. REBUILD.</div>
          <div style='color:#E2E8F0; font-size:26px; font-weight:bold; margin-bottom:14px;'>
            Fight E-Waste With Every Build</div>
          <div style='color:#94A3B8; font-size:14px; line-height:1.8; max-width:650px;
                      margin:0 auto;'>
            53 million tons of e-waste are generated every year. Only 17% gets recycled.
            The rest sits in landfills leaching lead, mercury, and cadmium into the ground.<br><br>
            Every blueprint from The Builder Foundry turns trash into something useful.
            That old treadmill isn't garbage — it's a motor, a frame, a belt drive system,
            and a linear actuator waiting to become something new.<br><br>
            <strong style='color:#10B981;'>Stop throwing things away. Start building.</strong></div>
        </div>
    """, unsafe_allow_html=True)

    # ── FREE TRIAL ──
    st.markdown("---")
    st.markdown("""
        <div style='text-align:center; margin:20px 0 12px;'>
          <div id="trial-section"></div>
          <h2 style='color:#10B981; font-size:36px;'>Try 1 Free Build — No Card Needed</h2>
          <p style='color:#94A3B8; font-size:16px;'>Build a blueprint, diagnose an engine, or check a quote — free.</p>
        </div>
    """, unsafe_allow_html=True)

    t1, t2, t3 = st.columns([1, 1.2, 1])
    with t2:
        trial_email = st.text_input("Email Address", placeholder="you@example.com",
                                    key="trial_email")
        email_optin = st.checkbox(
            "I agree to receive updates, tips, and new feature announcements from The Builder Foundry.",
            value=True, key="trial_optin"
        )
        st.markdown(
            "<div style='color:#475569; font-size:10px; margin-top:-8px; margin-bottom:8px;'>"
            "We respect your inbox. Unsubscribe anytime.</div>",
            unsafe_allow_html=True
        )
        if st.button("🚀 GET MY FREE BUILD", use_container_width=True):
            if not trial_email or "@" not in trial_email:
                st.warning("Enter a valid email address.")
            elif not email_optin:
                st.warning("Please agree to receive updates to activate your free trial.")
            else:
                with st.spinner("Creating your trial license..."):
                    result = api_post(
                        f"{AUTH_URL}/auth/trial",
                        {"email": trial_email.strip().lower(), "email_optin": True}
                    )
                    if isinstance(result, APIError):
                        if result.status == 409:
                            st.warning(result.detail)
                        elif result.status == 429:
                            st.warning("Too many trial requests. Please wait a few minutes.")
                        else:
                            st.error(result.detail)
                    else:
                        trial_key = result.get("key", "")
                        st.success(f"Your license key: **{trial_key}**")
                        st.info("Copy this key and use it to log in below. You have 1 free build and 7 days!")

    # ── TOKEN PACKS ──
    st.markdown("""
        <div style='text-align:center; margin:40px 0 12px;'>
          <h2 style='color:#E2E8F0; font-size:32px;'>Buy Tokens — Pay Per Build</h2>
          <p style='color:#64748B; font-size:14px;'>No subscription. No commitment. Tokens never expire.</p>
          <p style='color:#94A3B8; font-size:12px; margin-top:4px;'>
            Standard builds = 1⚡ &nbsp;|&nbsp; Industrial = 3⚡ &nbsp;|&nbsp; Experimental = 5⚡</p>
        </div>
    """, unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown("""
            <div style='background:#1E293B; padding:24px 16px; border-radius:8px;
                        border:1px solid #334155; text-align:center;'>
              <div style='color:#94A3B8; font-size:11px; font-weight:bold;
                          letter-spacing:2px;'>SPARK</div>
              <div style='color:white; font-size:32px; font-weight:bold; margin:8px 0;'>
                3⚡</div>
              <div style='color:#FF4500; font-size:24px; font-weight:bold;'>$9.99</div>
              <div style='color:#64748B; font-size:12px; margin-top:4px;'>$3.33 per token</div>
            </div>
        """, unsafe_allow_html=True)
        st.link_button("⚡ GET SPARK", STRIPE_SPARK, use_container_width=True)
    with k2:
        st.markdown("""
            <div style='background:#1E293B; padding:24px 16px; border-radius:8px;
                        border:2px solid #FF4500; text-align:center;
                        box-shadow:0 0 20px rgba(255,69,0,0.15);'>
              <div style='color:#FF4500; font-size:11px; font-weight:bold;
                          letter-spacing:2px;'>BUILDER ★</div>
              <div style='color:white; font-size:32px; font-weight:bold; margin:8px 0;'>
                10⚡</div>
              <div style='color:#FF4500; font-size:24px; font-weight:bold;'>$24.99</div>
              <div style='color:#64748B; font-size:12px; margin-top:4px;'>$2.50 per token</div>
            </div>
        """, unsafe_allow_html=True)
        st.link_button("🔥 GET BUILDER", STRIPE_BUILDER, use_container_width=True)
    with k3:
        st.markdown("""
            <div style='background:#1E293B; padding:24px 16px; border-radius:8px;
                        border:1px solid #334155; text-align:center;'>
              <div style='color:#10B981; font-size:11px; font-weight:bold;
                          letter-spacing:2px;'>FOUNDRY</div>
              <div style='color:white; font-size:32px; font-weight:bold; margin:8px 0;'>
                30⚡</div>
              <div style='color:#10B981; font-size:24px; font-weight:bold;'>$59.99</div>
              <div style='color:#64748B; font-size:12px; margin-top:4px;'>$2.00 per token</div>
            </div>
        """, unsafe_allow_html=True)
        st.link_button("🔧 GET FOUNDRY", STRIPE_FOUNDRY, use_container_width=True)
    with k4:
        st.markdown("""
            <div style='background:#1E293B; padding:24px 16px; border-radius:8px;
                        border:1px solid #FFD700; text-align:center;'>
              <div style='color:#FFD700; font-size:11px; font-weight:bold;
                          letter-spacing:2px;'>SHOP PASS</div>
              <div style='color:white; font-size:32px; font-weight:bold; margin:8px 0;'>
                100⚡</div>
              <div style='color:#FFD700; font-size:24px; font-weight:bold;'>$149.99</div>
              <div style='color:#64748B; font-size:12px; margin-top:4px;'>$1.50 per token</div>
            </div>
        """, unsafe_allow_html=True)
        st.link_button("👑 GET SHOP PASS", STRIPE_SHOPPASS, use_container_width=True)

    # ── SUBSCRIPTIONS ──
    st.markdown("""
        <div style='text-align:center; margin:30px 0 12px;'>
          <h3 style='color:#94A3B8; font-size:20px;'>Build All The Time? Subscribe &amp; Save</h3>
          <p style='color:#64748B; font-size:13px;'>Monthly token refill. Unused tokens roll over forever. Cancel anytime.</p>
        </div>
    """, unsafe_allow_html=True)

    s1, s2, s3 = st.columns([1, 1, 1])
    with s1:
        st.markdown("&nbsp;")
    with s2:
        st.markdown("""
            <div style='background:#1E293B; padding:20px; border-radius:8px;
                        border:1px solid #3B82F6; text-align:center;'>
              <div style='color:#3B82F6; font-size:11px; font-weight:bold;
                          letter-spacing:2px;'>PRO — 20⚡/MONTH</div>
              <div style='color:white; font-size:28px; font-weight:bold; margin:8px 0;'>
                $29.99<span style='font-size:14px; color:#94A3B8;'>/mo</span></div>
              <div style='color:#64748B; font-size:12px;'>$1.50/token &bull; Unlimited rollover</div>
            </div>
        """, unsafe_allow_html=True)
        st.link_button("📋 SUBSCRIBE PRO", STRIPE_PRO_SUB, use_container_width=True)
    with s3:
        st.markdown("""
            <div style='background:#1E293B; padding:20px; border-radius:8px;
                        border:1px solid #A855F7; text-align:center;'>
              <div style='color:#A855F7; font-size:11px; font-weight:bold;
                          letter-spacing:2px;'>MASTER — 60⚡/MONTH</div>
              <div style='color:white; font-size:28px; font-weight:bold; margin:8px 0;'>
                $74.99<span style='font-size:14px; color:#94A3B8;'>/mo</span></div>
              <div style='color:#64748B; font-size:12px;'>$1.25/token &bull; Unlimited rollover</div>
            </div>
        """, unsafe_allow_html=True)
        st.link_button("🚀 SUBSCRIBE MASTER", STRIPE_MASTER_SUB, use_container_width=True)

    # ── THE STORY ──
    st.markdown("""
        <div style='max-width:750px; margin:40px auto; text-align:center; padding:0 20px;'>
          <h2 style='color:#E2E8F0; font-size:24px; margin-bottom:12px;'>Built From Scraps. Literally.</h2>
          <p style='color:#94A3B8; font-size:14px; line-height:1.8;'>
            The Builder Foundry was created by a self-taught developer who pieces together
            computers from salvaged parts and builds things from scrap. No CS degree. No VC funding.
            Just a garage, a vision, and a refusal to stop learning.<br><br>
            As a mechanic, I watched people get overcharged every day for repairs they didn't
            understand. As a builder, I watched perfectly good parts get thrown in landfills.
            This tool fixes both problems.<br><br>
            This is Phase 1 of <strong style='color:#FF4500;'>Conception</strong> —
            an advanced AI being built to learn from every blueprint, every diagnosis,
            and every repair. Every time you use the Foundry, Conception gets smarter.
            It learns what works, what doesn't, and what things really cost.<br><br>
            <span style='color:#10B981; font-weight:bold;'>
              Builders. Mechanics. Vehicle owners. We're all on the same team.</span></p>
        </div>
    """, unsafe_allow_html=True)

    # ── LOGIN ──
    st.markdown("---")
    st.markdown("""
        <div style='text-align:center; margin-bottom:12px;'>
          <h3 style='color:#FF4500;'>Already Have a License?</h3>
        </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        license_key = st.text_input("License Key", type="password",
                                    placeholder="BOB-XXXX-XXXX-XXXX")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("AUTHORIZE", use_container_width=True):
                if not license_key:
                    st.warning("Enter a license key.")
                else:
                    with st.spinner("Verifying credentials..."):
                        result = api_post(
                            f"{AUTH_URL}/verify-license",
                            {"license_key": license_key}
                        )
                        if isinstance(result, APIError):
                            if result.status == 429:
                                st.warning("Too many login attempts. Wait a few minutes.")
                            else:
                                st.error(result.detail)
                        else:
                            st.session_state.logged_in  = True
                            st.session_state.user_email = result["email"]
                            st.session_state.user_name  = result["name"]
                            st.session_state.tier       = result["tier"]
                            st.session_state.jwt_token  = result["token"]
                            st.rerun()
        with col_b:
            st.link_button("BUY TOKENS", STRIPE_SPARK, use_container_width=True)

    # ── FOOTER ──
    st.markdown("""
        <div style='text-align:center; padding:40px 0 20px; color:#475569; font-size:12px;'>
          AoC3P0 Systems &nbsp;|&nbsp; The Builder Foundry &nbsp;|&nbsp; Conception DNA Architecture<br>
          <span style='color:#334155;'>bobtherobotbuilder.com</span>
        </div>
    """, unsafe_allow_html=True)
    st.stop()


    # ══════════════════════════════════════════════════════════════════════════════
