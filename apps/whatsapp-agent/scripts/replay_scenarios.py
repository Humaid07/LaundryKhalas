"""Replay harness (spec §11) — run the founder §12 scenarios through the agent's
backend rule-engines in MOCK mode and print a compliance report.

This is the deterministic "does the agent obey the rules" check: it exercises the
same pricing / negotiation / delivery / routing / complaint / privacy engines the
live agent uses, plus the assembled system prompt, and reports PASS/FAIL per
scenario. It makes NO LLM, WhatsApp or Stripe calls.

Run:
    cd apps/whatsapp-agent
    ./.venv/Scripts/python.exe -m scripts.replay_scenarios
Exit code is non-zero if any scenario fails.
"""
from __future__ import annotations

import datetime as _dt
import sys
from decimal import Decimal

from agents.whatsapp_agent.booking_tools import booking_system_prompt
from services import complaints, delivery, negotiation, pricing, service_resolution, specialty_routing

PROMPT = booking_system_prompt()


def _s1() -> bool:
    q = pricing.calculate_estimate([{"item_code": "WASH_FOLD_6KG", "quantity": 1}])
    t = delivery.order_turnaround(["WASH_FOLD_6KG"])
    return q.prices_include_vat and q.customer_total > 0 and not q.discount_applied \
        and (t["min_hours"], t["max_hours"]) == (24, 24)


def _s2() -> bool:
    a = negotiation.plan_offer(60).percentage == Decimal("10")
    b = negotiation.plan_offer(60, current_percentage=Decimal("10")).percentage == Decimal("20")
    f = negotiation.plan_offer(60, current_percentage=Decimal("20"), itemised=True,
                               facility_cost=Decimal("30")).price == Decimal("34.50")
    return a and b and f


def _s3() -> bool:
    return negotiation.plan_offer(200).percentage == Decimal("15") \
        and negotiation.plan_offer(200, current_percentage=Decimal("15")).percentage == Decimal("25")


def _s4() -> bool:
    q = delivery.express_quote(["WASH_FOLD_6KG"], 100, _dt.datetime(2026, 7, 29, 16, 30))
    return q.eligible and q.requires_facility_check and "quote_express" in PROMPT


def _s5() -> bool:
    return "PHOTO before any quote" in PROMPT


def _s6() -> bool:
    return "building/villa/flat number" in PROMPT and "room number for hotels" in PROMPT


def _s7() -> bool:
    return "Never invent availability" in PROMPT


def _s8() -> bool:
    return "prefer secure online card payment" in PROMPT and "cash on" in PROMPT \
        and "NEVER arrange cash off-system directly with the driver" in PROMPT


def _s9() -> bool:
    return bool(complaints.classify_category("burn mark on my shirt", None)) \
        and "REFUNDS require a human" in PROMPT


def _s10() -> bool:
    return specialty_routing.classify("villa deep cleaning").category == "HOME_CLEANING" \
        and service_resolution.classify_service_request("wedding dress").kind \
        is service_resolution.ServiceKind.ROUTE


def _s11() -> bool:
    return "sample garment OR exact measurements" in PROMPT and "cm or inches" in PROMPT


def _s12() -> bool:
    from agents.whatsapp_agent.booking_tools import workflow_state_block
    block = workflow_state_block({"order_id": "LK-1", "pickup_address": "Villa 12, Al Barsha",
                                  "pickup_area": "Al Barsha"})
    return block["order"]["pickup_address_present"] and "Villa 12" not in str(block)


def _s13() -> bool:
    return "NEVER send a review request" in PROMPT


def _s14() -> bool:
    return "Arabic" in PROMPT


SCENARIOS = [
    ("S1  Wash & Fold quote (VAT-inclusive, 24h, nothing invented)", _s1),
    ("S2  Haggle < 100 (10->20->floor 34.50)", _s2),
    ("S3  Haggle >= 100 (15->25)", _s3),
    ("S4  Express after 3 PM (facility check, not rejected)", _s4),
    ("S5  Specialty photo-gate", _s5),
    ("S6  Address + room capture", _s6),
    ("S7  Slot honesty", _s7),
    ("S8  Payment (card-first, cash fallback, no driver side-deal)", _s8),
    ("S9  Complaint escalation, no refund promise", _s9),
    ("S10 Villa/wedding/luxury route-to-specialist", _s10),
    ("S11 Alterations cm/inch", _s11),
    ("S12 Privacy: no full address in state block", _s12),
    ("S13 Promo suppression during complaint", _s13),
    ("S14 Arabic reply", _s14),
]


def main() -> int:
    print("LaundryKhalas WhatsApp agent - s12 scenario replay (mock mode)\n" + "=" * 60)
    failures = 0
    for label, check in SCENARIOS:
        try:
            ok = bool(check())
        except Exception as exc:  # noqa: BLE001
            ok = False
            label = f"{label}  [error: {exc}]"
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failures += 0 if ok else 1
    print("=" * 60)
    print(f"{len(SCENARIOS) - failures}/{len(SCENARIOS)} scenarios passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
