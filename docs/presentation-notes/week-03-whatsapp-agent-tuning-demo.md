# Presentation Notes — WhatsApp Agent Tuning (Week 3)

## 1. What we can show in the demo
- The **replay harness** running the 14 founder scenarios and printing PASS/FAIL:
  `cd apps/whatsapp-agent && ./.venv/Scripts/python.exe -m scripts.replay_scenarios` → **14/14 PASS**.
- The **negotiation engine** in tests: full price → 10%/15% → 20%/25% → facility-floor (34.50 on the
  founder's worked example) → escalate.
- **Routing**: "wedding dress" / "villa cleaning" / "couture" handed to a specialist, never quoted.
- **Privacy**: adversarial test proving a customer's phone/email/address never reaches a
  facility/driver message or the model's state.

## 2. Suggested demo flow
1. Run the replay harness — one screen, 14 green scenarios.
2. Show the negotiation worked example (AED 60 → 20% → 48; facility cost 30 → floor **34.50**).
3. Show a wedding-dress request routing to a specialist instead of being priced.
4. Show the privacy test output (no PII leaks).
5. Show a build report to convey the discipline (staged, tested, documented).

## 3. Screenshots needed
- Replay harness output (14/14).
- A negotiation test run.
- A privacy test run.

## 4. Talking points
- The agent now **behaves like the founder decided**: quote full price, negotiate only on haggling,
  never below a protected floor, never invent a price/turnaround/coverage.
- **The backend, not the AI, decides every number** — the model just phrases it. Safer and auditable.
- **One persona, English + Arabic**, warm and concise — no typos, no stalling, no over-promising.
- **Privacy by construction** — facilities/drivers see order ref + service + area only.

## 5. Technical explanation in simple language
We wrote the business rules as editable config and small, well-tested "engines." The AI can only
move money by asking an engine, which checks the rule and records it. So the AI can be friendly and
flexible in words while the company's rules stay firm and consistent.

## 6. Business value
- Protects margin: discounts follow a strict ladder and never go below a facility-cost floor.
- Consistency: no contradictory prices/turnaround across chats (a real pain in the old transcripts).
- Trust & compliance: no PII leakage; refunds/complaints always go to a human.
- Expansion-ready: AED/QAR plumbing in place for UAE + Qatar.

## 7. Before vs after
- **Before:** automatic 15% discount for everyone over AED 100; wedding dresses quoted as Clean &
  Press; no min-order fee/Express surcharge; AED-only; no single persona; PII not adversarially tested.
- **After:** full price first + negotiation ladder with a protected floor; specialist routing;
  min-order + Express pricing; AED/QAR; one persona (en/ar); adversarial privacy suite.

## 8. Risks / caveats to mention honestly
- The **deepest discount tier (facility-floor)** currently escalates to a human until we confirm how a
  facility's cost-per-order is calculated — a quick founder decision unlocks it.
- **QAR** is plumbed but unpriced (routes to a human) until a Qatar price list is loaded.
- The **persona name** is a placeholder until the founder sets it.
- Everything is **mock-first** — no live WhatsApp/Stripe/LLM was enabled.

## 9. What is coming next
Set the persona name; confirm the facility-floor cost basis + wire the live cost lookup; load the QAR
price list; re-seed the SLA table; then a live-WhatsApp readiness review.
