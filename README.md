# ⚙️ THE BUILDER FOUNDRY

### Three AI agents. Real web research. Real results.

**Build from scrap. Diagnose any engine. Verify any repair quote.**

[![Live App](https://img.shields.io/badge/LIVE-bobtherobotbuilder.com-FF4500?style=for-the-badge)](https://www.bobtherobotbuilder.com)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io)

---

## What Is This?

The Builder Foundry is a multi-agent AI platform that does three things no other tool does:

**1. Blueprint Forge** — Tell it what junk you have and what you want to build. Three AI agents analyze every component, search real maker projects on the web, and generate a complete engineering blueprint using *only your parts*. Not a shopping list. Junkyard engineering.

**2. Field Mechanic** — Enter your vehicle, engine, symptoms, mileage, and tools on hand. AI diagnoses the problem, searches real forums for verified fixes, finds TSBs and recalls, and writes a step-by-step repair procedure with real torque specs, real part prices, and an emergency jury-rig to get you home.

**3. Quote Checker** — Got a repair quote? Paste it in. AI checks it against real repair data, searches for recalls and extended warranties, and tells you if the price is fair — or if you're getting ripped off. $3.33 to potentially save $1,000+.

> AllData charges $199/month for static data. We charge $3.33 per diagnosis with live web research, AI diagnosis, and real parts pricing.

---

## How It Works

```
THREE MODES — ONE PLATFORM:

⚙️ BLUEPRINT FORGE                🔧 FIELD MECHANIC                🛡️ QUOTE CHECKER
┌──────────────────┐              ┌──────────────────┐              ┌──────────────────┐
│ Your junk         │              │ Vehicle + Engine  │              │ What they said    │
│ + what you want   │    FORGE     │ + Symptom         │   DIAGNOSE   │ + what they quoted│  CHECK
│   to build        │ ──────────►  │ + Already tried   │ ──────────►  │ + your mileage    │ ──────►
│                   │              │ + Tools on hand   │              │                   │
└──────────────────┘              └──────────────────┘              └──────────────────┘

         │                                 │                                │
         ▼                                 ▼                                ▼

  12-section blueprint            10-section repair               Fair price analysis
  + SVG schematic                 procedure with torque           + recall/warranty check
  + real parts pricing            specs, jury-rig option,         + "what to say" script
  + maker project links           forum fixes, TSBs,              + NHTSA complaint data
  + YouTube build videos          YouTube repair videos           + community stats
```

### The AI Round Table — 4 Agents Working in Parallel

| Agent | Role | What It Does |
|-------|------|-------------|
| 🟠 **GROK 4.2** | The Brain | Deep failure tree analysis. Full engine spec sheets. Structured JSON with mileage-aware diagnostics. Junkyard component identification with creative engineering suggestions. |
| 🔍 **GEMINI 2.5 Flash** | The Searcher | Searches the ACTUAL web — mechanic forums, TSBs, NHTSA recalls, parts pricing from RockAuto/Amazon, YouTube repair videos, Instructables projects, Harbor Freight pricing. Runs IN PARALLEL with Grok. |
| 🔵 **CLAUDE SONNET 4** | The Writer | Synthesizes Grok's analysis AND Gemini's web research into a complete document — blueprints with schematics, repair procedures with torque specs, or quote analyses with fair pricing breakdowns. |
| 🔬 **GEMINI 2.5 Flash** | The Reviewer | Reviews the output for safety issues, rates difficulty, estimates build time, and scores inventory usage. |

**Grok and Gemini run in parallel.** Same wait time as a single API call, double the intelligence.

---

## Features

### For Builders
- **Inventory-First Blueprints** — Every material traces back to your actual junk
- **Technical SVG Schematics** — Auto-generated engineering drawings with every build
- **Equipment Scanner** — Upload a photo, Gemini Vision identifies every component
- **Real Maker Research** — Gemini searches Instructables, YouTube, Harbor Freight for similar projects and gap-filler parts
- **Saved Garage** — Save your inventory, select items for each build

### For Mechanics
- **10-Section Repair Procedures** — Diagnosis, safety, field repair, torque specs, jury-rig, "do not do this," parts with real prices
- **"Already Tried" Awareness** — AI skips what you've already ruled out
- **Forum Fixes & TSBs** — Real verified fixes from CumminsForum, iBoats, TheDieselStop
- **NHTSA Complaints & Recalls** — Automatic recall and extended warranty detection
- **Saved Vehicles** — Save your fleet, one-tap re-diagnosis
- **Free Invoice Generator** — Professional repair estimates from any diagnosis (coming soon)

### For Vehicle Owners
- **Quote Verification** — Fair/High/Very High/Red Flag rating with cost breakdown
- **Warranty & Recall Check** — Finds coverage you didn't know existed
- **"What To Say" Script** — Exact words to use when calling the shop back
- **Community Intelligence** — How many others had this problem, what they paid

### Platform
- **Token System** — Pay per build, not per month. Tokens never expire.
- **User Profiles** — Business info, saved vehicles, saved inventory
- **Conception DNA** — Every build trains the AI. The more people use it, the smarter it gets.
- **Conception Learning Cache** — Repeat problems get faster, cheaper, more accurate answers over time

---

## Architecture

```
11 SERVICES — ZERO NEW INFRASTRUCTURE NEEDED

┌─────────────────────────────────────────────────────────────────────┐
│                    BUILDER APP (Streamlit)                           │
│              bobtherobotbuilder.com                                  │
│  ┌──────────┬───────────┬──────────┬──────────┬──────────────────┐  │
│  │ Forge    │ Mechanic  │ Quote    │ Scanner  │ Profile/Vault/   │  │
│  │ Tab      │ Tab       │ Check    │ Tab      │ DNA/Chat         │  │
│  └────┬─────┴─────┬─────┴────┬─────┴────┬─────┴──────────────────┘  │
└───────┼───────────┼──────────┼──────────┼───────────────────────────┘
        │           │          │          │
  ┌─────▼─────┐  ┌──▼───┐  ┌──▼───┐  ┌──▼──────────┐
  │ Auth       │  │ AI   │  │Bill- │  │ Workshop    │
  │ Service    │  │ Svc  │  │ing   │  │ Service     │
  │ (JWT/Keys  │  │      │  │(Stripe│  │ (Scanner)  │
  │  Profiles) │  │      │  │ Tokens│  │             │
  └─────┬──────┘  └──┬───┘  └──┬───┘  └──┬──────────┘
        │            │         │          │
        │       ┌────▼─────────┐          │
        │       │  AI Worker   │          │
        │       │  (Celery)    │          │
        │       │              │          │
        │       │ ┌──────────┐ │          │
        │       │ │agent_grok│ │          │
        │       │ │agent_clau│ │          │
        │       │ │agent_gemi│ │          │
        │       │ │prompts   │ │          │
        │       │ └──────────┘ │          │
        │       └──────┬───────┘          │
        │              │                  │
  ┌─────▼──────────────▼──────────────────▼───────┐
  │  PostgreSQL + Redis + Conception Service       │
  └────────────────────────────────────────────────┘
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Streamlit (12 modular files) |
| API Services | FastAPI + Uvicorn |
| Task Queue | Celery + Redis |
| Database | PostgreSQL 16 |
| AI Models | Grok 4.2 (xAI), Claude Sonnet 4 (Anthropic), Gemini 2.5 Flash (Google) |
| Payments | Stripe Checkout + Webhooks (token packs + subscriptions) |
| Hosting | Render.com (11 microservices) |
| Auth | JWT + License Keys + User Profiles |

### Codebase Structure

```
FRONTEND (builder-app):             BACKEND (builder-ai-worker):
├── app.py           (183 lines)    ├── ai_worker.py      (238 lines)
├── app_config.py    (170 lines)    ├── worker_config.py   (212 lines)
├── app_helpers.py   (146 lines)    ├── agent_grok.py      (296 lines)
├── landing_page.py  (598 lines)    ├── agent_claude.py    (221 lines)
├── tab_forge.py     (113 lines)    ├── agent_gemini.py    (256 lines)
├── tab_mechanic.py  (204 lines)    ├── prompts.py         (195 lines)
├── tab_quote_check.py (134 lines)  ├── conception_memory.py (37 lines)
├── tab_vault.py     (81 lines)     │
├── tab_scanner.py   (92 lines)     OTHER SERVICES:
├── tab_conception.py (72 lines)    ├── ai_service.py      (421 lines)
├── tab_profile.py   (160 lines)    ├── auth_service.py    (562 lines)
├── tab_chat.py      (33 lines)     ├── billing_service.py (408 lines)
└── builder_styles.py               └── export_service.py
```

No file over 600 lines. Every tab is its own module. Every agent is its own file. Model names are env vars.

---

## Pricing — Token System

**Pay per build. No subscription required. Tokens never expire.**

| Action | Standard | Industrial | Experimental |
|--------|----------|------------|-------------|
| Blueprint Forge | 1⚡ | 3⚡ | 5⚡ |
| Field Mechanic | 1⚡ | 3⚡ | 5⚡ |
| Quote Check | 1⚡ | — | — |
| Equipment Scan | 1⚡ | — | — |

### Token Packs (one-time, never expire)

| Pack | Tokens | Price | Per Token |
|------|--------|-------|-----------|
| Spark | 3 | $9.99 | $3.33 |
| Builder | 10 | $24.99 | $2.50 |
| Foundry | 30 | $59.99 | $2.00 |
| Shop Pass | 100 | $149.99 | $1.50 |

### Subscriptions (monthly auto-refill, unlimited rollover)

| Tier | Tokens/mo | Price | Per Token |
|------|-----------|-------|-----------|
| Pro | 20 | $29.99/mo | $1.50 |
| Master | 60 | $74.99/mo | $1.25 |

**Free trial: 1 token, no credit card required.**

---

## The Story

This platform was built by a self-taught developer who pieces together computers from salvaged parts and builds things from scrap. No CS degree. No VC funding. Just a garage, a vision, and a refusal to stop learning.

As a mechanic, I watched people get overcharged every day for repairs they didn't understand. As a builder, I watched perfectly good parts get thrown in landfills. This tool fixes both problems.

The Builder Foundry is Phase 1 of **Conception** — an advanced learning AI being built to serve as a family guardian, financial advisor, store manager, and eventually a physical robot. Every blueprint forged, every diagnosis run, and every quote checked trains Conception's brain. The more people use it, the smarter it gets. Over time, repeat problems get faster, cheaper, and more accurate as Conception learns from real repair outcomes.

> **53 million tons of e-waste are generated every year. Only 17% gets recycled.** Every blueprint from The Builder Foundry turns trash into something useful. Stop throwing things away. Start building.

---

## Roadmap

| Phase | Status | What |
|-------|--------|------|
| **Phase 1: The Builder** | ✅ LIVE | Blueprint forge, mechanic mode, quote checker, token system, 4-AI orchestration, Gemini web search, user profiles |
| **Phase 2: The Brain** | ✅ Built | Conception orchestrator, guardrails, MCP server, admin dashboard, marketing engine |
| **Phase 3: Conception Cache** | 🔧 Next | Learning from repair outcomes, cost reduction tiers, schematic caching, community intelligence stats |
| **Phase 4: Invoice System** | 🔧 Planned | Free estimate generator, repair cost database, "Verified Fair Pricing" mechanic badges |
| **Phase 5: The Body** | 🔧 Planned | Voice pipeline, autonomy engine, brain trace, Raspberry Pi body interface |

---

## Running Locally

```bash
git clone https://github.com/allitalianallthetime-max/phase-1-bOBBYtheBOTbuilder.git
cd phase-1-bOBBYtheBOTbuilder

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your API keys

# Requires PostgreSQL and Redis running locally
uvicorn auth_service:app --port 8001 &
uvicorn ai_service:app --port 8002 &
uvicorn billing_service:app --port 8006 &
uvicorn export_service:app --port 8004 &
celery -A ai_worker worker --loglevel=info &
streamlit run app.py
```

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `JWT_SECRET` | Token signing |
| `INTERNAL_API_KEY` | Service-to-service auth |
| `ANTHROPIC_API_KEY` | Claude Sonnet 4 |
| `GEMINI_API_KEY` | Gemini 2.5 Flash |
| `GROK_API_KEY` | Grok 4.2 (xAI) |
| `GROK_MODEL` | Model string (default: `grok-4.20-beta-0309-reasoning`) |
| `GROK_TEMPERATURE` | Grok temperature (default: `0.3`) |
| `STRIPE_SECRET_KEY` | Payment processing |
| `STRIPE_WEBHOOK_SEC` | Webhook verification |
| `DATABASE_URL` | PostgreSQL connection |
| `REDIS_URL` | Task queue + caching |
| `CONCEPTION_SERVICE_URL` | Conception learning service |
| `GMAIL_ADDRESS` | Blueprint email delivery |
| `GMAIL_APP_PW` | Gmail app password |

---

## Contributing

This is a solo project with a big vision. If you're interested in contributing, open an issue first.

Areas where help would be most valuable:
- **Prompt engineering** — Making diagnoses and blueprints more accurate
- **Frontend design** — The Streamlit UI could always be sharper
- **Mechanic knowledge** — Real-world repair expertise to validate AI output
- **Parts pricing data** — Affiliate integrations with RockAuto, Amazon, Harbor Freight

---

## License

Proprietary. All rights reserved. This repository is public for portfolio and demonstration purposes. Commercial use, redistribution, or derivative works require written permission from the author.

---

## Contact

- **Website:** [bobtherobotbuilder.com](https://www.bobtherobotbuilder.com)
- **Email:** allitalianallthetime@gmail.com
- **GitHub:** [@allitalianallthetime-max](https://github.com/allitalianallthetime-max)
- **Built by:** Anthony Coco | AoC3P0 Systems

---

<p align="center">
  <strong>Builders. Mechanics. Vehicle owners. We're all on the same team.</strong><br>
  <em>$3.33 per diagnosis. AllData charges $199/month.</em>
</p>
