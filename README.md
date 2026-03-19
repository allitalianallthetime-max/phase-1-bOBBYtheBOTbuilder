# ⚙️ THE BUILDER FOUNDRY

**Three AI agents. Real web research. Real results.**

**Build from scrap. Diagnose any engine. Verify any repair quote.**

[![Live App](https://img.shields.io/badge/LIVE-bobtherobotbuilder.com-FF4500?style=for-the-badge)](https://www.bobtherobotbuilder.com)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io)

---

## What Is This?

The Builder Foundry is a multi-agent AI platform that turns junk into blueprints, symptoms into repair procedures, and repair quotes into fair pricing — using **only the parts you already own**.

**Three modes. One platform.**

**1. Blueprint Forge** — Tell it your scrap and your goal. Three AI agents analyze every component, search real maker projects, and deliver a complete engineering blueprint + SVG schematic built from *your actual inventory*.

**2. Field Mechanic** — Stranded on a boat? Remote job site? Enter your engine, symptoms, mileage, and tools on hand. AI diagnoses the problem, pulls real forum fixes and TSBs, and writes a step-by-step procedure with torque specs, jury-rig options, and real part prices.

**3. Quote Checker** — Got a $2,400 repair quote? Paste it in. AI checks it against live data, finds recalls and warranties, and tells you if you're getting robbed — in 60 seconds for $3.33.

> AllData charges $199/month for static data.
> We charge $3.33 per diagnosis with live web research and three frontier models.

---

## How It Works

```
THREE MODES — ONE PLATFORM

 BLUEPRINT FORGE            FIELD MECHANIC            QUOTE CHECKER
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│ Your junk         │       │ Vehicle + Engine  │       │ What they said    │
│ + what you want   │ FORGE │ + Symptom         │ DIAG  │ + what they quoted│ CHECK
│   to build        │ ────► │ + Already tried   │ ────► │ + your mileage    │ ────►
│                   │       │ + Tools on hand   │       │                   │
└──────────────────┘       └──────────────────┘       └──────────────────┘
         │                          │                          │
         ▼                          ▼                          ▼

  12-section blueprint       10-section field repair     Fair price analysis
  + SVG schematic            with torque specs,          + recall/warranty check
  + real parts pricing       jury-rig + forum fixes      + "what to say" script
  + YouTube build videos     + TSBs + YouTube videos     + NHTSA complaints
```

### The AI Round Table — Four Agents Working in Parallel

| Agent | Role | What It Does |
|---|---|---|
| 🟠 **GROK 4.2** | The Brain | Structured JSON analysis, mileage-aware diagnostics, creative component harvesting |
| 🔍 **GEMINI 2.5** | The Searcher | Real-time web research (forums, TSBs, RockAuto pricing, YouTube, recalls) — runs **in parallel** |
| 🔵 **CLAUDE SONNET 4** | The Writer | Synthesizes everything into complete, readable documents |
| 🔬 **GEMINI 2.5** | The Reviewer | Safety review, difficulty rating, build time estimate, Conception readiness score |

---

## Features

### Builders
- Inventory-first blueprints (every part traces to your junk)
- Auto-generated SVG technical schematics
- Equipment Scanner (photo → component list)
- Saved garage inventory
- Real maker project research

### Mechanics
- Field-ready repair procedures with torque specs
- "Already Tried" awareness (never repeats ruled-out steps)
- Forum fixes, TSBs, NHTSA recalls, and YouTube links
- Saved vehicles for one-tap re-diagnosis
- Emergency jury-rig options with risk warnings

### Vehicle Owners
- Instant quote verification (Fair / High / Red Flag)
- Automatic recall & extended warranty detection
- "What to say to the shop" script
- Community pricing intelligence

### Platform
- Token system (pay per use, tokens never expire)
- Conception DNA learning loop
- Free professional invoice generator
- User profiles with saved vehicles & inventory

---

## Pricing — Simple & Transparent

**Pay per build. No subscription required.**

| Pack | Tokens | Price | Per Token |
|---|---|---|---|
| Spark | 3 | $9.99 | $3.33 |
| Builder ★ | 10 | $24.99 | $2.50 |
| Foundry | 30 | $59.99 | $2.00 |
| Shop Pass | 100 | $149.99 | $1.50 |

**Subscriptions (monthly refill + unlimited rollover)**
- **Pro** — 20 tokens/mo — $29.99
- **Master** — 60 tokens/mo — $74.99

**Free trial** — 1 build, no card required.

---

## The Story

Built by a self-taught developer who pieces computers together from salvaged parts and refuses to throw anything away.

As a mechanic, I watched people get overcharged for repairs they didn't understand. As a builder, I watched perfectly good parts go to landfills. The Builder Foundry fixes both problems.

This is **Phase 1 of Conception** — an advanced learning AI that gets smarter with every blueprint, diagnosis, and quote checked. Every time you use it, Conception learns.

> 53 million tons of e-waste are generated every year. Only 17% gets recycled.
> Every blueprint turns trash into something useful.

**Stop throwing things away. Start building.**

---

## Tech Stack & Architecture

**11 microservices • Zero new infrastructure needed**

- **Frontend**: Streamlit (modular pages)
- **Backend**: FastAPI + Celery + Redis
- **Database**: PostgreSQL
- **AI Models**: Grok 4.2 • Claude Sonnet 4 • Gemini 2.5 Flash
- **Payments**: Stripe
- **Hosting**: Render.com

---

## Roadmap

| Phase | Status | Focus |
|---|---|---|
| Phase 1 | ✅ Live | Core product + 4-agent orchestration |
| Phase 2 | ✅ Built | Conception orchestrator & admin tools |
| Phase 3 | 🔧 In Progress | Learning cache, cost reduction tiers, community stats |
| Phase 4 | Planned | Full invoice system + mechanic badges |
| Phase 5 | Planned | Voice interface + physical robot integration |

---

## Built With Passion

**Builders. Mechanics. Vehicle owners. We're all on the same team.**

Made by Anthony Coco • AoC3P0 Systems
[Website](https://www.bobtherobotbuilder.com) • [GitHub](https://github.com/allitalianallthetime-max)

---

*53 million tons of e-waste. Only 17% recycled.
Every build fights that number.*
