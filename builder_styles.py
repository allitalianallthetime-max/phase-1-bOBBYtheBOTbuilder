"""
builder_styles.py
=================
Premium cyberpunk-industrial theme for the AoC3P0 Builder Foundry.
Cinematic neon glows, glassmorphism, fluid animations, and production polish.
"""

BUILDER_CSS = """
<style>
/* ── GOOGLE FONTS ── */
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@400;500;600;700&display=swap');

/* ── ROOT VARIABLES ── */
:root {
  --forge-orange:   #FF4500;
  --forge-dark:     #0A0E17;
  --forge-panel:    #0F1623;
  --forge-card:     #141C2E;
  --forge-border:   #2A3A52;
  --forge-muted:    #64748B;
  --forge-text:     #CBD5E1;
  --forge-bright:   #F1F5F9;
  --forge-gold:     #FFD700;
  --forge-green:    #10B981;
  --forge-blue:     #3B82F6;
  --glow-orange:    0 0 15px rgba(255,69,0,0.5);
  --glow-blue:      0 0 15px rgba(59,130,246,0.4);
  --glass:          rgba(15,22,35,0.85);
}

/* ── GLOBAL RESET ── */
html, body, [data-testid="stAppViewContainer"] {
  background: var(--forge-dark) !important;
  color: var(--forge-text) !important;
  font-family: 'Rajdhani', sans-serif !important;
}

/* ── HIDE STREAMLIT CHROME ── */
#MainMenu, footer, [data-testid="stDecoration"], [data-testid="collapsedControl"] { display: none !important; }

/* ── HEADER ENHANCEMENTS ── */
header[data-testid="stHeader"] {
  background: var(--forge-dark) !important;
  border-bottom: 1px solid #FF4500 !important;
}

/* ── SIDEBAR ── */
[data-testid="stSidebar"] {
  background: var(--forge-panel) !important;
  border-right: 1px solid #FF4500 !important;
}

/* ── BUTTONS ── */
.stButton > button {
  background: transparent !important;
  color: var(--forge-orange) !important;
  border: 1px solid var(--forge-orange) !important;
  border-radius: 4px !important;
  font-family: 'Share Tech Mono', monospace !important;
  font-size: 13px !important;
  letter-spacing: 1.5px !important;
  text-transform: uppercase !important;
  transition: all 0.25s cubic-bezier(0.23,1,0.32,1) !important;
}

.stButton > button:hover {
  background: var(--forge-orange) !important;
  color: #0A0E17 !important;
  box-shadow: var(--glow-orange) !important;
  transform: translateY(-1px);
}

/* Primary action buttons */
.stButton > button[kind="primary"] {
  background: var(--forge-orange) !important;
  color: #0A0E17 !important;
  font-weight: 700 !important;
}

/* ── INPUTS & TEXTAREAS ── */
.stTextInput input, .stTextArea textarea, .stSelectbox select {
  background: var(--glass) !important;
  border: 1px solid var(--forge-border) !important;
  border-radius: 4px !important;
  color: var(--forge-bright) !important;
  font-family: 'Share Tech Mono', monospace !important;
  transition: all 0.2s !important;
}

.stTextInput input:focus, .stTextArea textarea:focus {
  border-color: var(--forge-orange) !important;
  box-shadow: var(--glow-orange) !important;
}

/* ── CARDS & EXPANDERS ── */
.stExpander, .element-container div[style*="background"] {
  background: var(--forge-card) !important;
  border: 1px solid var(--forge-border) !important;
  border-radius: 8px !important;
  transition: all 0.25s ease !important;
}

.stExpander:hover {
  border-color: var(--forge-orange) !important;
  box-shadow: var(--glow-orange) !important;
}

/* ── METRICS ── */
[data-testid="stMetric"] {
  background: var(--forge-card) !important;
  border: 1px solid var(--forge-border) !important;
  border-radius: 8px !important;
  padding: 20px !important;
}

[data-testid="stMetricValue"] {
  color: var(--forge-orange) !important;
  font-size: 32px !important;
  font-weight: 700 !important;
}

/* ── BLUEPRINT OUTPUT ── */
.blueprint-output {
  background: #0F1623 !important;
  border: 1px solid var(--forge-orange) !important;
  border-left-width: 4px !important;
  border-radius: 6px !important;
  padding: 24px !important;
  font-family: 'Share Tech Mono', monospace !important;
  font-size: 13.5px !important;
  line-height: 1.85 !important;
  color: #E2E8F0;
}

/* ── NEON PULSE & GLOW ── */
@keyframes neonPulse {
  0%, 100% { box-shadow: var(--glow-orange); }
  50% { box-shadow: 0 0 25px rgba(255,69,0,0.9); }
}
.pulse { animation: neonPulse 2s ease-in-out infinite; }

/* ── TICKER TAPE ── */
.ticker-tape {
  background: linear-gradient(90deg, #FF4500, #F97316);
  color: #0A0E17;
  font-family: 'Share Tech Mono', monospace;
  font-size: 11px;
  letter-spacing: 3px;
  padding: 5px 0;
  overflow: hidden;
  white-space: nowrap;
}

.ticker-tape span {
  display: inline-block;
  animation: ticker 28s linear infinite;
}

/* ── SCROLLBAR ── */
::-webkit-scrollbar { width: 7px; height: 7px; }
::-webkit-scrollbar-thumb {
  background: var(--forge-orange);
  border-radius: 4px;
}

/* ── VAULT / SCAN CARDS ── */
.vault-item:hover, .scan-result:hover {
  border-color: var(--forge-gold) !important;
  transform: scale(1.02);
  box-shadow: var(--glow-orange) !important;
}
</style>
"""

FORGE_HEADER_HTML = """
<div style="background: linear-gradient(90deg, #0A0E17 0%, #141C2E 50%, #0A0E17 100%); border-bottom: 3px solid #FF4500; padding: 0; margin-bottom: 0;">
  <!-- TICKER TAPE -->
  <div class="ticker-tape pulse">
    <span>
      ⚙️ THE BUILDER FOUNDRY IS ALIVE &nbsp;◆&nbsp;
      ROUND TABLE ACTIVE &nbsp;◆&nbsp;
      GROK-4.2 • CLAUDE SONNET 4 • GEMINI 2.5 &nbsp;◆&nbsp;
      CONCEPTION DNA LEARNING &nbsp;◆&nbsp;
      ALL SYSTEMS NOMINAL &nbsp;◆&nbsp;
      ⚙️ THE BUILDER FOUNDRY IS ALIVE &nbsp;◆&nbsp;
    </span>
  </div>

  <!-- MAIN HEADER -->
  <div style="display:flex; align-items:center; justify-content:space-between; padding:18px 28px;">
    <div>
      <div style="font-family:'Share Tech Mono',monospace; font-size:12px; color:#FF4500; letter-spacing:4px; margin-bottom:2px;">
        AoC3P0 SYSTEMS • PHASE 1
      </div>
      <div style="font-family:'Rajdhani',sans-serif; font-size:38px; font-weight:700; color:#F1F5F9; letter-spacing:2px;">
        THE BUILDER FOUNDRY
      </div>
      <div style="font-family:'Share Tech Mono',monospace; font-size:11px; color:#64748B;">
        MULTI-AGENT ENGINEERING INTELLIGENCE
      </div>
    </div>

    <div style="text-align:right; line-height:1.3;">
      <div style="font-family:'Share Tech Mono',monospace; font-size:12px; color:#10B981;">
        ● SYSTEM STATUS: <span style="color:#FF4500;">NOMINAL</span>
      </div>
      <div style="font-family:'Share Tech Mono',monospace; font-size:10px; color:#64748B;">
        GROK-4.2 • CLAUDE SONNET 4 • GEMINI 2.5 FLASH
      </div>
      <div style="font-family:'Share Tech Mono',monospace; font-size:10px; color:#64748B;">
        POSTGRES • REDIS • CELERY • RENDER
      </div>
    </div>
  </div>

  <!-- SUB NAV BAR -->
  <div style="background:rgba(255,69,0,0.08); border-top:1px solid #2A3A52; padding:8px 28px; display:flex; gap:20px; font-size:11px; font-family:'Share Tech Mono',monospace;">
    <span style="color:#FF4500;">⚙ FORGE</span>
    <span style="color:#64748B;">🗄 VAULT</span>
    <span style="color:#64748B;">🔬 SCANNER</span>
    <span style="color:#10B981;">🔧 MECHANIC</span>
    <span style="color:#3B82F6;">🛡 QUOTE CHECK</span>
    <span style="color:#64748B;">🧠 DNA</span>
    <span style="color:#64748B;">👤 PROFILE</span>
    <span style="color:#64748B;">💬 ARENA</span>
  </div>
</div>
"""
