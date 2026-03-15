# ⚙️ THE BUILDER FOUNDRY

### *Turn junk into genius. AI-powered engineering blueprints from the parts you already have.*

[![Live App](https://img.shields.io/badge/LIVE-bobtherobotbuilder.com-FF4500?style=for-the-badge)](https://www.bobtherobotbuilder.com)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io)

---

## What Is This?

You have a broken treadmill, an old Dell computer, and a dream. You want to build a cat litter robot.

Every other AI tool would ignore your stuff and generate a generic shopping list. **The Builder Foundry does the opposite.** It looks at the specific items you already own, breaks them down into harvestable components (motors, frames, wiring, sensors, control boards), and generates a complete engineering blueprint that builds your project **from those actual parts.**

> *"The treadmill's 2.5HP DC motor becomes your drum drive. The incline actuator becomes your waste tilting mechanism. The Dell's i5 motherboard becomes your automation controller. The treadmill's steel frame becomes your structural chassis."*

That's not a suggestion to go shopping. That's junkyard engineering.

---

## How It Works

```
YOU ENTER:                          YOU GET:
┌─────────────────────┐             ┌──────────────────────────────┐
│ Project: Cat Litter  │             │ ✅ Engineering Blueprint     │
│ Robot                │    FORGE    │ ✅ Technical SVG Schematic   │
│                      │ ─────────► │ ✅ Materials Manifest        │
│ Inventory:           │             │    (every part traced to     │
│ - Old treadmill      │             │     your actual inventory)   │
│ - Dell OptiPlex PC   │             │ ✅ Assembly Sequence         │
│                      │             │ ✅ Safety Notes              │
└─────────────────────┘             │ ✅ Testing Procedures        │
                                    └──────────────────────────────┘
```

### The Round Table — 3 AI Agents Working Together

| Agent | Role | What It Does |
|-------|------|-------------|
| 🟠 **GROK-3** | Junkyard Analyst | Tears apart every inventory item and identifies every harvestable component — motors, frames, wiring, bearings, circuit boards, power supplies |
| 🔵 **CLAUDE SONNET** | Blueprint Engineer | Writes the full engineering blueprint using ONLY the parts Grok identified. Every material traces back to your inventory |
| 🟢 **GEMINI FLASH** | Quality Inspector | Reviews the blueprint for safety issues, rates difficulty, estimates build time, and scores how well it actually used your inventory |

---

## Features

- **Inventory-First Design** — Enter what you have. Get a blueprint built from those specific parts. No generic shopping lists.
- **Technical Schematics** — Auto-generated SVG engineering drawings with color-coded components, dimension lines, and part labels showing which inventory item each piece came from.
- **Multi-AI Orchestration** — Three AI agents (Grok-3, Claude Sonnet, Gemini Flash) collaborate on every blueprint, each handling what they do best.
- **Equipment Scanner** — Upload a photo of any hardware. Gemini Vision identifies every component for your inventory manifest.
- **Conception DNA Vault** — Every blueprint is archived. The more you build, the smarter the system gets.
- **License-Gated Access** — Stripe-powered subscriptions with automated license key delivery via email.
- **Arena Chat** — Live global chat for all operators across all tiers.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    BUILDER APP (Streamlit)               │
│              bobtherobotbuilder.com                       │
└──────────┬──────────────┬───────────────┬───────────────┘
           │              │               │
     ┌─────▼─────┐  ┌────▼────┐   ┌─────▼──────┐
     │ Auth       │  │ AI      │   │ Billing    │
     │ Service    │  │ Service │   │ Service    │
     │ (JWT/Keys) │  │ (Queue) │   │ (Stripe)   │
     └─────┬─────┘  └────┬────┘   └─────┬──────┘
           │              │               │
           │         ┌────▼────┐          │
           │         │ AI      │          │
           │         │ Worker  │          │
           │         │ (Celery)│          │
           │         └────┬────┘          │
           │              │               │
     ┌─────▼──────────────▼───────────────▼──────┐
     │              PostgreSQL + Redis             │
     └─────────────────────────────────────────────┘
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Streamlit (Python) |
| API Services | FastAPI + Uvicorn |
| Task Queue | Celery + Redis |
| Database | PostgreSQL 16 |
| AI Models | Grok-3 (xAI), Claude Sonnet (Anthropic), Gemini Flash (Google) |
| Payments | Stripe Checkout + Webhooks |
| Hosting | Render.com (microservices) |
| Auth | JWT + License Keys |

---

## Pricing

| Tier | Price | Builds | For |
|------|-------|--------|-----|
| **Starter** | $25/mo | 25/month | Hobbyists and curious makers |
| **Pro** | $100/mo | 100/month | Serious builders and workshops |
| **Master** | $999/year | Unlimited | Schools, makerspaces, and professionals |

---

## The Story

This platform was built by a self-taught developer who pieces together computers from parts and builds things from scrap. No CS degree. No funding. Just a Ryzen 9 Frankenstein workstation, a passion for engineering, and a refusal to stop learning.

The Builder Foundry is Phase 1 of **Conception** — an advanced learning AI being built to serve as a family guardian, financial advisor, marketing engine, and eventually a physical robot. Every blueprint forged on this platform trains Conception's brain. Every user interaction makes him smarter.

The vision: an AI that doesn't just answer questions — it builds things, protects your family, runs your business, and one day walks beside you.

---

## Roadmap

| Phase | Status | What |
|-------|--------|------|
| **Phase 1: The Builder** | ✅ LIVE | Core forge pipeline, Stripe payments, license system, 3-AI orchestration |
| **Phase 2: The Brain** | 🔧 Built | Conception orchestrator, guardrails, MCP server, admin dashboard |
| **Phase 3: Education** | 🔧 Built | Homeschool, public school, charter, and private school portals with age verification |
| **Phase 4: The Arena** | 🔧 Built | Competitions, marketplace, collaboration, community features |
| **Phase 5: The Body** | 🔧 Built | Voice pipeline, autonomy engine, brain trace, Raspberry Pi body interface |

---

## Running Locally

```bash
# Clone the repo
git clone https://github.com/allitalianallthetime-max/phase-1-bOBBYtheBOTbuilder.git
cd phase-1-bOBBYtheBOTbuilder

# Install dependencies
pip install -r requirements.txt

# Set environment variables (see .env.example)
cp .env.example .env
# Edit .env with your API keys

# Start services (requires PostgreSQL and Redis running locally)
uvicorn auth_service:app --port 8001 &
uvicorn ai_service:app --port 8002 &
uvicorn billing_service:app --port 8006 &
uvicorn export_service:app --port 8004 &
celery -A ai_worker worker --loglevel=info &
streamlit run app.py
```

---

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Purpose |
|----------|---------|
| `JWT_SECRET` | Token signing (never rotate after launch) |
| `INTERNAL_API_KEY` | Service-to-service authentication |
| `ANTHROPIC_API_KEY` | Claude Sonnet access |
| `GEMINI_API_KEY` | Gemini Flash access |
| `XAI_API_KEY` | Grok-3 access |
| `STRIPE_SECRET_KEY` | Payment processing |
| `DATABASE_URL` | PostgreSQL connection |
| `REDIS_URL` | Task queue and caching |

---

## Contributing

This is a solo project with a big vision. If you're interested in contributing, open an issue first to discuss what you'd like to work on.

Areas where help would be most valuable:
- **Prompt engineering** — Making blueprints even more creative and inventory-aware
- **Frontend design** — The Streamlit UI could always be sharper
- **Education content** — STEM curriculum modules for the education portal
- **Hardware integration** — Raspberry Pi body interface and sensor packages

---

## License

Proprietary. All rights reserved. This repository is public for portfolio and demonstration purposes. Commercial use, redistribution, or derivative works require written permission from the author.

---

## Contact

- **Website:** [bobtherobotbuilder.com](https://www.bobtherobotbuilder.com)
- **Email:** allitalianallthetime@gmail.com
- **Built by:** Anthony Coco | AoC3P0 Systems

---

<p align="center">
  <strong>You weren't born rich. You were born relentless.</strong><br>
  <em>Phase 1 ships tonight. Everything else follows.</em>
</p>
