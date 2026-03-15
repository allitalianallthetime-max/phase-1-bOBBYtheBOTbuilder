"""
builder_styles.py
=================
Dark industrial cyberpunk theme for the AoC3P0 Builder Foundry.
Imported by app.py — if this file is missing, app.py falls back to minimal defaults.
"""

BUILDER_CSS = """
<style>
/* ── GOOGLE FONT ── */
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@400;600;700&display=swap');

/* ── ROOT VARIABLES ── */
:root {
  --forge-orange:  #FF4500;
  --forge-dark:    #0A0E17;
  --forge-panel:   #0F1623;
  --forge-card:    #1A2235;
  --forge-border:  #2A3A52;
  --forge-muted:   #64748B;
  --forge-text:    #CBD5E1;
  --forge-bright:  #F1F5F9;
  --forge-gold:    #FFD700;
  --forge-green:   #1D9E75;
  --forge-red:     #DC2626;
  --forge-blue:    #3B82F6;
  --glow-orange:   0 0 12px rgba(255, 69, 0, 0.4);
  --glow-blue:     0 0 12px rgba(59,130,246,0.3);
}

/* ── GLOBAL RESET ── */
html, body, [data-testid="stAppViewContainer"] {
  background-color: var(--forge-dark) !important;
  color: var(--forge-text) !important;
  font-family: 'Rajdhani', sans-serif !important;
}

/* ── HIDE STREAMLIT CHROME ── */
#MainMenu, footer, [data-testid="stDecoration"],
[data-testid="collapsedControl"] { display: none !important; }

header[data-testid="stHeader"] {
  background: var(--forge-dark) !important;
  border-bottom: 1px solid var(--forge-border) !important;
}

/* ── SIDEBAR ── */
[data-testid="stSidebar"] {
  background: var(--forge-panel) !important;
  border-right: 1px solid var(--forge-border) !important;
  padding-top: 0 !important;
}

[data-testid="stSidebar"]::before {
  content: "";
  display: block;
  height: 3px;
  background: linear-gradient(90deg, var(--forge-orange), transparent);
  width: 100%;
}

/* ── BUTTONS ── */
.stButton > button {
  background: transparent !important;
  color: var(--forge-orange) !important;
  border: 1px solid var(--forge-orange) !important;
  border-radius: 3px !important;
  font-family: 'Share Tech Mono', monospace !important;
  font-size: 13px !important;
  letter-spacing: 1.5px !important;
  text-transform: uppercase !important;
  transition: all 0.2s ease !important;
  padding: 8px 16px !important;
}

.stButton > button:hover {
  background: var(--forge-orange) !important;
  color: var(--forge-dark) !important;
  box-shadow: var(--glow-orange) !important;
}

/* Primary forge button */
.stButton > button[kind="primary"] {
  background: var(--forge-orange) !important;
  color: var(--forge-dark) !important;
  font-weight: 700 !important;
  font-size: 14px !important;
}

/* ── INPUTS ── */
.stTextInput input, .stTextArea textarea, .stSelectbox select {
  background: var(--forge-card) !important;
  border: 1px solid var(--forge-border) !important;
  border-radius: 3px !important;
  color: var(--forge-bright) !important;
  font-family: 'Share Tech Mono', monospace !important;
  font-size: 13px !important;
  padding: 10px !important;
  transition: border-color 0.2s !important;
}

.stTextInput input:focus, .stTextArea textarea:focus {
  border-color: var(--forge-orange) !important;
  box-shadow: var(--glow-orange) !important;
}

/* ── EXPANDERS ── */
[data-testid="stExpander"] {
  background: var(--forge-card) !important;
  border: 1px solid var(--forge-border) !important;
  border-radius: 4px !important;
  margin-bottom: 8px !important;
}

[data-testid="stExpander"]:hover {
  border-color: var(--forge-orange) !important;
}

/* ── METRICS ── */
[data-testid="stMetric"] {
  background: var(--forge-card) !important;
  border: 1px solid var(--forge-border) !important;
  border-radius: 6px !important;
  padding: 16px !important;
  text-align: center !important;
}

[data-testid="stMetricValue"] {
  color: var(--forge-orange) !important;
  font-family: 'Share Tech Mono', monospace !important;
  font-size: 28px !important;
  font-weight: 700 !important;
}

[data-testid="stMetricLabel"] {
  color: var(--forge-muted) !important;
  font-size: 11px !important;
  letter-spacing: 1px !important;
  text-transform: uppercase !important;
}

/* ── STATUS BADGE ── */
[data-testid="stStatus"] {
  background: var(--forge-card) !important;
  border: 1px solid var(--forge-green) !important;
  border-radius: 4px !important;
}

/* ── PROGRESS BAR ── */
.stProgress > div > div {
  background: var(--forge-orange) !important;
  border-radius: 2px !important;
}

/* ── ALERTS ── */
.stAlert {
  border-radius: 4px !important;
  border-left-width: 3px !important;
  font-family: 'Share Tech Mono', monospace !important;
  font-size: 13px !important;
}

/* ── DIVIDERS ── */
hr {
  border-color: var(--forge-border) !important;
  margin: 20px 0 !important;
}

/* ── HEADINGS ── */
h1, h2, h3, h4 {
  font-family: 'Rajdhani', sans-serif !important;
  color: var(--forge-bright) !important;
  letter-spacing: 1px !important;
}

h3 { color: var(--forge-orange) !important; }

/* ── MARKDOWN TEXT ── */
.stMarkdown p, .stMarkdown li {
  color: var(--forge-text) !important;
  line-height: 1.7 !important;
}

code, pre {
  background: var(--forge-panel) !important;
  border: 1px solid var(--forge-border) !important;
  color: var(--forge-orange) !important;
  font-family: 'Share Tech Mono', monospace !important;
  border-radius: 3px !important;
}

/* ── DOWNLOAD BUTTONS ── */
.stDownloadButton > button {
  background: var(--forge-card) !important;
  border: 1px solid var(--forge-green) !important;
  color: var(--forge-green) !important;
}

.stDownloadButton > button:hover {
  background: var(--forge-green) !important;
  color: var(--forge-dark) !important;
}

/* ── LINK BUTTONS ── */
.stLinkButton a {
  background: var(--forge-card) !important;
  border: 1px solid var(--forge-border) !important;
  color: var(--forge-text) !important;
  border-radius: 3px !important;
  font-family: 'Share Tech Mono', monospace !important;
  font-size: 12px !important;
  letter-spacing: 1px !important;
}

/* ── SPINNER ── */
.stSpinner > div {
  border-top-color: var(--forge-orange) !important;
}

/* ── SCROLLBAR ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--forge-panel); }
::-webkit-scrollbar-thumb {
  background: var(--forge-border);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover { background: var(--forge-orange); }

/* ── AGENT CARDS ── */
.agent-card {
  background: var(--forge-card);
  border: 1px solid var(--forge-border);
  border-radius: 6px;
  padding: 16px;
  text-align: center;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.agent-card:hover {
  border-color: var(--forge-orange);
  box-shadow: var(--glow-orange);
}

/* ── VAULT ITEM ── */
.vault-item {
  background: var(--forge-card);
  border: 1px solid var(--forge-border);
  border-left: 3px solid var(--forge-orange);
  border-radius: 4px;
  padding: 12px 16px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.15s;
}

.vault-item:hover {
  border-left-color: var(--forge-gold);
  box-shadow: var(--glow-orange);
}

/* ── SCAN RESULTS ── */
.scan-result {
  background: var(--forge-panel);
  border: 1px solid var(--forge-green);
  border-radius: 6px;
  padding: 16px;
  font-family: 'Share Tech Mono', monospace;
  font-size: 13px;
}

/* ── CONCEPTION DNA PANEL ── */
.conception-panel {
  background: linear-gradient(135deg, var(--forge-card) 0%, #0D1B2A 100%);
  border: 1px solid var(--forge-blue);
  border-radius: 8px;
  padding: 20px;
  box-shadow: var(--glow-blue);
}

/* ── TICKER TAPE ── */
@keyframes ticker {
  0%   { transform: translateX(100%); }
  100% { transform: translateX(-100%); }
}

.ticker-tape {
  background: var(--forge-orange);
  color: var(--forge-dark);
  font-family: 'Share Tech Mono', monospace;
  font-size: 11px;
  letter-spacing: 2px;
  overflow: hidden;
  white-space: nowrap;
  padding: 4px 0;
}

.ticker-tape span {
  display: inline-block;
  animation: ticker 25s linear infinite;
}

/* ── NEON PULSE ── */
@keyframes pulse-orange {
  0%, 100% { box-shadow: 0 0 4px rgba(255,69,0,0.3); }
  50%       { box-shadow: 0 0 16px rgba(255,69,0,0.8); }
}

.pulse { animation: pulse-orange 2s ease-in-out infinite; }

/* ── BLUEPRINT TEXT ── */
.blueprint-output {
  background: var(--forge-panel);
  border: 1px solid var(--forge-border);
  border-left: 4px solid var(--forge-orange);
  border-radius: 4px;
  padding: 20px;
  font-family: 'Share Tech Mono', monospace;
  font-size: 13px;
  line-height: 1.8;
  color: var(--forge-text);
  max-height: 600px;
  overflow-y: auto;
}
</style>
"""

FORGE_HEADER_HTML = """
<div style="
  background: linear-gradient(90deg, #0A0E17 0%, #0F1623 50%, #0A0E17 100%);
  border-bottom: 2px solid #FF4500;
  padding: 0;
  margin-bottom: 0;
">
  <!-- Ticker tape -->
  <div class="ticker-tape">
    <span>
      ⚙️ BUILDER FOUNDRY ONLINE &nbsp;◆&nbsp;
      ROUND TABLE ENGAGED &nbsp;◆&nbsp;
      GROK-3 // CLAUDE SONNET // GEMINI 2.0 &nbsp;◆&nbsp;
      CONCEPTION DNA LEARNING &nbsp;◆&nbsp;
      TIMELESS TREASURES INTEGRATION ACTIVE &nbsp;◆&nbsp;
      ALL SYSTEMS OPERATIONAL &nbsp;◆&nbsp;
      ⚙️ BUILDER FOUNDRY ONLINE &nbsp;◆&nbsp;
    </span>
  </div>

  <!-- Main header -->
  <div style="display:flex; align-items:center; justify-content:space-between; padding: 16px 24px;">
    <div>
      <div style="font-family:'Share Tech Mono',monospace; font-size:11px;
                  color:#FF4500; letter-spacing:4px; margin-bottom:4px;">
        AoC3P0 SYSTEMS
      </div>
      <div style="font-family:'Rajdhani',sans-serif; font-size:32px;
                  font-weight:700; color:#F1F5F9; letter-spacing:3px;">
        THE BUILDER FOUNDRY
      </div>
      <div style="font-family:'Share Tech Mono',monospace; font-size:11px;
                  color:#64748B; letter-spacing:2px;">
        MULTI-AGENT ENGINEERING INTELLIGENCE // CONCEPTION DNA ARCHITECTURE
      </div>
    </div>
    <div style="text-align:right;">
      <div style="font-family:'Share Tech Mono',monospace; font-size:11px; color:#1D9E75;">
        ● SYSTEM STATUS: NOMINAL
      </div>
      <div style="font-family:'Share Tech Mono',monospace; font-size:10px; color:#64748B; margin-top:4px;">
        GROK-3 &nbsp;|&nbsp; CLAUDE SONNET 4.6 &nbsp;|&nbsp; GEMINI 2.0 FLASH
      </div>
      <div style="font-family:'Share Tech Mono',monospace; font-size:10px; color:#64748B; margin-top:2px;">
        POSTGRESQL &nbsp;|&nbsp; REDIS &nbsp;|&nbsp; CELERY &nbsp;|&nbsp; RENDER.COM
      </div>
    </div>
  </div>

  <!-- Sub-bar -->
  <div style="
    background: rgba(255,69,0,0.08);
    border-top: 1px solid #2A3A52;
    padding: 6px 24px;
    display: flex;
    gap: 32px;
  ">
    <span style="font-family:'Share Tech Mono',monospace; font-size:10px; color:#FF4500;">
      ⚙ FORGE BLUEPRINT
    </span>
    <span style="font-family:'Share Tech Mono',monospace; font-size:10px; color:#64748B;">
      🗄 CONCEPTION VAULT
    </span>
    <span style="font-family:'Share Tech Mono',monospace; font-size:10px; color:#64748B;">
      🔬 EQUIPMENT SCANNER
    </span>
    <span style="font-family:'Share Tech Mono',monospace; font-size:10px; color:#64748B;">
      🧠 CONCEPTION DNA
    </span>
    <span style="font-family:'Share Tech Mono',monospace; font-size:10px; color:#64748B;">
      🏟 ARENA [COMING SOON]
    </span>
  </div>
</div>
"""
