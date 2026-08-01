# Presentation Notes — Bank Details, Ratings & New Services (2026-08-01)

## What we can show
1. **Cleaner partner settings** — the Quality Check toggle is gone from Operations (it never worked; it was silently dropped server-side).
2. **Carpet Cleaning & Curtain Cleaning** now appear as selectable Accepted Services in both the partner and internal facility forms — real catalogue categories, not hard-coded.
3. **Secure bank details** — a partner adds payout banking; the IBAN shows masked (`AE•• •••• •••• •••• 1234`); "Reveal full details" decrypts (owner/manager only) and is logged. Internal admins can view/edit the same, gated to admins.
4. **Ratings** — an internal user rates a facility and a driver on 1–5 factors; the overall score is computed by the backend live in the form; the partner sees a read-only Ratings page with the score, factor bars, trend, and a performance summary — but never the internal notes.

## Suggested demo flow
1. Partner Portal → Settings → Operations: show the toggle is gone. → My Facilities: add carpet/curtain to Accepted Services; add bank details; reveal + hide.
2. Internal Dashboard → a facility detail page: open **Bank Details** (reveal), then **Performance rating** → "Rate facility" (watch overall auto-update) → save; **Driver ratings** → rate a driver.
3. Back in Partner Portal → **Ratings**: the new facility + driver scores appear (summary only).

## Talking points (plain language)
- **Banking is treated as sensitive.** The IBAN and account number are encrypted in the database — even someone reading the database sees only ciphertext. The full number is shown only when an authorized person explicitly reveals it, and every reveal is recorded.
- **Ratings are trustworthy.** The official score is always calculated on the server from the factor scores, so a screen or a partner can't fake a number, and the maths is reproducible.
- **Partners see performance, not internal politics.** They get their score, the breakdown, the trend, and a written summary — but internal notes stay internal.
- **The AI agent is walled off.** The customer WhatsApp agent has no access to any of this — no banking, no internal ratings, no notes. That's enforced in code and covered by a test.

## Business value
- Enables real facility payouts (banking on file, securely).
- Gives operations a structured, auditable quality lever over facilities and drivers, with a partner-facing feedback loop.
- Carpet/curtain become independently routable services (matching, pricing, agent lookup).

## Risks / caveats to mention honestly
- Bank-document upload and manual score overrides were intentionally deferred (not needed yet).
- A real `BANK_ENCRYPTION_KEY` must be set before any non-dev use.
- This shipped alongside a concurrent WhatsApp-agent commit; the working tree still needs a clean commit + reconciliation.
