# WhatsApp Agent Spec Gap-Close (A–F) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close six spec gaps in the WhatsApp Operations Agent — full per-item facility rate card, payment-method capture, structured alterations capture, alterations turnaround, stale docs, and same-day express semantics — mock-first and fully tested.

**Architecture:** Follow the codebase's established seam: a **pure/deterministic service** does the logic (unit-tested offline) and a **thin tool handler** in `agents/whatsapp_agent/booking_tools.py` wires it to persistence. Facility cost stays server-side and never reaches any customer/facility/model-facing output. Migrations target the dev/test Supabase only and are additive + idempotent; the SQLite test harness uses an in-memory `FakeOrdersRepo`, so most unit tests need no schema change.

**Tech Stack:** Python 3.11, pytest (async), asyncpg (Supabase), SQLAlchemy models (SQLite test schema), JSON config, `services.money` (Decimal).

## Global Constraints

- **Mock-first.** No live LLM / WhatsApp / Stripe. No live external calls. (CLAUDE.md §5.)
- **Never invent data.** Prices/rates/SLA come from config/DB; unknown → escalate/pending, never a guessed number. (CLAUDE.md §5.7–5.8.)
- **Privacy firewall.** Facility cost + item rates are cost data — never in any customer/facility/model-facing output or assembled prompt. (CLAUDE.md §7.)
- **Migrations:** dev/test Supabase ONLY; additive; idempotent; label MOCK. Apply via the existing asyncpg apply/verify script pattern.
- **Currency:** AED (UAE) / QAR (Qatar) resolved by `services.market`; never mix currencies.
- **Money:** always via `services.money` (Decimal, HALF-UP).
- **Commits:** the owner's standing rule is *commit to `main` only when asked*. The commit steps below are written for completeness; at execution, batch them and push only on the owner's go-ahead.
- **Do NOT touch:** persona naming (deferred decision G) or the approval-queue / driver-availability tool (deferred decision H). Document them; build neither.
- **Design source:** `docs/superpowers/specs/2026-07-31-whatsapp-agent-spec-gapclose-design.md`.

---

## File Structure

**Create**
- `apps/whatsapp-agent/services/payment.py` — pure payment-method normalisation (card/cash).
- `apps/whatsapp-agent/services/alterations.py` — pure alteration-detail validation (cm/inch gate).
- `apps/whatsapp-agent/tests/test_payment_preference.py` — payment tool + pure tests.
- `apps/whatsapp-agent/tests/test_alterations_capture.py` — alteration tool + pure tests.
- `apps/whatsapp-agent/scripts/build_facility_item_rates_seed.py` — maps Appendix A → catalogue `item_code`s, emits SQL INSERT rows + an unmapped-lines report.
- `supabase/migrations/20260731_000036_facility_item_rates.sql` — `facility_item_rates` table + Appendix A per-item seed + `facility_services` rows for added categories.
- `supabase/migrations/20260731_000037_orders_payment_method.sql` — `orders.payment_method` column.
- `apps/whatsapp-agent/scripts/apply_migration_000036_037.py` + `verify_migration_000036_037.py` — apply/verify on dev/test Supabase (mirror the existing apply/verify script pattern).

**Modify**
- `apps/whatsapp-agent/config/delivery_sla.json` — `SLA_ALTERATIONS` 1–2 days (D); express same-day meta (F).
- `apps/whatsapp-agent/services/delivery.py` — same-day express model + docstrings (F, E).
- `apps/whatsapp-agent/services/market.py` — docstring reconcile: Qatar is priced (E).
- `apps/whatsapp-agent/services/facility_cost.py` — `item_rates` lookup tier (A).
- `apps/whatsapp-agent/db/repositories/facility_pricing_repo.py` — `candidates_for_item` (A).
- `apps/whatsapp-agent/agents/whatsapp_agent/booking_tools.py` — pass `item_rates` (A); `set_payment_preference` + `request_payment_link` tools (B); `record_alteration_details` tool (C).
- `apps/whatsapp-agent/db/repositories/orders_repo.py` — `payment_method` in `_BOOKING_COLS` + `set_payment_method` (B).
- `apps/whatsapp-agent/models.py` — `Order.payment_method` + `FacilityItemRate` model (B, A test schema).
- `apps/whatsapp-agent/tests/test_facility_cost.py` — per-item resolution tests (A).
- `apps/whatsapp-agent/tests/test_delivery_sla.py` — tailoring 1–2 days + same-day express (D, F).
- `apps/whatsapp-agent/tests/test_scenarios_regression.py` — S4/S8/S11 toward runtime behaviour.
- `apps/whatsapp-agent/tests/test_privacy_firewall.py` — item rates never surface.
- `docs/build-reports/2026-07-31-whatsapp-agent-tuning.md` — build report (CLAUDE.md §12).

---

## Task 1: Item D (alterations turnaround) + Item E (stale docs)

Small, self-contained: config value + docstring reconciles. Grouped because each is a one-liner with a single verifying test (D) / no behaviour change (E).

**Files:**
- Modify: `apps/whatsapp-agent/config/delivery_sla.json:22`
- Modify: `apps/whatsapp-agent/services/market.py:1-11,87-90`
- Modify: `apps/whatsapp-agent/services/delivery.py:9-16` (Qatar/express wording only; the same-day model itself is Task 2)
- Test: `apps/whatsapp-agent/tests/test_delivery_sla.py`

**Interfaces:**
- Consumes: `services.delivery.order_turnaround(item_codes)` (existing).
- Produces: no new symbols; `SLA_ALTERATIONS` now min 24 / max 48, display "1–2 days".

- [ ] **Step 1: Write the failing test** in `tests/test_delivery_sla.py`

```python
def test_alterations_turnaround_is_one_to_two_days():
    from services import delivery
    delivery.reload_sla()
    t = delivery.order_turnaround(["ALTERATIONS_JEANS_LENGTH"])  # any ALTERATIONS item
    assert t["min_hours"] == 24
    assert t["max_hours"] == 48
    assert t["display_text"] == "1–2 days"
```

> If `ALTERATIONS_JEANS_LENGTH` is not the real code, use any item whose `category_code == "ALTERATIONS"` from `config/laundry_catalogue.json`; the rule matches on category, so the exact item only needs to resolve to that category.

- [ ] **Step 2: Run it, verify it fails**

Run: `cd apps/whatsapp-agent && python -m pytest tests/test_delivery_sla.py::test_alterations_turnaround_is_one_to_two_days -v`
Expected: FAIL — current display "2 days", max_hours 48 but min_hours 48.

- [ ] **Step 3: Fix the config.** In `config/delivery_sla.json`, change the `SLA_ALTERATIONS` rule (line 22):

```json
    {"code": "SLA_ALTERATIONS", "match": {"category_code": "ALTERATIONS"}, "min_hours": 24, "max_hours": 48, "day_type": "CALENDAR", "express_eligible": false, "priority": 10, "display_text": "1–2 days"},
```

- [ ] **Step 4: Run test, verify pass**

Run: `cd apps/whatsapp-agent && python -m pytest tests/test_delivery_sla.py::test_alterations_turnaround_is_one_to_two_days -v`
Expected: PASS

- [ ] **Step 5: Reconcile stale docs (E).** No behaviour change — docstrings only.

In `services/market.py`, replace the two "Qatar (QAR) is not yet priced" claims:
- Module docstring (lines ~6-8): change to note that QA pricing is now configured (`markets.json` `pricing_configured: true`, QA catalogue overlay live); QAR quotes are served from the QA catalogue, not routed to a human for lack of a price.
- The `market_for_phone`/`pricing_configured_for_phone` inline note if it repeats the claim.

In `services/delivery.py`, module docstring (lines 9-16): the "Express = 12h" statements are superseded by Task 2; leave a one-line pointer that express is the same-day model (final wording lands in Task 2). No code change in this task.

- [ ] **Step 6: Run the delivery + market suites to confirm no regression**

Run: `cd apps/whatsapp-agent && python -m pytest tests/test_delivery_sla.py tests/test_market.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add apps/whatsapp-agent/config/delivery_sla.json apps/whatsapp-agent/services/market.py apps/whatsapp-agent/services/delivery.py apps/whatsapp-agent/tests/test_delivery_sla.py
git commit -m "WhatsApp agent: tailoring turnaround 1-2 days + reconcile Qatar-priced docs"
```

---

## Task 2: Item F — Express = same-day (founder semantics)

Replace the fixed `express_hours: 12` customer-facing model with **same calendar day** when the order is express-eligible and pickup is before the 15:00 cutoff. Surcharge (+50%) and cutoff unchanged; post-cutoff still not auto-rejected.

**Files:**
- Modify: `apps/whatsapp-agent/config/delivery_sla.json:3-13` (meta)
- Modify: `apps/whatsapp-agent/services/delivery.py:85-146` (`order_turnaround`, `estimate_delivery`, `_delivery_text`), `:229-243` (`delivery_options`), docstrings `:9-16,149-151`
- Test: `apps/whatsapp-agent/tests/test_delivery_sla.py`

**Interfaces:**
- Consumes: `services.money`, `services.clock.combine` (market-local datetime).
- Produces:
  - `delivery.express_same_day_end_local() -> str` ("HH:MM", default "21:00").
  - `order_turnaround(item_codes, express=True)` result gains `"same_day": True` and `display_text == "same day"` (replaces `"12 hours (Express)"`).
  - `estimate_delivery(item_codes, pickup_end_at, express=True)` — when the result is `same_day`, `estimated_delivery_end_at` = end-of-business (`express_same_day_end_local`) on the **pickup date**, not `pickup_end + hours`.

- [ ] **Step 1: Write failing tests** in `tests/test_delivery_sla.py`

```python
import datetime as _dt


def test_express_turnaround_is_same_day_not_twelve_hours():
    from services import delivery
    delivery.reload_sla()
    t = delivery.order_turnaround(["WASH_FOLD_STANDARD_KG"], express=True)  # any express-eligible item
    assert t["applied_express"] is True
    assert t.get("same_day") is True
    assert t["display_text"] == "same day"
    assert "12 hours" not in t["display_text"]


def test_express_estimate_lands_end_of_pickup_day():
    from services import delivery
    delivery.reload_sla()
    pickup_end = _dt.datetime(2026, 7, 25, 11, 0)  # 11:00 on pickup day
    est = delivery.estimate_delivery(["WASH_FOLD_STANDARD_KG"], pickup_end, express=True)
    end = est["estimated_delivery_end_at"]
    assert end.date() == pickup_end.date()          # same calendar day
    assert (end.hour, end.minute) == (21, 0)         # end-of-business, config-driven
```

> Use a real express-eligible item code (category ∈ {WASH_FOLD, CLEAN_PRESS, PRESS_ONLY}); confirm the exact code from `config/laundry_catalogue.json` (e.g. the Wash & Fold per-kg item).

- [ ] **Step 2: Run, verify fail**

Run: `cd apps/whatsapp-agent && python -m pytest tests/test_delivery_sla.py -k express -v`
Expected: FAIL — current display is `"12 hours (Express)"`, no `same_day` key, estimate is `pickup+12h`.

- [ ] **Step 3: Update meta** in `config/delivery_sla.json` (keep `express_cutoff_local`, `express_surcharge_pct`):

```json
  "meta": {
    "timezone": "Asia/Dubai",
    "day_type": "CALENDAR",
    "express_model": "SAME_DAY",
    "express_same_day_end_local": "21:00",
    "express_hours": 12,
    "express_surcharge_aed": null,
    "express_surcharge_pct": 0.5,
    "express_cutoff_local": "15:00",
    "express_eligible_categories": ["WASH_FOLD", "CLEAN_PRESS", "PRESS_ONLY"],
    "source": "Laundry Khalas standard turnaround rules (task spec §23; express = same-day, founder 2026-07-31)",
    "verified_at": "2026-07-31"
  },
```

> `express_hours` is retained only as a legacy fallback; the customer-facing path no longer uses it.

- [ ] **Step 4: Implement the same-day model** in `services/delivery.py`.

Add near `express_cutoff_local` (after line 160):

```python
def express_same_day_end_local() -> str:
    """Local end-of-business time an Express same-day order is delivered by
    ('HH:MM', default 21:00). Config-driven — never invented."""
    return str(meta().get("express_same_day_end_local", "21:00"))


def _same_day_end_time() -> _dt.time:
    raw = express_same_day_end_local()
    try:
        hh, mm = (int(x) for x in raw.split(":", 1))
        return _dt.time(hour=hh, minute=mm)
    except (ValueError, TypeError):
        return _dt.time(hour=21, minute=0)
```

In `order_turnaround`, replace the express branch (lines 101-107):

```python
    if express and express_eligible:
        return {
            "min_hours": 0, "max_hours": 0, "day_type": "CALENDAR",
            "display_text": "same day",
            "rule_codes": ["EXPRESS"], "express_eligible": True,
            "applied_express": True, "same_day": True,
        }
```

Ensure the non-express return dict also carries `"same_day": False` (add the key to the two other return dicts in `order_turnaround` for a stable shape).

In `estimate_delivery` (lines 121-136), special-case same-day so the estimate lands end-of-business on the pickup date:

```python
def estimate_delivery(item_codes, pickup_end_at, *, express=False):
    t = order_turnaround(item_codes, express=express)
    start_at = end_at = None
    if pickup_end_at is not None:
        if t.get("same_day"):
            end_at = _dt.datetime.combine(pickup_end_at.date(), _same_day_end_time(),
                                          tzinfo=pickup_end_at.tzinfo)
            start_at = pickup_end_at
        else:
            start_at = pickup_end_at + _dt.timedelta(hours=t["min_hours"])
            end_at = pickup_end_at + _dt.timedelta(hours=t["max_hours"])
    return {
        **t,
        "estimated_delivery_start_at": start_at,
        "estimated_delivery_end_at": end_at,
        "estimated_delivery_text": _delivery_text(t, start_at, end_at),
    }
```

In `delivery_options` (lines 234-242), replace the express display/hours so it reads "same day":

```python
    if std["express_eligible"]:
        exp = order_turnaround(item_codes, express=True)
        out["express"] = {
            "mode": "EXPRESS", "display_text": exp["display_text"],  # "same day"
            "same_day": True,
            "surcharge_pct": float(express_surcharge_pct()),
            "cutoff_local": express_cutoff_local(),
            "same_day_end_local": express_same_day_end_local(),
        }
```

Update the module docstring (lines 9-16) and the section header (lines 149-151): Express = **same calendar day** when collected before the 15:00 cutoff; +50% surcharge; a request after the cutoff is not auto-rejected (facility capacity checked, else standard 24h). Remove the "Express = 12h" wording finalised from Task 1.

- [ ] **Step 5: Run, verify pass**

Run: `cd apps/whatsapp-agent && python -m pytest tests/test_delivery_sla.py -v`
Expected: PASS (including existing tests — verify none asserted the old "12 hours" string; if any did, update them to "same day").

- [ ] **Step 6: Check `express_quote` snapshot callers.** `express_quote`/`ExpressQuote` (lines 186-226) are unchanged (surcharge math), but grep for any test/consumer asserting `"12 hours"`:

Run: `cd apps/whatsapp-agent && grep -rn "12 hours" tests/ agents/ services/`
Fix any such assertion/prompt string to "same day".

- [ ] **Step 7: Commit**

```bash
git add apps/whatsapp-agent/config/delivery_sla.json apps/whatsapp-agent/services/delivery.py apps/whatsapp-agent/tests/test_delivery_sla.py
git commit -m "WhatsApp agent: express = same-day (founder semantics), retire fixed 12h display"
```

---

## Task 3: Item A part 1 — per-item facility cost lookup (pure)

Add an `item_rates` tier to `facility_cost.compute_facility_cost`. Pure/offline; no DB, no behaviour change when `item_rates` is omitted (back-compat).

**Files:**
- Modify: `apps/whatsapp-agent/services/facility_cost.py:73-120`
- Test: `apps/whatsapp-agent/tests/test_facility_cost.py`

**Interfaces:**
- Produces: `compute_facility_cost(lines, rates, *, quotations=None, item_rates=None, min_charge=0, operational_fees=0) -> FacilityCostResult`. Per non-quote line the resolution order is: **quotation** (bespoke/inspection) → **`item_rates[item_code]`** → **`rates[service_code]`** → **unpriced**. Measured lines multiply the resolved rate by the measure; count lines by quantity.

- [ ] **Step 1: Write failing tests** in `tests/test_facility_cost.py`

```python
def test_item_rate_overrides_category_rate():
    from services import facility_cost as fc
    lines = [
        {"item_code": "CLEAN_PRESS_SHIRT", "service_code": "CLEAN_PRESS",
         "pricing_type": "FIXED_PER_ITEM", "quantity": 2},
        {"item_code": "CLEAN_PRESS_ABAYA", "service_code": "CLEAN_PRESS",
         "pricing_type": "FIXED_PER_ITEM", "quantity": 1},
    ]
    # Category rate 6; per-item shirt 7, abaya 8.
    res = fc.compute_facility_cost(lines, {"CLEAN_PRESS": 6.0},
                                   item_rates={"CLEAN_PRESS_SHIRT": 7.0, "CLEAN_PRESS_ABAYA": 8.0})
    assert res.complete is True
    assert float(res.facility_cost) == 22.0          # 2*7 + 1*8, NOT 3*6=18


def test_item_rate_falls_back_to_category_then_unpriced():
    from services import facility_cost as fc
    lines = [{"item_code": "CLEAN_PRESS_SHIRT", "service_code": "CLEAN_PRESS",
              "pricing_type": "FIXED_PER_ITEM", "quantity": 1}]
    # No item rate → category rate 6 used.
    res = fc.compute_facility_cost(lines, {"CLEAN_PRESS": 6.0}, item_rates={})
    assert res.complete is True and float(res.facility_cost) == 6.0
    # No item rate AND no category rate → incomplete.
    res2 = fc.compute_facility_cost(lines, {}, item_rates={})
    assert res2.complete is False and res2.facility_cost is None


def test_backcompat_without_item_rates_kwarg():
    from services import facility_cost as fc
    lines = [{"item_code": "X", "service_code": "CLEAN_PRESS",
              "pricing_type": "FIXED_PER_ITEM", "quantity": 1}]
    res = fc.compute_facility_cost(lines, {"CLEAN_PRESS": 6.0})   # no item_rates
    assert res.complete is True and float(res.facility_cost) == 6.0
```

- [ ] **Step 2: Run, verify fail**

Run: `cd apps/whatsapp-agent && python -m pytest tests/test_facility_cost.py -k "item_rate or backcompat" -v`
Expected: FAIL — `compute_facility_cost` has no `item_rates` kwarg.

- [ ] **Step 3: Implement the tier** in `services/facility_cost.py`.

Change the signature (line 73-75) to add `item_rates`:

```python
def compute_facility_cost(lines: list[dict], rates: dict[str, float] | None, *,
                          quotations: dict[str, float] | None = None,
                          item_rates: dict[str, float] | None = None,
                          min_charge=0, operational_fees=0) -> FacilityCostResult:
```

Add `item_rates = item_rates or {}` next to the existing `rates`/`quotations` defaults (line 88-89). Replace the standard-rate block (lines 103-108) so the item rate wins over the category rate:

```python
        item_code = ln.get("item_code")
        rate = item_rates.get(item_code)
        if rate is None:
            rate = rates.get(service_code)
        if rate is None:
            unpriced.append(code)
            continue
        qty = billable_quantity(ln.get("pricing_type"), ln.get("quantity"), ln.get("measure"))
        subtotal += money.round_money(money.to_decimal(rate) * qty)
```

Update the module/function docstrings to record the resolution order (quotation → item_rate → category rate → unpriced).

- [ ] **Step 4: Run, verify pass**

Run: `cd apps/whatsapp-agent && python -m pytest tests/test_facility_cost.py -v`
Expected: PASS (new + all existing).

- [ ] **Step 5: Commit**

```bash
git add apps/whatsapp-agent/services/facility_cost.py apps/whatsapp-agent/tests/test_facility_cost.py
git commit -m "WhatsApp agent: per-item facility cost tier (item_rate over category), back-compatible"
```

---

## Task 4: Item A part 2 — facility_item_rates table, Appendix A seed, repo + wiring

Persist per-item facility rates and feed them into the floor computation. Migration + SQLAlchemy model (SQLite test schema) + repo method + caller wiring.

**Files:**
- Create: `apps/whatsapp-agent/scripts/build_facility_item_rates_seed.py`
- Create: `supabase/migrations/20260731_000036_facility_item_rates.sql`
- Modify: `apps/whatsapp-agent/models.py` (add `FacilityItemRate`)
- Modify: `apps/whatsapp-agent/db/repositories/facility_pricing_repo.py` (add `candidates_for_item`)
- Modify: `apps/whatsapp-agent/agents/whatsapp_agent/booking_tools.py:99-131` (`_facility_cost_for_order`)
- Test: `apps/whatsapp-agent/tests/test_facility_pricing.py`

**Interfaces:**
- Consumes: `facility_cost.compute_facility_cost(..., item_rates=...)` (Task 3); `facility_pricing.pick_lowest` (existing).
- Produces:
  - Table `facility_item_rates(id, facility_id, item_code, rate, currency, active, valid_from, valid_to, created_at, updated_at, unique(facility_id, item_code))`.
  - `facility_pricing_repo.candidates_for_item(item_code, *, market=None, lat=None, lon=None) -> list[dict]` (rows: `facility_id, facility_code, latitude, longitude, rate, currency, distance_km`).

- [ ] **Step 1: Build the Appendix A → item_code mapping script.** Create `scripts/build_facility_item_rates_seed.py`. It reads the catalogue (source of truth) so no item_code is invented; unmapped Appendix-A lines are reported, never guessed.

```python
"""Map the Appendix A facility cost rate card → catalogue item_codes and emit the
SQL INSERT rows for migration 000036. Any Appendix-A line with no catalogue match
is printed to stderr and left UNSEEDED (never invented). Run:
    python scripts/build_facility_item_rates_seed.py > /tmp/facility_item_rates_rows.sql
"""
import sys
from services import catalogue

# (Appendix A label, catalogue alias/name to match, AED cost). Labels grouped by
# the design doc §Appendix A. Extend/adjust the alias where a name differs.
RATE_CARD = [
    # Clean & Press
    ("Shirt", "shirt", 7.0), ("Polo", "polo", 8.0), ("Top/Blouse", "blouse", 8.0),
    ("Trousers/Jeans", "trousers", 10.0), ("Abaya", "abaya", 8.0), ("Kandura", "kandura", 7.0),
    ("Jacket/Blazer", "blazer", 23.0), ("2-Piece Suit", "2 piece suit", 31.0),
    ("Evening Dress", "evening dress", 33.0),
    # Home & Care (measured lines are per-sqm rate)
    ("Carpet Regular", "carpet", 15.0), ("Carpet Wool", "wool carpet", 22.0),
    ("Blanket", "blanket", 11.0), ("Duvet", "duvet", 25.0),
    # Shoe / Bag
    ("Formal shoes", "formal shoes", 48.0), ("Sneakers", "sneakers", 42.0),
    ("Backpack", "backpack", 110.0), ("Handbag", "handbag", 143.0),
    # Alterations
    ("Jeans length cut", "jeans length", 13.20), ("Pant waist", "waist", 19.80),
    # ... (complete from design doc §Appendix A)
]


def _resolve(alias: str) -> str | None:
    codes, reason = catalogue.resolve_item_alias(alias)
    return codes[0] if reason == "ok" and codes else None


def main() -> None:
    rows, unmapped = [], []
    for label, alias, cost in RATE_CARD:
        code = _resolve(alias)
        if code:
            rows.append((code, cost))
        else:
            unmapped.append((label, alias))
    for label, alias in unmapped:
        print(f"UNMAPPED (left unseeded): {label!r} via alias {alias!r}", file=sys.stderr)
    # Emit VALUES tuples for both MOCK facilities.
    for fac in ("FAC-DXB-MARINA", "FAC-AUH-CENTRAL"):
        for code, cost in rows:
            print(f"    ('{fac}','{code}',{cost:.2f}),")


if __name__ == "__main__":
    main()
```

> Complete `RATE_CARD` from the design doc's Appendix A. Where a catalogue item is `PER_SQM` (carpets) the cost is the per-sqm rate — `facility_cost.billable_quantity` multiplies by the measure automatically. Where the catalogue models a line as `STARTING_FROM`/inspection (some alterations/restoration), the item rate acts as the quotation seed; note it in the migration comment.

- [ ] **Step 2: Author the migration.** Create `supabase/migrations/20260731_000036_facility_item_rates.sql`:

```sql
-- =====================================================================
-- LaundryKhalas — Facility per-ITEM rates (Appendix A rate card, MOCK)
-- Migration: 20260731_000036_facility_item_rates
-- Target: dev/test Supabase ONLY. Additive + idempotent.
-- Backs the per-item negotiation floor (design §3). Item rate overrides the
-- category rate; cost NEVER surfaced (CLAUDE.md §7). Unmapped Appendix-A lines
-- are intentionally omitted (see scripts/build_facility_item_rates_seed.py).
-- =====================================================================
create table if not exists facility_item_rates (
    id           uuid primary key default gen_random_uuid(),
    facility_id  uuid not null references facilities (id) on delete cascade,
    item_code    text not null,
    rate         numeric(12,2) not null,          -- MOCK internal cost per unit/sqm
    currency     text not null default 'AED',
    active       boolean not null default true,
    valid_from   date,
    valid_to     date,
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now(),
    unique (facility_id, item_code)
);
create index if not exists idx_facility_item_rates_code on facility_item_rates (item_code);
alter table facility_item_rates enable row level security;
drop trigger if exists set_facility_item_rates_updated_at on facility_item_rates;
create trigger set_facility_item_rates_updated_at before update on facility_item_rates
    for each row execute function set_updated_at();

-- Extend service coverage so the added categories are offered + can be costed.
insert into facility_services (facility_id, service_code, offered, bespoke_ok)
select f.id, s.code, true, s.bespoke
from facilities f
cross join (values
    ('HOME_CARE', false), ('SOFT_TOY', false),
    ('ALTERATIONS', false), ('RESTORATION', true)
) as s(code, bespoke)
where f.code in ('FAC-DXB-MARINA', 'FAC-AUH-CENTRAL')
on conflict (facility_id, service_code) do nothing;

-- Category fallback rates for the added categories (blended MOCK).
insert into facility_rates (facility_id, service_code, rate)
select f.id, r.code, r.rate
from facilities f
join (values
    ('FAC-DXB-MARINA','HOME_CARE',15.00), ('FAC-DXB-MARINA','SOFT_TOY',31.00),
    ('FAC-DXB-MARINA','ALTERATIONS',13.20), ('FAC-DXB-MARINA','RESTORATION',48.00),
    ('FAC-AUH-CENTRAL','HOME_CARE',16.00), ('FAC-AUH-CENTRAL','SOFT_TOY',33.00),
    ('FAC-AUH-CENTRAL','ALTERATIONS',14.00), ('FAC-AUH-CENTRAL','RESTORATION',50.00)
) as r(fcode, code, rate) on r.fcode = f.code
on conflict (facility_id, service_code) do nothing;

-- Per-item Appendix A seed (rows generated by build_facility_item_rates_seed.py).
insert into facility_item_rates (facility_id, item_code, rate)
select f.id, r.item_code, r.rate
from facilities f
join (values
    -- <<< paste the generated VALUES tuples here >>>
    ('FAC-DXB-MARINA','CLEAN_PRESS_SHIRT',7.00)
) as r(fcode, item_code, rate) on r.fcode = f.code
on conflict (facility_id, item_code) do nothing;
```

- [ ] **Step 3: Add the SQLAlchemy model** (SQLite test schema) in `models.py`, following the existing `Base` + `mapped_column` style:

```python
class FacilityItemRate(Base):
    __tablename__ = "facility_item_rates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    facility_id: Mapped[str] = mapped_column(String(36), index=True)
    item_code: Mapped[str] = mapped_column(String(64), index=True)
    rate: Mapped[float] = mapped_column()
    currency: Mapped[str] = mapped_column(String(8), default="AED")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
```

- [ ] **Step 4: Write the failing repo test** in `tests/test_facility_pricing.py` (mirror how existing repo tests seed rows; if the existing file only tests pure `pick_lowest`, add a DB test guarded like the other DB-backed tests in the suite). The pure selection is already covered; assert `candidates_for_item` returns the seeded rows lowest-first via `pick_lowest`:

```python
@pytest.mark.asyncio
async def test_candidates_for_item_returns_item_rate(seed_two_facilities_with_item_rate):
    from db.repositories import facility_pricing_repo
    from services import facility_pricing
    cands = await facility_pricing_repo.candidates_for_item("CLEAN_PRESS_SHIRT", market="AE")
    assert cands, "expected at least one facility item rate"
    chosen = facility_pricing.pick_lowest(cands)
    assert chosen["rate"] is not None
```

> If facility tables are not present in the SQLite test schema (they are asyncpg/Supabase-only in this repo), follow the existing convention for `facility_pricing_repo` tests — mark the DB test with the same skip/live marker other facility-repo tests use, and rely on the pure `compute_facility_cost` tests (Task 3) for logic coverage. Do not invent a SQLite facility schema if the codebase doesn't already have one.

- [ ] **Step 5: Implement `candidates_for_item`** in `db/repositories/facility_pricing_repo.py`, mirroring `candidates_for_service` (lines 37-62) but joining `facility_item_rates`:

```python
async def candidates_for_item(item_code: str, *, market: str | None = None,
                              lat=None, lon=None) -> list[dict]:
    """Qualified facilities that have an active per-ITEM rate for item_code, with
    their rate + distance. Used only for the backend negotiation floor."""
    rows = await database.fetch(
        """
        select f.id as facility_id, f.code as facility_code,
               f.latitude, f.longitude, f.capacity_daily,
               r.rate, r.currency
        from facilities f
        join facility_item_rates r on r.facility_id = f.id
             and r.item_code = $1 and r.active = true
        where f.is_active = true and f.accepts_orders = true
          and f.operating_status not in ('closed','paused')
          and ($2::text is null or f.market is null or f.market = $2::text)
        """,
        item_code, market,
    )
    out = []
    for row in rows:
        d = dict(row)
        d["distance_km"] = facility_pricing.haversine_km(lat, lon, d["latitude"], d["longitude"])
        d["facility_id"] = str(d["facility_id"])
        out.append(d)
    return out
```

- [ ] **Step 6: Wire item rates into the floor** in `agents/whatsapp_agent/booking_tools.py` `_facility_cost_for_order` (lines 99-131). After building the per-category `rates` map, build a per-item map and pass it:

```python
        item_rates: dict[str, float] = {}
        for ln in lines:
            code = ln.get("item_code")
            if not code:
                continue
            candidates = await facility_pricing_repo.candidates_for_item(code, market=ctx.market)
            chosen = facility_pricing.pick_lowest(candidates)
            if chosen and chosen.get("rate") is not None:
                item_rates[code] = float(chosen["rate"])
        result = fc.compute_facility_cost(lines, rates, item_rates=item_rates)
```

Keep the existing try/except fail-safe: any DB/offline failure still yields `None` (→ pending), never a guess. Facility cost remains logged internally only.

- [ ] **Step 7: Run the facility suites**

Run: `cd apps/whatsapp-agent && python -m pytest tests/test_facility_cost.py tests/test_facility_pricing.py -q`
Expected: PASS.

- [ ] **Step 8: Generate the seed + apply migration to dev/test Supabase** (done in Task 7's apply step — the migration file must be complete first). For now verify the migration parses and the seed script runs:

Run: `cd apps/whatsapp-agent && python scripts/build_facility_item_rates_seed.py 2>/tmp/unmapped.txt | head` and review `/tmp/unmapped.txt` — every unmapped line is a deliberate omission, not an error.

- [ ] **Step 9: Commit**

```bash
git add apps/whatsapp-agent/scripts/build_facility_item_rates_seed.py supabase/migrations/20260731_000036_facility_item_rates.sql apps/whatsapp-agent/models.py apps/whatsapp-agent/db/repositories/facility_pricing_repo.py apps/whatsapp-agent/agents/whatsapp_agent/booking_tools.py apps/whatsapp-agent/tests/test_facility_pricing.py
git commit -m "WhatsApp agent: per-item facility rate card (Appendix A seed) wired into negotiation floor"
```

---

## Task 5: Item B — payment-method capture (mock)

Persist a card/cash preference and provide a **mock** payment-link handoff that mints no Stripe link.

**Files:**
- Create: `apps/whatsapp-agent/services/payment.py`
- Create: `apps/whatsapp-agent/tests/test_payment_preference.py`
- Modify: `apps/whatsapp-agent/db/repositories/orders_repo.py:522-550` (`_BOOKING_COLS`) + new `set_payment_method`
- Modify: `apps/whatsapp-agent/models.py` (`Order.payment_method`)
- Modify: `apps/whatsapp-agent/agents/whatsapp_agent/booking_tools.py` (schemas + dispatch)
- Create: `supabase/migrations/20260731_000037_orders_payment_method.sql`

**Interfaces:**
- Produces:
  - `payment.normalize_payment_method(raw) -> "card" | "cash" | None`.
  - `orders_repo.set_payment_method(order_uuid, method) -> dict | None`.
  - Tools `set_payment_preference` (input `{method}`) and `request_payment_link` (no input).

- [ ] **Step 1: Write failing pure test** in `tests/test_payment_preference.py`

```python
import pytest


def test_normalize_payment_method():
    from services import payment
    assert payment.normalize_payment_method("card") == "card"
    assert payment.normalize_payment_method("Apple Pay") == "card"
    assert payment.normalize_payment_method("pay by link") == "card"
    assert payment.normalize_payment_method("cash") == "cash"
    assert payment.normalize_payment_method("cod") == "cash"
    assert payment.normalize_payment_method("bitcoin") is None
    assert payment.normalize_payment_method("") is None
```

- [ ] **Step 2: Run, verify fail**

Run: `cd apps/whatsapp-agent && python -m pytest tests/test_payment_preference.py::test_normalize_payment_method -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement** `services/payment.py`:

```python
"""Payment-method normalisation (pure). Stripe-first: the agent pushes online
card/Apple Pay, accepts cash on reluctance, and NEVER arranges an off-system cash
side-deal with the driver (spec §2.6/§6). This maps free customer text to a stored
preference; it does NOT create a payment link (that is a deferred, live-Stripe step)."""
from __future__ import annotations

_CARD_WORDS = ("card", "credit", "debit", "apple pay", "google pay", "link", "online", "stripe")
_CASH_WORDS = ("cash", "cod", "on delivery", "on pickup", "hand")


def normalize_payment_method(raw: str | None) -> str | None:
    """Return 'card', 'cash', or None (unrecognised). Card takes precedence when a
    message mentions both (we prefer to steer to Stripe)."""
    if not raw:
        return None
    low = raw.strip().lower()
    if any(w in low for w in _CARD_WORDS):
        return "card"
    if any(w in low for w in _CASH_WORDS):
        return "cash"
    return None
```

- [ ] **Step 4: Run, verify pass**

Run: `cd apps/whatsapp-agent && python -m pytest tests/test_payment_preference.py::test_normalize_payment_method -v`
Expected: PASS

- [ ] **Step 5: Write failing tool tests** in `tests/test_payment_preference.py`, reusing the `FakeOrdersRepo` pattern from `tests/test_booking_tools.py` (copy the fake + `_ctx` helper, or import if exported). Add a `set_payment_method`/`get_latest_for_conversation` to the fake:

```python
import datetime as _dt
import json
from agents.whatsapp_agent import booking_tools
from agents.whatsapp_agent.booking_tools import BookingContext, make_booking_executor
from services import order_store


class FakeRepo:
    def __init__(self):
        self.row = {"id": "o1", "order_id": "LK-2026-000999", "conversation_id": "c1",
                    "status": order_store.PICKUP_SCHEDULED, "conversation_state": "booking_confirmed"}
        self.payment_method = None

    async def get_active_draft(self, cid):
        return self.row if self.row["status"] == order_store.DRAFT else None

    async def get_latest_for_conversation(self, cid):
        return self.row

    async def set_payment_method(self, order_uuid, method):
        self.payment_method = method
        self.row["payment_method"] = method
        return self.row


def _ctx(repo):
    return BookingContext(conversation_id="c1", order_uuid="o1", repo=repo,
                          today=_dt.date(2026, 7, 25),
                          available_slots=lambda *a, **k: [])


@pytest.mark.asyncio
async def test_set_payment_preference_persists_card():
    repo = FakeRepo()
    execute = make_booking_executor(_ctx(repo))
    out, is_err = await execute("set_payment_preference", {"method": "apple pay"})
    assert not is_err
    assert repo.payment_method == "card"
    assert json.loads(out)["payment_method"] == "card"


@pytest.mark.asyncio
async def test_set_payment_preference_rejects_junk():
    repo = FakeRepo()
    execute = make_booking_executor(_ctx(repo))
    out, is_err = await execute("set_payment_preference", {"method": "bitcoin"})
    assert is_err
    assert repo.payment_method is None


@pytest.mark.asyncio
async def test_request_payment_link_creates_pending_task_no_link(monkeypatch):
    created = {}

    async def _fake_create(task_type, **kw):
        created["type"] = task_type
        return {"task_ref": "PT-1"}

    monkeypatch.setattr("db.repositories.pending_tasks_repo.create", _fake_create)
    repo = FakeRepo()
    execute = make_booking_executor(_ctx(repo))
    out, is_err = await execute("request_payment_link", {})
    assert not is_err
    data = json.loads(out)
    assert created["type"] == "AWAITING_PAYMENT"
    assert data.get("link") in (None, "")          # NEVER mints a link
    assert data.get("handoff") is True
```

- [ ] **Step 6: Run, verify fail**

Run: `cd apps/whatsapp-agent && python -m pytest tests/test_payment_preference.py -k "preference or payment_link" -v`
Expected: FAIL — tools unknown.

- [ ] **Step 7: Add the tool schemas** to `BOOKING_TOOL_SCHEMAS` in `booking_tools.py` (after `create_pending_task`, ~line 394):

```python
    {"name": "set_payment_preference",
     "description": "Record how the customer wants to pay AFTER their order is confirmed. "
                    "Push secure online card/Apple Pay first (fast, card via a secure link); if the "
                    "customer is reluctant, cash on collection/delivery is accepted — never lose the order "
                    "over payment method, and NEVER arrange cash directly with the driver. method is 'card' "
                    "or 'cash'. The backend stores it; you do NOT create a payment link here.",
     "input_schema": {"type": "object", "properties": {"method": {"type": "string"}},
                      "required": ["method"], "additionalProperties": False}},
    {"name": "request_payment_link",
     "description": "Hand off creation of the secure card payment link to the payment system (after "
                    "processing, before dispatch). You do NOT generate the link yourself — this creates a "
                    "durable AWAITING_PAYMENT task and tells the customer a secure link will follow. Only "
                    "call once the customer chose card.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
```

- [ ] **Step 8: Add the dispatch handlers** before the final `return _err(f"Unhandled tool ...")` (line 1592). Neither is in `_WRITE_TOOLS` (payment is post-confirmation — must NOT force-create a draft):

```python
        if name == "set_payment_preference":
            from services import payment as payment_svc
            method = payment_svc.normalize_payment_method(str(ti.get("method", "")))
            if method is None:
                return _err("Unrecognised payment method — ask the customer card or cash.")
            order = await ctx.repo.get_latest_for_conversation(ctx.conversation_id)
            if not order:
                return _ok({"stored": False, "reason": "no_order",
                            "message": "No order yet — confirm the booking first."})
            await ctx.repo.set_payment_method(order["id"], method)
            logger.info("payment_preference_set", conversation=ctx.conversation_id, method=method)
            return _ok({"stored": True, "payment_method": method})

        if name == "request_payment_link":
            from db.repositories import pending_tasks_repo
            order = await ctx.repo.get_latest_for_conversation(ctx.conversation_id)
            task = await pending_tasks_repo.create(
                "AWAITING_PAYMENT", customer_id=(ctx.customer or {}).get("id"),
                conversation_id=ctx.conversation_id,
                notes=f"[PAYMENT_LINK] order {(order or {}).get('order_id')}"[:1000])
            logger.info("payment_link_requested", conversation=ctx.conversation_id)
            return _ok({"handoff": True, "link": None,
                        "reference": (task or {}).get("task_ref"),
                        "message": "A secure payment link will be sent shortly."})
```

Add both names to `_TOOL_NAMES` implicitly (they are in `BOOKING_TOOL_SCHEMAS`, so `_TOOL_NAMES` at line 456 already includes them — no extra edit).

- [ ] **Step 9: Add `set_payment_method` + allow-list to the real repo** (`orders_repo.py`). Add `"payment_method"` to `_BOOKING_COLS` (line 522-550) and:

```python
async def set_payment_method(order_uuid: str, method: str) -> dict | None:
    """Persist the customer's chosen payment method (card|cash) on any order,
    bypassing the draft-only FSM path (payment is post-confirmation)."""
    return await database.fetchrow(
        "update orders set payment_method = $2 where id = $1 returning *",
        order_uuid, method,
    )
```

- [ ] **Step 10: Add the model + migration.** In `models.py` add to `Order`:

```python
    payment_method: Mapped[str | None] = mapped_column(String(12), nullable=True)
```

Create `supabase/migrations/20260731_000037_orders_payment_method.sql`:

```sql
-- Orders: customer payment-method preference (card|cash). dev/test Supabase only.
alter table orders add column if not exists payment_method text;
alter table orders drop constraint if exists orders_payment_method_check;
alter table orders add constraint orders_payment_method_check
    check (payment_method is null or payment_method in ('card','cash'));
```

- [ ] **Step 11: Run the payment suite + booking regressions**

Run: `cd apps/whatsapp-agent && python -m pytest tests/test_payment_preference.py tests/test_booking_tools.py -q`
Expected: PASS.

- [ ] **Step 12: Commit**

```bash
git add apps/whatsapp-agent/services/payment.py apps/whatsapp-agent/tests/test_payment_preference.py apps/whatsapp-agent/db/repositories/orders_repo.py apps/whatsapp-agent/models.py apps/whatsapp-agent/agents/whatsapp_agent/booking_tools.py supabase/migrations/20260731_000037_orders_payment_method.sql
git commit -m "WhatsApp agent: payment-method capture (card/cash) + mock payment-link handoff"
```

---

## Task 6: Item C — structured alterations capture (cm/inch gate)

A tool that records alteration measurements, hard-rejecting any unit that isn't cm or inch, and stores the detail through the existing order-notes path.

**Files:**
- Create: `apps/whatsapp-agent/services/alterations.py`
- Create: `apps/whatsapp-agent/tests/test_alterations_capture.py`
- Modify: `apps/whatsapp-agent/agents/whatsapp_agent/booking_tools.py` (schema + dispatch)

**Interfaces:**
- Produces:
  - `alterations.validate_alteration_details(item, measurement_value, unit, has_sample) -> AlterationCheck` with `.ok: bool`, `.reason: str` ("ok"|"needs_unit"|"needs_measurement"|"unknown_unit"), `.unit: str|None` (normalised "cm"/"inch"), `.note_text: str|None`.
  - Tool `record_alteration_details` (input `{item, measurement_value?, unit?, has_sample}`).

- [ ] **Step 1: Write failing pure tests** in `tests/test_alterations_capture.py`

```python
def test_alteration_requires_cm_or_inch():
    from services import alterations
    r = alterations.validate_alteration_details("trousers", 30, "centimetre", has_sample=False)
    assert r.ok and r.unit == "cm"

    r2 = alterations.validate_alteration_details("trousers", 30, "inches", has_sample=False)
    assert r2.ok and r2.unit == "inch"

    r3 = alterations.validate_alteration_details("trousers", 30, "units", has_sample=False)
    assert not r3.ok and r3.reason == "unknown_unit"

    r4 = alterations.validate_alteration_details("trousers", 30, None, has_sample=False)
    assert not r4.ok and r4.reason == "needs_unit"


def test_alteration_sample_only_ok_without_measurement():
    from services import alterations
    r = alterations.validate_alteration_details("shirt", None, None, has_sample=True)
    assert r.ok and r.note_text and "sample" in r.note_text.lower()


def test_alteration_no_sample_needs_measurement():
    from services import alterations
    r = alterations.validate_alteration_details("shirt", None, None, has_sample=False)
    assert not r.ok and r.reason == "needs_measurement"
```

- [ ] **Step 2: Run, verify fail**

Run: `cd apps/whatsapp-agent && python -m pytest tests/test_alterations_capture.py -k "cm_or_inch or sample or measurement" -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement** `services/alterations.py`:

```python
"""Structured alterations capture (pure). Alterations need either a well-fitting
SAMPLE garment or EXACT measurements, and the unit must be explicitly cm or inch
(a real error source in the corpus). This validates + composes an operational note;
persistence is the caller's job (order_notes). Feasibility is still confirmed by the
tailor on inspection — this never promises an outcome (spec §2.9)."""
from __future__ import annotations

from dataclasses import dataclass

_CM = {"cm", "cms", "centimetre", "centimetres", "centimeter", "centimeters"}
_INCH = {"in", "inch", "inches", '"'}


@dataclass(frozen=True)
class AlterationCheck:
    ok: bool
    reason: str                 # ok | needs_unit | needs_measurement | unknown_unit
    unit: str | None = None     # normalised: "cm" | "inch"
    note_text: str | None = None


def _normalize_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    u = unit.strip().lower()
    if u in _CM:
        return "cm"
    if u in _INCH:
        return "inch"
    return None


def validate_alteration_details(item: str, measurement_value, unit: str | None,
                                has_sample: bool) -> AlterationCheck:
    item = (item or "alteration").strip()
    if has_sample:
        return AlterationCheck(True, "ok", None,
                               f"Alteration ({item}): well-fitting sample garment provided.")
    if measurement_value is None:
        return AlterationCheck(False, "needs_measurement")
    if unit is None:
        return AlterationCheck(False, "needs_unit")
    norm = _normalize_unit(unit)
    if norm is None:
        return AlterationCheck(False, "unknown_unit")
    return AlterationCheck(True, "ok", norm,
                           f"Alteration ({item}): {measurement_value} {norm} (no sample).")
```

- [ ] **Step 4: Run, verify pass**

Run: `cd apps/whatsapp-agent && python -m pytest tests/test_alterations_capture.py -v`
Expected: PASS

- [ ] **Step 5: Write failing tool test** (reuse the `FakeOrdersRepo` from Task 5 / `test_booking_tools.py`, monkeypatch `order_notes_repo.apply_candidate`):

```python
@pytest.mark.asyncio
async def test_record_alteration_rejects_bad_unit(monkeypatch):
    stored = {}

    async def _apply_candidate(order_id, **kw):
        stored.update(kw)
        return {"action": "stored"}

    monkeypatch.setattr("db.repositories.order_notes_repo.apply_candidate", _apply_candidate)
    monkeypatch.setattr("db.repositories.order_notes_repo.grouped_active",
                        lambda *a, **k: _async({}))
    repo = FakeDraftRepo()  # a fake whose get_active_draft returns a draft row
    execute = make_booking_executor(_ctx(repo))
    out, is_err = await execute("record_alteration_details",
                                {"item": "trousers", "measurement_value": 30, "unit": "units",
                                 "has_sample": False})
    assert is_err
    assert not stored               # nothing persisted on a bad unit


@pytest.mark.asyncio
async def test_record_alteration_stores_cm(monkeypatch):
    stored = {}

    async def _apply_candidate(order_id, **kw):
        stored.update(kw)
        return {"action": "stored"}

    async def _grouped(order_id):
        return {}

    monkeypatch.setattr("db.repositories.order_notes_repo.apply_candidate", _apply_candidate)
    monkeypatch.setattr("db.repositories.order_notes_repo.grouped_active", _grouped)
    repo = FakeDraftRepo()
    execute = make_booking_executor(_ctx(repo))
    out, is_err = await execute("record_alteration_details",
                                {"item": "trousers", "measurement_value": 30, "unit": "inches",
                                 "has_sample": False})
    assert not is_err
    assert "inch" in stored["text"].lower()
```

> `FakeDraftRepo` = a `FakeOrdersRepo` whose `get_active_draft` returns a draft row (alterations happen pre-confirmation). Add an `_async` helper or make the monkeypatched functions coroutines as shown.

- [ ] **Step 6: Run, verify fail**

Run: `cd apps/whatsapp-agent && python -m pytest tests/test_alterations_capture.py -k record_alteration -v`
Expected: FAIL — tool unknown.

- [ ] **Step 7: Add the tool schema** to `BOOKING_TOOL_SCHEMAS` (near `propose_order_note`, ~line 428):

```python
    {"name": "record_alteration_details",
     "description": "Capture an alteration/tailoring spec. Alterations need EITHER a well-fitting sample "
                    "garment (has_sample=true) OR exact measurements. When measurements are given you MUST "
                    "pass the unit and it MUST be 'cm' or 'inch' — always confirm which with the customer; "
                    "the backend rejects a missing/other unit. Feasibility is confirmed by the tailor on "
                    "inspection — never promise the outcome. The detail is stored as an operational note.",
     "input_schema": {"type": "object",
                      "properties": {"item": {"type": "string"},
                                     "measurement_value": {"type": "number"},
                                     "unit": {"type": "string"},
                                     "has_sample": {"type": "boolean"}},
                      "required": ["item", "has_sample"], "additionalProperties": False}},
```

- [ ] **Step 8: Add the dispatch handler** before the final `return _err` (line 1592):

```python
        if name == "record_alteration_details":
            from db.repositories import order_notes_repo
            from services import alterations as alt
            check = alt.validate_alteration_details(
                str(ti.get("item", "")), ti.get("measurement_value"),
                ti.get("unit"), bool(ti.get("has_sample")))
            if not check.ok:
                _msg = {
                    "needs_unit": "Ask the customer whether the measurement is in cm or inches.",
                    "unknown_unit": "That unit isn't recognised — confirm cm or inches.",
                    "needs_measurement": "Ask for exact measurements or a well-fitting sample garment.",
                }.get(check.reason, "Ask for measurements (cm or inch) or a sample garment.")
                return _err(_msg)
            draft = await _ensure_draft()
            result = await order_notes_repo.apply_candidate(
                str(draft["id"]), category="ITEM_HANDLING", text=check.note_text,
                source="CUSTOMER_MESSAGE", source_message_id=getattr(ctx, "source_message_id", None),
                conversation_id=ctx.conversation_id)
            active = await order_notes_repo.grouped_active(str(draft["id"]))
            return _ok({"recorded": True, "unit": check.unit,
                        "result": result.get("action"), "active_notes": active})
```

- [ ] **Step 9: Run the alterations suite + booking regressions**

Run: `cd apps/whatsapp-agent && python -m pytest tests/test_alterations_capture.py tests/test_booking_tools.py -q`
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add apps/whatsapp-agent/services/alterations.py apps/whatsapp-agent/tests/test_alterations_capture.py apps/whatsapp-agent/agents/whatsapp_agent/booking_tools.py
git commit -m "WhatsApp agent: structured alterations capture with cm/inch hard gate"
```

---

## Task 7: Regression tests, privacy assertion, migrations applied, build report

Tighten the §12 regression scenarios that now have real tool behaviour, prove no privacy leak, apply the migrations to dev/test Supabase, and write the build report.

**Files:**
- Modify: `apps/whatsapp-agent/tests/test_scenarios_regression.py` (S4, S8, S11)
- Modify: `apps/whatsapp-agent/tests/test_privacy_firewall.py`
- Create: `apps/whatsapp-agent/scripts/apply_migration_000036_037.py`, `verify_migration_000036_037.py`
- Create: `docs/build-reports/2026-07-31-whatsapp-agent-tuning.md`

**Interfaces:**
- Consumes: all tools/services from Tasks 2–6.

- [ ] **Step 1: Strengthen S4/S8/S11.** For each, add a runtime assertion alongside the existing prompt-string check:
  - **S4 (express after cutoff):** assert `delivery.express_quote(...)` for a before-cutoff time yields a same-day display ("same day", not "12 hours"); after-cutoff yields `requires_facility_check=True`.
  - **S8 (payment):** drive `set_payment_preference("cash")` → persisted "cash"; `set_payment_preference("apple pay")` → "card"; `request_payment_link` → `AWAITING_PAYMENT`, `link is None`.
  - **S11 (alterations):** drive `record_alteration_details` with unit "units" → error; with "inches" → recorded, note contains "inch".

Follow the existing style in `test_scenarios_regression.py` (reuse its fixtures/fakes). Keep the prompt-string assertions too — they guard the system prompt.

- [ ] **Step 2: Run the regression suite**

Run: `cd apps/whatsapp-agent && python -m pytest tests/test_scenarios_regression.py -v`
Expected: PASS.

- [ ] **Step 3: Add a privacy assertion** in `tests/test_privacy_firewall.py`: build an order that triggers a facility floor (itemised), and assert no item-rate number and no facility-cost number appears in `workflow_state_block(row)` or the facility handoff payload. Mirror the existing PII-grep assertions in that file.

Run: `cd apps/whatsapp-agent && python -m pytest tests/test_privacy_firewall.py -v`
Expected: PASS.

- [ ] **Step 4: Write the apply/verify scripts** (mirror the existing `scripts/apply_migration_*.py` / `verify_*` pattern used for 000034/000035 — asyncpg, read the `.sql`, execute, then verify table/column existence + a seed-row count). `apply_migration_000036_037.py` applies both `.sql` files in order; `verify_migration_000036_037.py` asserts:
  - `facility_item_rates` exists and has > 0 rows for both facilities;
  - `orders.payment_method` column exists with the CHECK constraint;
  - `facility_services` has the added categories.

- [ ] **Step 5: Generate the final seed + complete the migration.** Run the seed script from Task 4 Step 1 with the full `RATE_CARD`, paste the emitted VALUES rows into `000036`'s per-item INSERT, and review the unmapped report.

Run: `cd apps/whatsapp-agent && python scripts/build_facility_item_rates_seed.py 2>/tmp/unmapped.txt 1>/tmp/rows.sql && cat /tmp/unmapped.txt`

- [ ] **Step 6: Apply + verify on dev/test Supabase** (uses the dev/test `DATABASE_URL` from the env the other migrations used — never production):

Run: `cd apps/whatsapp-agent && python scripts/apply_migration_000036_037.py && python scripts/verify_migration_000036_037.py`
Expected: both print success; verify asserts pass.

- [ ] **Step 7: Full targeted suite (no live external calls).**

Run: `cd apps/whatsapp-agent && python -m pytest tests/test_delivery_sla.py tests/test_facility_cost.py tests/test_facility_pricing.py tests/test_payment_preference.py tests/test_alterations_capture.py tests/test_scenarios_regression.py tests/test_privacy_firewall.py tests/test_booking_tools.py -q`
Expected: PASS. Then run `ruff check services/ agents/ tests/` and fix any lint.

- [ ] **Step 8: Write the build report** `docs/build-reports/2026-07-31-whatsapp-agent-tuning.md` per CLAUDE.md §12 (all 25 sections): objective, what/why, files created/modified, migrations 000036/000037, agent behaviour added (payment pref, alterations capture, same-day express, per-item floor), what's mock-only (all facility rates, payment link), what's deferred (G persona, H approval-queue/driver-tool, live Stripe), tests run + results, known limitations, privacy notes (cost data server-side), how to verify. Also update `docs/00-Home.md` links and the current `docs/weekly-reports/` + `docs/presentation-notes/` week files.

- [ ] **Step 9: Commit**

```bash
git add apps/whatsapp-agent/tests/test_scenarios_regression.py apps/whatsapp-agent/tests/test_privacy_firewall.py apps/whatsapp-agent/scripts/apply_migration_000036_037.py apps/whatsapp-agent/scripts/verify_migration_000036_037.py supabase/migrations/20260731_000036_facility_item_rates.sql docs/
git commit -m "WhatsApp agent: gap-close regression + privacy tests, migrations applied, build report"
```

---

## Self-Review

**Spec coverage** (design §3–§9):
- A (facility rate card, per-item) → Tasks 3 (pure lookup) + 4 (table/seed/repo/wiring). ✔
- B (payment-method capture) → Task 5. ✔
- C (alterations capture) → Task 6. ✔
- D (alterations turnaround) → Task 1. ✔
- E (stale docs) → Task 1 (market/delivery docstrings). ✔
- F (express same-day) → Task 2. ✔
- G, H (deferred) → documented in Global Constraints + build report (Task 7 Step 8); not built. ✔
- Testing (design §10) → Tasks 1–7 each ship tests; §12 S4/S8/S11 tightened in Task 7. ✔
- Migrations (design §11) → 000036 (Task 4) + 000037 (Task 5), applied/verified in Task 7. ✔

**Placeholder scan:** the only intentional "paste generated rows here" is the Appendix-A seed, which is derived from the catalogue by a real script (Task 4 Step 1) and completed in Task 7 Step 5 — not invented data. `RATE_CARD` is seeded with concrete examples and explicitly marked to complete from the design's Appendix A. No TBD/TODO logic steps.

**Type consistency:** `compute_facility_cost(..., item_rates=...)` defined in Task 3, consumed in Task 4. `candidates_for_item` defined in Task 4, consumed there. `normalize_payment_method` / `set_payment_method` / `set_payment_preference` / `request_payment_link` names consistent across Task 5. `validate_alteration_details` / `AlterationCheck` fields (`ok`, `reason`, `unit`, `note_text`) consistent across Task 6. Tool names match `BOOKING_TOOL_SCHEMAS` additions and dispatch branches.

**Open risk carried forward:** if the SQLite test schema has no facility tables, `candidates_for_item`'s DB test follows the existing facility-repo test convention (skip/live marker) — the logic is fully covered by the pure `compute_facility_cost` tests. This is called out in Task 4 Step 4.
