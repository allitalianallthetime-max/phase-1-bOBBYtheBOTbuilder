# PHASE 1 LAUNCH CHECKLIST
# Print this out. Check off each item. Tonight we ship.

## SECRETS (5 min)
[ ] Generated JWT_SECRET (python -c "import secrets; print(secrets.token_hex(32))")
[ ] Generated INTERNAL_API_KEY
[ ] Generated MASTER_KEY
[ ] Wrote all 3 down somewhere safe

## AI API KEYS (10 min)
[ ] ANTHROPIC_API_KEY from console.anthropic.com
[ ] GEMINI_API_KEY from aistudio.google.com
[ ] XAI_API_KEY from x.ai (this is also GROK_API_KEY)

## STRIPE (30 min)
[ ] Created Stripe account (or logged in)
[ ] Created Product: Builder Starter ($25/mo) → copied Price ID
[ ] Created Product: Builder Pro ($100/mo) → copied Price ID
[ ] Created Product: Builder Master ($999/year) → copied Price ID
[ ] Created Payment Link → copied URL
[ ] Created Webhook endpoint: https://builder-billing.onrender.com/stripe/webhook
[ ] Selected events: checkout.session.completed, customer.subscription.deleted
[ ] Copied Webhook Signing Secret (whsec_...)
[ ] Copied Secret Key (sk_test_... for now)

## GITHUB (10 min)
[ ] Created repo: conception-builder (private)
[ ] Copied all Phase 1 .py files to repo root
[ ] Copied requirements.txt to repo root
[ ] Copied .streamlit/config.toml to repo
[ ] Copied render_phase1.yaml → renamed to render.yaml
[ ] Copied .gitignore to repo root
[ ] Pushed to GitHub

## RENDER DEPLOY (20 min)
[ ] Connected GitHub repo to Render
[ ] Created Blueprint from render.yaml
[ ] All 10 items showing (1 DB + 1 Redis + 8 services)
[ ] Clicked "Apply" — deployment started
[ ] Set INTERNAL_API_KEY on ALL 8 services
[ ] Set JWT_SECRET on: auth, ai, export, app
[ ] Set MASTER_KEY on: auth
[ ] Set AI keys on: ai, ai-worker, workshop-worker
[ ] Set Stripe keys on: billing
[ ] Set STRIPE_PAYMENT_URL on: billing, app
[ ] All services showing green health checks

## TEST (15 min)
[ ] Opened builder-app.onrender.com — login screen loads
[ ] Clicked "GET A LICENSE" — Stripe checkout opens
[ ] Purchased with test card (4242 4242 4242 4242)
[ ] Checked billing logs — webhook received
[ ] Logged in with license key — SUCCESS
[ ] Forged a blueprint — completed
[ ] Downloaded as .md — file looks good
[ ] Downloaded as .txt — file looks good

## GO LIVE (10 min)
[ ] Switched Stripe to LIVE mode
[ ] Updated STRIPE_SECRET_KEY to live key in Render
[ ] Created NEW live webhook, updated STRIPE_WEBHOOK_SECRET
[ ] Updated STRIPE_PAYMENT_URL to live payment link
[ ] Made real $25 purchase to myself — WORKS
[ ] First real dollar earned. Let's go.

## MARKETING (ongoing)
[ ] Posted demo video on TikTok/YouTube Shorts/Reels
[ ] Posted story on Reddit (r/robotics, r/maker, r/engineering)
[ ] Posted on Hacker News (Show HN)
[ ] Created Product Hunt listing
[ ] Shared payment link on all social profiles
