# Build Report — Knowledge Reinforcement Phase 1 (Rules → Config)

- **Date:** 2026-08-08
- **Design spec:** `docs/superpowers/specs/2026-08-08-knowledge-reinforcement-design.md`
- **Source material:** `C:\Users\HP\Downloads\Whatsapp agent knowledge reinforcing material\`
  (`Whatsapp agent rules for every service.docx`, `LaundryKhalas_Pricing_Questions.docx`,
  `LaundryKhalas_WhatsApp_Agent_Master_Prompt_1.md`) — chats handled in Phase 2.

## Objective

Encode the founder's documented business rules into `config/*.json` so the agent
follows them at runtime, filling the gaps a full audit found vs the current config.

## Audit headline

An automated audit mapped ~50 concrete rules from the docs against the live
config. **The large majority were already correctly encoded** in prior sessions
(all Wash&Fold weight tiers + multi-bag optimization, the full alterations price
matrix, express +50%/3PM cutoff, min-order 30/fee 10, negotiation ladder,
coverage, VAT-inclusive, toy/mascot/bedding/sofa/carpet prices). Phase 1 is a
targeted gap-fill.

## Changes made (all tested)

### 1. Leather garments — NEW `LEATHER_CARE` category
Previously the agent could not quote leather clothing at all. Added
`config/laundry_catalogue.json` category `LEATHER_CARE` (sort_order 12):
- `LEATHER_JACKET` From AED 80, `LEATHER_TROUSERS` From 50, `LEATHER_SKIRT` From 50,
  `LEATHER_GLOVES` From 20 — all `is_starting_price` + `requires_inspection` (photo).
- "leather jacket" resolves to `LEATHER_JACKET` (longest-alias match); bare
  "jacket" still resolves to Clean & Press (unaffected). Exotic/crocodile/python
  leather still routes to `LUXURY_BESPOKE` (unchanged).

### 2. Wedding dress — now QUOTED (founder decision: quote 150–400)
- Added `CLEAN_PRESS_DRESS_WEDDING` From AED 150, `is_starting_price` +
  `requires_inspection` (photo). Aliases: wedding dress/gown, bridal gown/dress/wear.
- Removed the `WEDDING_DRESS` route-to-human category from
  `config/specialty_routing.json`. Wedding dress is now quoted (From 150, ask for a
  photo) instead of silently handed to a human.
- Heavily embellished/embroidered wedding dresses still fall to the bespoke
  photo-flow (facility quote), which is correct.
- Added `SLA_WEDDING_DRESS` 1–3 days.

### 3. Evening dress — now a "from" price
`CLEAN_PRESS_DRESS_EVENING` set `is_starting_price` + `pricing_type: STARTING_FROM`
(founder: "estimate at our price; facility may revise for beading/size").

### 4. Turnaround (SLA) corrections in `config/delivery_sla.json`
- **Curtains** → 3–4 days (added `SLA_CURTAIN`; was defaulting to 1–2 days).
- **Alterations** → 1–2 days (was 2 days).
- **Mascots** → 2–3 days (was 2 days).
- **Restoration** → 2–5 days (was 2–3 days).

### 5. B2B (`services/b2b.py`)
- Acknowledgement now promises a **same-day response, before close of business**.
- Added qualifying keywords: gym, spa, salon, clinic, factory, manufacturing,
  warehouse, kitchen linen.

### 6. Min-order — already correct
`config/fulfilment_charges.json` already encodes: order ≥ 30 → free delivery;
below 30 → ask the customer to add an item, else a flat 10 AED fee stated up
front. Matches the founder's clarified rule exactly. No change.

## Founder decisions recorded

- **Wedding dress:** quote From 150 (not route to human). ✅ implemented.
- **Discount cap conflict:** the "25% max, then escalate" in the pricing doc is
  the standard negotiation ladder; the **facility-cost floor is the approved
  exception** — the agent MAY concede deeper than 25% down toward (never below)
  the facility's cost floor. **No change to negotiation logic** (already built
  this way).

## Deferred (not built)

- Press-only folding surcharge (+1 AED) — needs a code modifier; low value.
- Bag standard-vs-designer SLA split — needs item-level SLA; low value.

## Flagged

- **WhatsApp service menu now has 12 category rows**; WhatsApp interactive lists
  cap at 10 (already 11 before leather). The live agent asks conversationally, so
  this may not bite; if it does, mark `LEATHER_CARE` hidden-from-menu (it still
  resolves by alias). To verify.

## Files changed

- `config/laundry_catalogue.json` (LEATHER_CARE category, wedding item, evening from-price)
- `config/specialty_routing.json` (removed WEDDING_DRESS routing)
- `config/delivery_sla.json` (curtain/alterations/mascot/restoration/wedding SLAs)
- `services/b2b.py` (same-day response + keywords)
- Tests: `tests/test_delivery_sla.py`, `tests/test_catalogue_pricing.py`,
  `tests/test_specialty_routing.py`, `tests/test_service_resolution.py`,
  `tests/test_service_persistence.py`, `tests/test_service_selection_interactive.py`

## Tests

- Targeted suites (catalogue, SLA, specialty routing, resolution, persistence,
  interactive, B2B): **all green** (135 + 21 assertions across the affected areas).
- Full suite: see completion note.
- New/updated tests assert: leather resolution + from-price; wedding quoted not
  routed; embellished wedding → bespoke; SLA values; leather doesn't hijack "jacket".

## Deploy note (IMPORTANT)

`config/*.json` is import-time source of truth; the **Supabase DB is the runtime
source**. For production to pick up these changes, re-seed:
- `scripts/seed_service_catalogue.py` (catalogue incl. leather/wedding/evening)
- `scripts/seed_delivery_sla.py` (turnaround changes)
Specialty-routing + B2B are read from config/code directly (no reseed needed).

## How to verify in production

After re-seeding: message the agent and confirm — "leather jacket" quotes From
AED 80 + asks for a photo; "wedding dress" quotes From 150 + asks for a photo;
"curtains" says 3–4 days; a B2B enquiry mentions a same-day response.

## Next

Phase 2 — retrieval KB from the 533 real chats (redact → embed → pgvector →
`search_past_conversations` tool). Its own build report on completion.
