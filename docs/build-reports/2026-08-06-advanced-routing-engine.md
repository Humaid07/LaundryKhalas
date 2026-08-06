# Build Report — Advanced Routing Engine + Trial-Facility Test Environment

**Date:** 2026-08-06

## Existing routing implementation found
- Production auto-assignment: `facilities_repo.select_for_location` (lexicographic SQL `ORDER BY`:
  location-match → open/busy → spare-capacity → least-loaded → age; only hard gate `is_active AND
  operating_status NOT IN (closed,paused)`), invoked by `facility_routing.assign_facility_for_order`.
  No distance/drivers/rating/cost/hours; no scoring formula.
- A richer, unused-for-routing engine `facility_matching.py::rank()` (eligibility + lexicographic rank
  on distance/quality_score) fed only the agent tool. **Extended into the shared engine per the approved
  decision** — one engine now serves test + production; production remains on legacy until Ops changes
  the mode.

## Files changed / added
- Engine (`services/routing/`): `config.py`, `availability.py`, `eligibility.py`, `scoring.py`,
  `slots.py`, `evaluator.py`, `candidate_loader.py`, `engine.py`, `simulator.py`, `trial_facilities.py`.
- Integration: `services/facility_routing.py` (mode dispatch + `_assign_advanced` + `_assign_legacy` +
  snapshot), `db/repositories/routing_decisions_repo.py`, `api/internal_routing.py`, `main.py`,
  `settings.py`.
- Seed/ops scripts: `scripts/{seed,reset}_test_facilities_and_drivers.py`, `scripts/apply_migration.py`.
- Tests: `test_routing_availability.py`, `test_routing_evaluator.py`, `test_routing_integration.py`,
  `test_trial_facilities.py`, `test_routing_simulator.py`.

## Database migrations
`20260806_000049_advanced_routing.sql` (**applied + verified** on dev/test Supabase): facility routing
attributes (rating, review_count, perf rates, workload, express, turnaround, capacity_level,
`is_test_facility`), `facility_services.express_ok`, new `facility_capabilities`, driver availability
fields (shift/break/leave/employment/express/service_days/limit/coords/`is_test_driver`), and the
`routing_decisions` snapshot table.

## The 11 facilities created / driver allocation / shifts / statuses / services / ratings / capacity /
hours
Source of truth: `services/routing/trial_facilities.py` (seeded idempotently). 11 facilities across Al
Barsha 1 (2), Deira (3), Al Barsha 2 (1), Dubai Marina (1), JVC (2), Palm Jumeirah (2); 21 drivers total
(facilities with 1, 2 and 3 drivers). Each facility carries the exact rating/review_count/quality_score/
status/radius/capacity/workload/operating-hours/services/express-services/specialist-capabilities from
the spec; each driver its shift/break/leave/express eligibility. `DEFAULT_SEED_TIME = 2026-08-06 12:30`
(the spec's per-driver statuses are not simultaneously realizable at one instant — resolved by deriving
status from shift/break/leave at any evaluation time; two later-shift "available" drivers use a
documented 12:00 start). Verified: exactly 11 facilities, ≤3 drivers each, distinct coordinates.

## Driver availability rules
`availability.py` derives (in priority) OFFLINE → ON_LEAVE → NOT_YET_ON_SHIFT/SHIFT_ENDED → ON_BREAK →
ASSIGNED/ON_PICKUP/ON_DELIVERY (stored status or ≥ assignment limit) → AVAILABLE, at a given time.
`available_driver_count` counts only AVAILABLE; express requires `express_eligible`. Total vs available
are always separate — a facility with 3 drivers but 0 available is rejected.

## Routing hard eligibility rules
`eligibility.py` runs before scoring and returns reason codes: `SERVICE_NOT_SUPPORTED`,
`SPECIALIST_CAPABILITY_MISSING`, `OUTSIDE_SERVICE_RADIUS`, `FACILITY_PAUSED/CLOSED/OUTSIDE_WORKING_HOURS`,
`CAPACITY_UNAVAILABLE`, `NO_DRIVERS_ASSIGNED/SCHEDULED`, `NO_AVAILABLE_DRIVER`,
`DRIVER_ON_BREAK/ON_LEAVE/OFFLINE/OUTSIDE_SHIFT/ASSIGNMENT_LIMIT_REACHED`, `EXPRESS_NOT_SUPPORTED`,
`NO_EXPRESS_DRIVER_AVAILABLE`, `TURNAROUND_UNAVAILABLE`, `MARKET_NOT_SUPPORTED`,
`TEST_ENVIRONMENT_MISMATCH`.

## Routing scoring logic / how ratings + reviews + availability + hours affect routing
`scoring.py` (only eligible facilities): weighted-sum of normalized components — distance (0.30),
**Bayesian weighted_rating** (0.25; `(C·m + n·r)/(C+n)`, m=4.3, C=20), quality (0.10), workload (0.15),
available_drivers (0.10), pickup_delay (0.10), cost (0 unless approved). Ratings/reviews only rank among
eligible facilities (a 4.9/3-review facility does NOT beat a 4.7/160-review one; a highly rated facility
never wins a service it doesn't support). Driver availability enters both eligibility (0 available →
rejected) and score (available_drivers component). Facility + driver operating hours gate slot validity.

## Routing simulator changes
`services/routing/simulator.py` + `POST /api/internal/routing/simulate` rerun the SAME engine with
temporary overrides (facility status/workload/rating/services, driver status/shift/break/express) — no DB
edits unless `save`. Backend-complete; the admin simulator UI is the remaining front-end piece.

## Facility Dashboard validation
Test orders route only to test facilities (environment-isolated loader); the redesigned Facility
Dashboard (previous build) renders the assigned order. Routing scores/competing facilities are never in
the facility payload (diagnostics are internal-only, RLS-denied).

## Operations Dashboard controls
`GET /api/internal/routing/config`, `POST /simulate`, `GET /decisions`, `GET /decisions/mismatches`
(shadow legacy-vs-advanced review queue). Facility/driver status overrides reuse the existing internal
facilities + drivers APIs; the routing-monitoring admin page is the remaining front-end piece.

## Automated test scenarios / results
`test_routing_*` + `test_trial_facilities` (~90 assertions) cover the matrix at the pure level: service/
specialist eligibility before scoring, weighted-review ranking, 1-available-beats-3-unavailable,
3-total/1-scheduled, break/leave/shift/offline/assignment-limit, capacity/status gates, express support +
driver + 3 PM cutoff, distance-vs-availability, no-eligible→manual; plus integration (mode dispatch,
atomic assign, shadow comparison, manual case, legacy fallback, env isolation) and simulator overrides.
**All green.** Live E2E against the seeded Supabase: 5/5 routing scenarios correct.

## Routing defects identified and fixed
Availability precedence (stored active-task status must read as busy regardless of count); granular
per-driver rejection reasons surfaced alongside the aggregate; Palm Luxury express-CP implied CP service
(added); seed time-object + partial-index ON CONFLICT fixes.

## How to seed / reset / run the simulator
Seed: `ENABLE_TEST_FACILITIES=true ALLOW_TEST_SEED=true python scripts/seed_test_facilities_and_drivers.py`
(idempotent). Reset: `ALLOW_TEST_RESET=true python scripts/reset_test_facilities_and_drivers.py --confirm TEST`
(deletes ONLY test rows). Simulator: `POST /api/internal/routing/simulate` (ops-guarded).

## Rollout / production-capability
Deterministic modes in `config.py`: off (legacy), shadow (advanced evaluated + compared, legacy assigns),
canary (deterministic cohort %), live (advanced assigns). Fallback to legacy on advanced error
(production only; test never touches legacy). A correct "no eligible facility" opens an Operations
manual-routing case — never a legacy bypass. Atomic idempotent assignment via `orders.set_facility`
compare-and-set. **Defaults: engine off, all test/ALLOW flags false — production behaviour unchanged.**

## Remaining limitations
Admin front-ends for the simulator + routing-monitoring page (APIs are complete + tested); production
shadow/canary/live enablement is an Operations decision (env-controlled). Internal facility cost stays a
0-weight factor (not an approved routing factor today).
