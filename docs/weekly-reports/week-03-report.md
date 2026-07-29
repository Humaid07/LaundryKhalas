# Week 3 Report

Covers **2026-07-29** (the WhatsApp Operations Agent tuning program). Follows
[[week-02-report]]. Headline: the customer-facing WhatsApp agent was **tuned to the
founder-approved specification** — a real negotiation engine replaces the old automatic
discount, plus min-order/express pricing, AED/QAR plumbing, a single persona, route-to-human
categories, adversarial privacy tests, and a §12 regression suite + replay harness. All
mock-first; nothing live was enabled. Test counts below were run this session unless noted.

## 1. Executive summary
The agent now follows the founder's confirmed rules. It quotes the **full website price** and
only discounts through a **negotiation ladder** (10→20% under AED 100, 15→25% over) with a
protected **facility-floor** (`floor = discounted − 0.75×(discounted − cost)`); it charges the
min-order delivery fee, prices Express at +50% with a 3 PM cut-off, speaks as one persona in
English/Arabic, quotes only in the customer's currency, routes villa/wedding/luxury work to a
specialist, and never leaks customer PII to facilities/drivers. Delivered in 7 staged, reviewed
slices, each with tests + a build report.

## 2. What shipped this week
- **Negotiation-only discount model** — retired the automatic 15%-over-100 discount (rollback
  flag kept); new `negotiate_order_price` tool driving the §3 ladder + facility-floor + escalation.
- **Rules/config layer** — negotiation, min-order/delivery (≥50 free / <50 → 8), Express +50% &
  3 PM cut-off, AED/QAR currency plumbing, carpet turnaround 2–5 days, persona.
- **System prompt** — persona (single name, never-reveal-AI, en/ar), §2.12 order flow (photo-gate,
  full-address capture, driver 15–30 min + reception/security/door fallbacks, special-care notes,
  alterations cm/inch), payment guardrails, AED/QAR overlay.
- **Tools** — `quote_express`, delivery fee in the summary, `route_to_specialist`.
- **Routing** — villa/home cleaning, wedding dresses, luxury/couture → specialist (never quoted).
- **Privacy** — adversarial tests proving no phone/email/full-address reaches facility/driver output
  or the model-facing state block.
- **Regression** — 14 §12 scenario tests + a runnable `scripts/replay_scenarios.py` (14/14 pass).

## 3. What changed since last update
The agent's discount behaviour changed materially: full price is quoted by default and discounts
come only from negotiation. Wedding dresses now route to a specialist instead of being quoted as
Clean & Press. Carpet turnaround corrected 3–4 → 2–5 days.

## 4. Screens/features ready to demo
No new UI. Demo is via the agent's backend + the replay harness (`scripts/replay_scenarios.py`)
and the test suites. See [[week-03-whatsapp-agent-tuning-demo]].

## 5. Backend progress
7 config files + 4 new pure services (`negotiation`, `fulfilment`, `market`, `specialty_routing`),
plus additions to `pricing`, `booking_flow`, `delivery`, `service_resolution`, `rules`, `settings`,
and the Claude booking tools/prompt.

## 6. Frontend progress
None this week (agent-only scope).

## 7. Agent progress
Persona, negotiation, min-order/express pricing, currency overlay, specialist routing, promo
suppression during complaints — all mock-first and prompt/tool-gated. The backend (never the model)
decides every price/discount/route.

## 8. Database progress
**No migration** — negotiation state reuses existing discount columns; routing uses the existing
pending-tasks table. `delivery_sla_rules` needs a re-seed (carpet/express) before live use.

## 9. Security/privacy progress
Dedicated adversarial privacy suite added; facility/driver output + the model-facing state block
proven PII-free.

## 10. Testing progress
286 passed across the 17 program-touched suites; 14/14 replay scenarios; ruff clean on all changed
files. Full suite not run (large; targeted runs per README).

## 11. Blockers
None technical. Two founder inputs gate go-live (below).

## 12. Risks
- The **facility-floor cost basis** is unconfirmed, so the deepest negotiation tier currently
  escalates to a human rather than auto-offering the floor (safe, but not the full §3.2 experience).
- QAR is plumbed but unpriced — QAR customers route to a human.

## 13. Decisions needed from founder/team
1. **Set `agent_name`** (single persona name).
2. **Confirm the facility-floor cost basis** (how a facility's cost-per-order is derived) so the
   live facility-cost lookup can be wired.
3. **Provide the Qatar (QAR) price list** to enable QAR quoting.

## 14. Deviations from roadmap/spec
Facility-floor is engine-complete but not yet reachable end-to-end (cost lookup deferred pending the
decision above). Ghost-timer auto-advance deferred (needs a scheduler). Min-order/express engines
built in Stage 1; exposed as tools in Stage 3b.

## 15. Next week's plan
Wire the live facility-cost lookup + re-seed the SLA table once the cost basis is confirmed; set the
persona name; load the QAR price list; then a live-WhatsApp readiness review.
