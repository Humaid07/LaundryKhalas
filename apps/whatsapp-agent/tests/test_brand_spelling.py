"""Phase 1: brand spelling is 'Laundry Khalas' everywhere customer-facing; the
open-ended pickup-time step is superseded."""
import json
from pathlib import Path

import rules
from services import followups

ROOT = Path(__file__).resolve().parent.parent


def test_no_khalaas_in_runtime_source():
    offenders = []
    for pattern in ("services/*.py", "agents/whatsapp_agent/*.py", "config/*.json"):
        for p in ROOT.glob(pattern):
            if "Khalaas" in p.read_text(encoding="utf-8"):
                offenders.append(str(p.relative_to(ROOT)))
    assert offenders == [], f"brand typo 'Khalaas' remains in: {offenders}"


def test_persona_org_is_correct():
    org = json.loads((ROOT / "config" / "persona.json").read_text(encoding="utf-8"))["organization"]
    assert org == "Laundry Khalas"


def test_followup_template_uses_correct_brand():
    msg = followups.render(followups.WEB_ABANDONMENT_1, persona="Zoya")
    assert "Laundry Khalas" in msg
    assert "Khalaas" not in msg


def test_pickup_time_step_superseded():
    steps = rules.agent_rules()["booking_flow"]["steps"]
    assert "select_pickup_time" not in steps
    assert "select_pickup_slot" in steps
