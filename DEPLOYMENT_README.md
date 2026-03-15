# CONCEPTION — PHASE 1 DEPLOYMENT GUIDE
## The Builder Foundry | Revenue-First Launch

---

## WHAT'S IN THIS FOLDER

```
phase1/
├── render_phase1.yaml      ← Render Blueprint (10 items: DB + Redis + 8 services)
├── requirements.txt        ← Python dependencies for ALL services
├── .env.example            ← Template for every secret you need
├── .streamlit/
│   └── config.toml         ← Dark theme + Streamlit config
├── DEPLOYMENT_README.md    ← You are here
└── STRIPE_SETUP.md         ← Step-by-step Stripe configuration
```

## FILES YOU ALREADY HAVE (from your project repo)

These files must be in the ROOT of your GitHub repo alongside render_phase1.yaml:

```
auth_service.py             ← License verification + JWT
ai_service.py               ← Blueprint request handler
ai_worker.py                ← Celery worker (Grok + Claude + Gemini)
billing_service.py          ← Stripe webhook + license creation
workshop_service.py         ← Equipment scanner request handler
workshop_worker.py          ← Gemini Vision analysis worker
export_service.py           ← Vault + downloads + stats
app.py                      ← Streamlit UI (the product)
builder_styles.py           ← CSS/HTML for the app
requirements.txt            ← (copy from this folder to repo root)
.streamlit/config.toml      ← (copy from this folder to repo root)
```

---

## DEPLOYMENT STEPS

### STEP 1: Prepare Your GitHub Repo

1. Create a new GitHub repo (private recommended): `conception-builder`
2. Copy ALL your Python service files to the repo root
3. Copy `requirements.txt` from this folder to repo root
4. Copy `.streamlit/config.toml` to `.streamlit/config.toml` in repo root
5. Copy `render_phase1.yaml` to repo root, rename to `render.yaml`
6. Push to GitHub

Your repo should look like:
```
conception-builder/
├── render.yaml              ← renamed from render_phase1.yaml
├── requirements.txt
├── .streamlit/config.toml
├── auth_service.py
├── ai_service.py
├── ai_worker.py
├── billing_service.py
├── workshop_service.py
├── workshop_worker.py
├── export_service.py
├── app.py
├── builder_styles.py
└── (any other files these import)
```

### STEP 2: Generate Your Secrets

Open a terminal and run this THREE times:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

- 1st output → JWT_SECRET (NEVER change after users exist)
- 2nd output → INTERNAL_API_KEY (same on every service)
- 3rd output → MASTER_KEY (admin access only)

WRITE THESE DOWN. You'll need them in Step 4.

### STEP 3: Set Up Stripe (see STRIPE_SETUP.md for full details)

Quick version:
1. Go to dashboard.stripe.com
2. Create 3 Products with Prices:
   - Builder Starter: $25/month → copy the Price ID
   - Builder Pro: $100/month → copy the Price ID
   - Builder Master: $999/year → copy the Price ID
3. Create a Payment Link (or Checkout page)
4. Set up Webhook:
   - URL: `https://builder-billing.onrender.com/stripe/webhook`
   - Events: `checkout.session.completed`, `customer.subscription.deleted`
   - Copy the Webhook Signing Secret

### STEP 4: Deploy to Render

1. Go to dashboard.render.com
2. Click "New" → "Blueprint"
3. Connect your GitHub repo
4. Render reads your `render.yaml` and shows all 10 items
5. Click "Apply" — Render will create everything
6. Go to EACH service's "Environment" tab and set the secrets:

**Every service needs:**
- `INTERNAL_API_KEY` → your generated key

**builder-auth needs:**
- `JWT_SECRET` → your generated key
- `MASTER_KEY` → your generated key
- `GMAIL_ADDRESS` → (optional) your gmail
- `GMAIL_APP_PW` → (optional) Google App Password

**builder-ai needs:**
- `JWT_SECRET`
- `XAI_API_KEY` → from x.ai
- `ANTHROPIC_API_KEY` → from console.anthropic.com
- `GEMINI_API_KEY` → from aistudio.google.com

**builder-ai-worker needs:**
- `XAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GEMINI_API_KEY`
- `GROK_API_KEY` → same as XAI_API_KEY

**builder-workshop-worker needs:**
- `GEMINI_API_KEY`

**builder-billing needs:**
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_STARTER`
- `STRIPE_PRICE_PRO`
- `STRIPE_PRICE_MASTER`
- `STRIPE_PAYMENT_URL`

**builder-export needs:**
- `JWT_SECRET`

**builder-app needs:**
- `JWT_SECRET`
- `STRIPE_PAYMENT_URL`

### STEP 5: Test the Money Flow

1. In Stripe Dashboard, make sure you're in TEST MODE
2. Go to your Builder App URL: `https://builder-app.onrender.com`
3. Click "GET A LICENSE" — should open your Stripe checkout
4. Use test card: `4242 4242 4242 4242` (any future date, any CVC)
5. After payment, check Render logs for builder-billing → should show webhook received
6. Try logging in with the license key
7. Forge a blueprint → verify it completes
8. Download it as .md and .txt

### STEP 6: Go Live

1. Switch Stripe to LIVE MODE
2. Update `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` in Render to live values
3. Update `STRIPE_PAYMENT_URL` to your live payment link
4. Make a real $25 purchase to yourself to confirm
5. You are now making money. Post the link everywhere.

---

## MONTHLY COSTS

| Item                        | Cost     |
|-----------------------------|----------|
| builder-db (basic-1gb)      | $7/mo    |
| builder-redis (free)        | $0       |
| builder-auth (starter)      | $7/mo    |
| builder-ai (starter)        | $7/mo    |
| builder-ai-worker (starter) | $7/mo    |
| builder-workshop (starter)  | $7/mo    |
| builder-workshop-worker (starter) | $7/mo |
| builder-billing (starter)   | $7/mo    |
| builder-export (starter)    | $7/mo    |
| builder-app (starter)       | $7/mo    |
| **TOTAL**                   | **$63/mo** |

Break-even: 3 Starter licenses ($75) covers infrastructure.

---

## PHASE 2 UPGRADE PATH

When Phase 1 is generating $200+/month consistently, add these services:
- builder-conception (orchestrator)
- builder-guardrails
- builder-mcp
- builder-admin
- builder-analytics (free tier)
- builder-guardian (bundle)

Just add their blocks to your render.yaml from render_MASTER_v3.yaml.
No code changes needed — ai_worker already handles Conception gracefully.
