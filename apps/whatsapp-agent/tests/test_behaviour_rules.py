"""Phase 1: the canonical behaviour_rules section is the source of truth and loads."""
import json
from pathlib import Path

import rules

CONFIG = Path(__file__).resolve().parent.parent / "config" / "whatsapp_agent_rules.json"
EXPECTED_IDS = {
    "WHATSAPP_BRAND_NAME", "WHATSAPP_RESPONSE_LENGTH", "WHATSAPP_RESPONSE_SEGMENTATION",
    "WHATSAPP_NO_UNNECESSARY_CTA", "WHATSAPP_SOFT_CONVERSION_STYLE", "WHATSAPP_DISCOUNT_FOLLOWUP",
    "WHATSAPP_PICKUP_SLOT_SELECTION", "WHATSAPP_NO_OPEN_ENDED_PICKUP_TIME",
    "WHATSAPP_HUMAN_CONVERSION_ESCALATION",
}


def _cfg() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_brand_name_is_laundry_khalas():
    assert _cfg()["brand_name"] == "Laundry Khalas"


def test_no_double_a_typo_in_config():
    assert "Khalaas" not in CONFIG.read_text(encoding="utf-8")


def test_all_nine_behaviour_rules_present_and_active():
    by_id = {r["id"]: r for r in _cfg()["behaviour_rules"]["rules"]}
    assert set(by_id) == EXPECTED_IDS
    assert all(r.get("active", True) for r in by_id.values())
    assert all(str(r["text"]).strip() for r in by_id.values())


def test_section_is_versioned():
    section = _cfg()["behaviour_rules"]
    assert section.get("version")
    assert section.get("updated_at")


def test_brand_rule_carries_param():
    by_id = {r["id"]: r for r in _cfg()["behaviour_rules"]["rules"]}
    assert by_id["WHATSAPP_BRAND_NAME"]["params"]["brand_name"] == "Laundry Khalas"


def test_segmentation_rule_max_three():
    by_id = {r["id"]: r for r in _cfg()["behaviour_rules"]["rules"]}
    assert by_id["WHATSAPP_RESPONSE_SEGMENTATION"]["params"]["max_segments"] == 3


def test_behaviour_rule_texts_active_priority_desc():
    texts = rules.behaviour_rule_texts()
    assert any("Laundry Khalas" in t for t in texts)
    assert any("1, 2, or at most 3" in t for t in texts)
    # brand rule (priority 100) renders before segmentation (priority 89)
    brand_i = next(i for i, t in enumerate(texts) if "Laundry Khalas" in t and "never" in t.lower())
    seg_i = next(i for i, t in enumerate(texts) if "at most 3" in t)
    assert brand_i < seg_i


def test_brand_name_accessor():
    assert rules.brand_name() == "Laundry Khalas"
