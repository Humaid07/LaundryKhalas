# Service Taxonomy — Test Script / Checklist

Use this to verify the live LaundryKhalas service taxonomy is wired end-to-end.
All steps are **mock-safe** (no live WhatsApp / Stripe / LLM / website calls).

---

## A. Automated (fastest)

From `apps/whatsapp-agent`:

```bash
# 1. Cross-surface sync check (backend vs WhatsApp vs SEO vs dashboard mirror)
python scripts/verify_service_taxonomy.py        # exits 0 + "OK — all surfaces are in sync."

# 2. Taxonomy test suite
.venv/Scripts/python -m pytest tests/test_service_taxonomy.py -q

# 3. Full backend suite (regression)
.venv/Scripts/python -m pytest -q                 # 245 passed
```

From `apps/admin`:

```bash
npx tsc --noEmit -p tsconfig.json                 # 0 new errors
npx tsx lib/dashboard/filters.test.ts             # 45/45 pass
```

## B. Service dropdown / clarification (WhatsApp agent)

- [ ] `GET /api/service-taxonomy/options` returns the 8 services + `help_me_choose`.
- [ ] Send **"Hi, I need a laundry pickup service"** → agent asks *"which service?"*
      and shows the 8 service buttons (it does NOT pick one).
- [ ] Send **"I'd like to book a pickup"** → same clarification + `SERVICE_ACTIONS`.

## C. Item → service mapping (order extraction)

| customer says | expected service |
|---|---|
| "I need dry cleaning for two suits" | Boutique Clean & Press |
| "I need my shoes cleaned" / "restore my sneakers" | Artisan Shoe Restoration |
| "I need carpet cleaning" / "clean my curtains" | Deep Carpet & Curtain Care |
| "just my weekly laundry, a bag of clothes" | Premium Wash & Fold |
| "I have a duvet and some towels" | Luxe Bed & Bath Care |
| "hem my trousers and fix a zip" | Tailoring & Alterations |
| "clean my designer handbag" | Luxury Bag Spa |
| bare "shirts and trousers" (no service word) | *ambiguous → ask clarification* |

- [ ] Each row above resolves as expected (covered by `test_service_taxonomy.py`).

## D. Pricing safety (RULE 7 / 8)

- [ ] "How much for curtains cleaning?" → *"team will confirm the exact price"*,
      **no** AED figure (carpet/curtain is `requires_manual_quote`).
- [ ] Boutique Clean & Press with 2 suits → floor estimate `AED 22` stored in `amount`.
- [ ] Bag spa / tailoring / carpet-curtain → `amount` stays `null` (manual quote).

## E. Supabase order storage

*(dev/test Supabase mode — requires DB creds; otherwise the repo mapping is
covered by `test_order_row_maps_service_fields_to_dashboard_shape`.)*

- [ ] Migration `20260722_000004_service_taxonomy.sql` applied — `orders` has
      `service_id`, `service_display_name`, `unit_type`, `requires_manual_quote`.
- [ ] A WhatsApp-captured order stores `service_id` + `service_display_name`
      + `unit_type` + item list.

## F. Dashboard

- [ ] Global **Service** filter lists the 8 real services (Premium Wash & Fold …
      Deep Carpet & Curtain Care).
- [ ] `/operations/customer-orders` live orders show the selected service
      (`service_display_name`).
- [ ] Break sync on purpose (edit one `display_name` in `service-catalog.ts`),
      reload `/operations/customer-orders` with the live flag on →
      **"Service taxonomy mismatch detected."** banner appears. Revert to clear it.

## G. SEO agents

- [ ] `seo_agents/taxonomy.py` `taxonomy_service_ids()` == backend `service_ids()`.
- [ ] Content clusters cover: wash & fold, dry cleaning / clean & press, steam
      pressing / ironing, bed & bath, shoe cleaning, tailoring, carpet & curtain,
      luxury bag, + umbrella "personal laundry pickup and delivery".
