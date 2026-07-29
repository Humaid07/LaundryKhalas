# Build Report — Qatar (QAR) Pricing

**Date:** 2026-07-29
**Type:** Backend — market-aware pricing (mock-first)
**Follows:** the WhatsApp Operations Agent tuning program (Stages 1–7).

## Objective
Enable end-to-end **QAR quoting for Qatar** using the founder-provided price list
(https://laundrykhalas.com/en-qa/personal-laundry/pricing/), closing the "QAR plumbing now,
price list later" open item — without breaking the AED baseline.

## What was built
- **`config/laundry_catalogue_qa.json`** — QAR price overlay for the QA market: 52 personal-laundry
  items (Wash & Fold, Clean & Press, Press Only) mapped onto the existing catalogue item codes,
  from the fetched Qatar page. (QAR ≈ AED for most items; additional-weight differs: QAR 10.95/kg.)
- **`services/catalogue.py`** — `has_market_pricing()`, `market_currency()`, `market_prices()`
  (cached per-market overlay loader; AE unchanged).
- **`services/pricing.py`** — `calculate_estimate(..., market="AE")`: for a priced non-AE market it
  uses that market's prices + currency; an item the market does **not** price becomes an
  inspection line (`force_pending`) so an AE number is **never** quoted as QAR. Quote formatting now
  uses the quote's currency instead of a hardcoded "AED".
- **`services/booking_flow.py`** — `market` threaded through `_pricing_updates` /
  `pricing_updates_for_row` so persisted totals are in the right currency.
- **`agents/whatsapp_agent/booking_tools.py`** — passes the (normalised) market into
  `get_order_summary`, `negotiate_order_price`, `quote_express`, and the grounding tools.
- **`agents/whatsapp_agent/llm_tools.py`** — `lookup_item_price` is market-aware (QAR label for QA;
  unpriced items → "priced after inspection"); fixed stale "auto 15% over AED 100" guidance to the
  negotiation-only model.
- **`config/markets.json`** — QA `pricing_configured: true`.

## Verification (offline)
```
QA 6kg bag + 4kg extra  → QAR 103.80   (60 + 4×10.95)   [AE equivalent stays AED 88]
QA 5 shirts             → QAR 45
QA duvet (no QA price)  → priced after inspection (never the AED 42)
lookup "cardigan" (QA)  → "QAR 18";  (AE) → "AED 18"
```

## Tests run / results (honest)
- `tests/test_qa_pricing.py` (8) + updated `test_market.py` / `test_agent_prompt_persona.py`.
- Consolidated regression across 19 program suites: **321 passed**; replay harness **14/14**;
  ruff clean on all changed files. No live calls; the QA prices were read once from the public
  pricing page the founder supplied and stored in config (source recorded in the file).

## Known limitations
- The QA overlay covers **personal laundry** only (the fetched page). QA specialty categories
  (Shoe/Bag/Carpet/Curtains/Alterations/Soft Toys/Restoration) are inspection/photo-quote/route for
  QA until a QA specialty price list is provided — no AED numbers leak.
- Regular (crossed-out) prices for QA are cosmetic; only the payable price is authoritative.
- FSM fallback path still defaults to AE; the Claude orchestration path (default) is market-aware.

## Next
Provide the QA specialty price list to extend QAR coverage; the two remaining founder items are the
`agent_name` and the facility-floor cost basis.
