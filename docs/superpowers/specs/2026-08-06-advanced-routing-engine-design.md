# Advanced Routing Engine + Trial-Facility Test Environment — Design

**Date:** 2026-08-06
**Status:** Approved — ONE shared, production-capable engine (extends `facility_matching.py`),
wired into `assign_facility_for_order` with off/shadow/canary/live modes. Test/prod strictly isolated.

## 1. Objective
A single authoritative routing engine that evaluates the same eligibility → availability → ranking →
explanation logic for BOTH synthetic test orders (test facilities/drivers) and real customer orders
(production facilities/drivers), with strict environment isolation, decision snapshots, safe legacy
fallback, and a staged rollout (shadow → canary → live) reviewable by Operations. Plus 11 seeded trial
facilities + drivers and the full routing test matrix.

## 2. Ground truth (from inspection)
- Production auto-assignment: `facilities_repo.select_for_location` — lexicographic SQL ORDER BY
  (location-match → open/busy → spare-capacity → least-loaded → age). Only hard gate: `is_active AND
  operating_status NOT IN (closed,paused)`. No distance/drivers/rating/cost/hours. Called by
  `services/facility_routing.assign_facility_for_order` from `order_confirmation.py`.
- Richer engine `services/facility_matching.py::rank()` — pure eligibility (status, accepts_orders,
  service coverage, radius/distance, operating hours) + lexicographic rank (open, spare-capacity,
  distance, quality_score). Only used by the agent tool, NOT by routing. Raw `quality_score`.
- Schema gaps: facilities lack rating/review_count/workload/express/specialist-capability columns
  (quality_score exists, manual). Drivers lack shift/break/leave/employment/express_eligible/
  service_days/assignment-limit (>1) fields; 1 active assignment enforced by a partial-unique index.
  No availability engine feeds routing. No simulator. Test markers exist everywhere; no
  keep-test-out-of-routing flag. Latest migration 000048 → next **000049**.

## 3. Architecture (shared, environment-agnostic)
```
Customer or test order
  → Environment-specific candidate LOADER (test rows XOR prod rows; never mixed)
  → SHARED advanced evaluator (pure):
       eligibility (hard) → driver+hours availability → pickup slots → ranking + explanation
  → Atomic idempotent assignment (order id + routing_version; compare-and-set)
  → Facility Dashboard
```
- `services/routing/availability.py` (pure) — driver availability from shift/break/leave/status/
  assignment/limit at a given `when`; canonical taxonomy + `available_driver_count` +
  express-capable-available. No wall-clock (takes `when`).
- `services/routing/eligibility.py` (pure) — hard checks, returns rejection reason codes per candidate.
- `services/routing/scoring.py` (pure) — weighted (Bayesian) rating + distance/quality/workload/
  capacity/available-drivers/pickup-delay/express/cost(if approved) → score_components + final score.
- `services/routing/slots.py` (pure) — valid pickup slots from facility hours ∩ driver availability ∩
  lead-time ∩ express-cutoff; stable slot ids.
- `services/routing/evaluator.py` (pure) — orchestrates the above → shared result contract.
- `services/routing/candidate_loader.py` — thin async adapters loading TEST xor PROD facilities+drivers
  (environment isolation enforced here + in SQL).
- `services/routing/config.py` — mode (off|shadow|canary|live), canary %, deterministic cohort
  (`sha1(order_id+routing_version) % 100`), fallback flag, snapshot-required flag.
- `db/repositories/routing_decisions_repo.py` — persist the snapshot (test + prod).
- Integration in `facility_routing.assign_facility_for_order`: mode dispatch, atomic assignment,
  fallback to legacy, manual-routing case when advanced finds no eligible facility (never bypassed).

### Result contract
```
{ selected_facility_id, selected_driver_id|null, selected_pickup_slot_id|null,
  routing_version: "ADVANCED_ROUTING_V1", eligible_candidates:[], rejected_candidates:[],
  score_components:{}, selection_reason:str, fallback_used:bool }
```

## 4. Environment isolation (backend-enforced)
Flags (production defaults): `ADVANCED_ROUTING_ENABLED=false`, `ADVANCED_ROUTING_MODE=off`,
`ADVANCED_ROUTING_CANARY_PERCENTAGE=0`, `ADVANCED_ROUTING_FALLBACK_TO_LEGACY=true`,
`ADVANCED_ROUTING_REQUIRE_DECISION_SNAPSHOT=true`, `ENABLE_TEST_FACILITIES=false`,
`ENABLE_TEST_DRIVERS=false`, `ALLOW_TEST_FACILITY_ROUTING=false`,
`ALLOW_PRODUCTION_FACILITY_ROUTING=true`, `ALLOW_TEST_FACILITIES_FOR_PRODUCTION=false`,
`ALLOW_PRODUCTION_FACILITIES_FOR_TEST=false`, `ALLOW_TEST_ORDER_CREATION=false`.
An order's environment (`orders.environment` / `is_test_data`) selects the loader; the loader filters
facilities/drivers by matching `is_test_facility`/`is_test_driver` + environment. A production order can
NEVER see a test facility and vice-versa. Test facilities never receive real customer PII (the existing
facility-handoff firewall still applies).

## 5. Weighted rating (documented, tested)
The legacy production router uses NO rating. `facility_matching` uses raw `quality_score`. The advanced
engine introduces an explicit, documented **Bayesian weighted rating**:
`weighted = (C*m + review_count*rating) / (C + review_count)` with prior `m` (global mean, default 4.3)
and confidence `C` (default 20). This prevents a 4.9★/3-review facility from outranking a 4.7★/160-review
one. It is a NEW, documented factor (the spec permits introducing it if documented + tested); raw rating
and review_count are also surfaced in the explanation.

## 6. Rejection reason codes
SERVICE_NOT_SUPPORTED, SPECIALIST_CAPABILITY_MISSING, OUTSIDE_SERVICE_RADIUS, FACILITY_PAUSED,
FACILITY_CLOSED, FACILITY_OUTSIDE_WORKING_HOURS, CAPACITY_UNAVAILABLE, NO_DRIVERS_ASSIGNED,
NO_DRIVERS_SCHEDULED, NO_AVAILABLE_DRIVER, DRIVER_ON_BREAK, DRIVER_ON_LEAVE, DRIVER_OFFLINE,
DRIVER_ASSIGNMENT_LIMIT_REACHED, DRIVER_OUTSIDE_SHIFT, EXPRESS_NOT_SUPPORTED, NO_EXPRESS_DRIVER_AVAILABLE,
TURNAROUND_UNAVAILABLE, MARKET_NOT_SUPPORTED, TEST_ENVIRONMENT_MISMATCH.

## 7. Driver availability taxonomy (derived)
AVAILABLE, ASSIGNED, ON_PICKUP, ON_DELIVERY, ON_BREAK, OFFLINE, ON_LEAVE, NOT_YET_ON_SHIFT, SHIFT_ENDED,
UNAVAILABLE. Derived (in priority order) from active flag/status, leave window, offline, shift window vs
`when`, break window vs `when`, active assignment, assignment-limit. `available_driver_count` counts only
AVAILABLE (+capacity); express-capable-available additionally requires `express_eligible`.

## 8. DEFAULT_SEED_TIME decision
`DEFAULT_SEED_TIME = 2026-08-06T12:30 Asia/Dubai` (a Thursday). The spec's per-driver seed statuses are
NOT simultaneously realizable at one instant (proof: Deira D6 `ON_BREAK` needs t∈[12,13]; Bar1 D2 on a
14–22 shift `AVAILABLE` needs t≥14). Resolution: drivers store real shift/break/leave/assignment data and
the engine derives status at any `when`. At 12:30 every stated status holds EXCEPT the two later-shift
"available" drivers (Bar1 D2, Palm D3), whose shifts are set to **12:00–20:00** (documented deviation from
the literal 14:00 start) to realize the intended "two overlapping shifts, both available" at seed time.
Shift-boundary behaviour is tested on Marina (D1 07–15 vs D2 15–23) around 15:00.

## 9. Decomposition (staged areas)
- **A. Foundation** — migration 000049 (facility rating/review/perf/workload/express/turnaround +
  `facility_capabilities` + `facility_services.express_ok`; driver shift/break/leave/employment/
  express/service_days/limit/test markers; `routing_decisions`); settings flags; `routing/config.py`.
- **B. Pure core** — availability, eligibility (+codes), scoring (weighted rating), slots, evaluator +
  exhaustive unit tests (covers most of the ~55 matrix as pure tests).
- **C. Loaders + snapshot + integration** — candidate loaders (env-isolated), snapshot repo, wire into
  `assign_facility_for_order` (mode dispatch, atomic idempotent assign, fallback, manual-routing case).
  Integration + concurrency + shadow/canary/live/fallback tests.
- **D. Seed/reset** — `seed_test_facilities_and_drivers` (11 exact facilities+drivers, idempotent),
  `reset_test_facilities_and_drivers` (TEST-guarded). Acceptance tests (exactly 11, driver counts, etc.).
- **E. Simulator + Ops monitoring** — admin routing simulator (overrides, rerun, save-override) +
  shadow-comparison monitoring page + API. Uses the SAME engine.
- **F. Facility-dashboard validation + docs + full sweep.**

## 10. Guardrails
No production routing behaviour changes until Operations moves the mode off `off`/`shadow`. No test
facility ever routes a production order. Never assign twice / two facilities / two slot sets. Advanced
"no eligible facility" → Operations manual-routing case, never a legacy bypass of safety. All overrides
audited. No LLM invents facilities, prices, or pickup times.
