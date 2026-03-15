# STRIPE SETUP GUIDE — THE BUILDER FOUNDRY
## Complete step-by-step to start collecting payments tonight

---

## STEP 1: CREATE YOUR STRIPE ACCOUNT

If you don't have one yet:
1. Go to https://dashboard.stripe.com/register
2. Fill out business info (sole proprietor is fine)
3. You can start in TEST MODE while you wait for verification

---

## STEP 2: CREATE YOUR 3 PRODUCTS

Go to: dashboard.stripe.com → Products → "+ Add product"

### Product 1: Builder Starter
- **Name:** Builder Foundry — Starter License
- **Description:** 25 AI-powered blueprint builds per month. Access to Forge, Vault, Equipment Scanner, and Arena Chat.
- **Pricing:**
  - Price: $25.00
  - Billing period: Monthly (Recurring)
- Click "Save product"
- **Copy the Price ID** (starts with `price_`) — this is your `STRIPE_PRICE_STARTER`

### Product 2: Builder Pro
- **Name:** Builder Foundry — Pro License
- **Description:** 100 AI-powered blueprint builds per month. Full access to all Foundry tools with priority processing.
- **Pricing:**
  - Price: $100.00
  - Billing period: Monthly (Recurring)
- Click "Save product"
- **Copy the Price ID** — this is your `STRIPE_PRICE_PRO`

### Product 3: Builder Master
- **Name:** Builder Foundry — Master License
- **Description:** Unlimited blueprint builds for 1 year. Full Foundry access. Master clearance. Direct access to Conception's evolving intelligence.
- **Pricing:**
  - Price: $999.00
  - Billing period: Yearly (Recurring)
- Click "Save product"
- **Copy the Price ID** — this is your `STRIPE_PRICE_MASTER`

---

## STEP 3: CREATE A PAYMENT LINK

Go to: dashboard.stripe.com → Payment Links → "+ Create payment link"

**Option A: Single link with product selector (recommended)**
1. Add all 3 products
2. Enable "Let customers adjust quantity" = NO
3. Under "After payment" → Redirect to: `https://builder-app.onrender.com`
4. Click "Create link"
5. Copy the URL — this is your `STRIPE_PAYMENT_URL`

**Option B: Separate links per tier**
Create 3 separate payment links, one per product.
Use the Starter link as your main `STRIPE_PAYMENT_URL`.
You can link to the others from your landing page.

---

## STEP 4: SET UP THE WEBHOOK

This is how Stripe tells your app that someone paid.

1. Go to: dashboard.stripe.com → Developers → Webhooks
2. Click "+ Add endpoint"
3. **Endpoint URL:** `https://builder-billing.onrender.com/stripe/webhook`
4. Click "Select events" and choose:
   - `checkout.session.completed` (when someone pays)
   - `customer.subscription.deleted` (when someone cancels)
5. Click "Add endpoint"
6. On the webhook detail page, click "Reveal" under Signing Secret
7. **Copy the signing secret** (starts with `whsec_`) — this is your `STRIPE_WEBHOOK_SECRET`

---

## STEP 5: COPY YOUR API KEYS

Go to: dashboard.stripe.com → Developers → API keys

- **Secret key** (starts with `sk_test_` or `sk_live_`) — this is your `STRIPE_SECRET_KEY`
- You do NOT need the publishable key for this setup

---

## STEP 6: SET EVERYTHING IN RENDER

In your Render Dashboard, go to builder-billing → Environment:

| Variable              | Value                        |
|-----------------------|------------------------------|
| STRIPE_SECRET_KEY     | sk_test_...  (or sk_live_)   |
| STRIPE_WEBHOOK_SECRET | whsec_...                    |
| STRIPE_PRICE_STARTER  | price_...                    |
| STRIPE_PRICE_PRO      | price_...                    |
| STRIPE_PRICE_MASTER   | price_...                    |
| STRIPE_PAYMENT_URL    | https://buy.stripe.com/...   |

Also set STRIPE_PAYMENT_URL on builder-app.

---

## STEP 7: TEST THE FULL FLOW

### In TEST mode:
1. Go to your payment link
2. Use test card: `4242 4242 4242 4242`
   - Expiry: any future date (e.g., 12/34)
   - CVC: any 3 digits (e.g., 123)
   - ZIP: any 5 digits (e.g., 19104)
3. Complete the purchase
4. Check Render logs for builder-billing — you should see:
   ```
   INFO: Webhook received: checkout.session.completed
   INFO: License created for: your_email@example.com
   ```
5. Go to builder-app.onrender.com
6. Enter the license key that was created
7. Forge a blueprint
8. Download it

### Switch to LIVE mode:
1. In Stripe Dashboard, toggle from "Test mode" to live
2. Create a NEW webhook for live mode (same URL, same events)
3. Update these in Render:
   - `STRIPE_SECRET_KEY` → your live secret key (sk_live_...)
   - `STRIPE_WEBHOOK_SECRET` → your live webhook signing secret
   - `STRIPE_PAYMENT_URL` → your live payment link
4. Make a real $25 purchase to yourself
5. Confirm it works end-to-end
6. You're live. Start selling.

---

## TROUBLESHOOTING

**"License invalid, expired, or revoked"**
- Check builder-billing logs — did the webhook fire?
- Verify STRIPE_WEBHOOK_SECRET matches exactly
- Make sure INTERNAL_API_KEY is the same on billing AND auth

**Webhook not firing**
- Verify the webhook URL is exactly: https://builder-billing.onrender.com/stripe/webhook
- Check that builder-billing is running (green in Render dashboard)
- In Stripe → Webhooks, check "Recent deliveries" for errors

**"Auth service offline"**
- builder-auth might still be deploying (first deploy takes 3-5 min)
- Check Render logs for builder-auth for errors
- Verify DATABASE_URL is set (it should auto-populate from builder-db)

**Blueprint forge hangs**
- Check builder-ai-worker logs
- Verify at least one AI API key is set (ANTHROPIC_API_KEY or XAI_API_KEY)
- Check REDIS_URL is populated (auto from builder-redis)

---

## QUICK REFERENCE: ALL STRIPE VALUES YOU NEED

| What to copy from Stripe        | Where it goes in Render        |
|----------------------------------|-------------------------------|
| Secret key (sk_...)              | STRIPE_SECRET_KEY             |
| Webhook signing secret (whsec_) | STRIPE_WEBHOOK_SECRET         |
| Starter Price ID (price_...)     | STRIPE_PRICE_STARTER          |
| Pro Price ID (price_...)         | STRIPE_PRICE_PRO              |
| Master Price ID (price_...)      | STRIPE_PRICE_MASTER           |
| Payment Link URL                 | STRIPE_PAYMENT_URL            |
