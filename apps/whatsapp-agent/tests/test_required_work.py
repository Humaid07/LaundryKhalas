"""Deterministic Required Work builder — grounded, never invented (Area 1)."""
from services import required_work as rw


def test_press_and_quantity_pluralisation():
    order = {"service_display_name": "Iron / Press", "line_items": [
        {"name": "Shirt", "quantity": 5},
    ]}
    out = rw.build_required_work(order, [])
    assert out == ["Press 5 Shirts"]


def test_wash_and_fold_verb():
    order = {"service": "Wash & Fold", "line_items": [{"name": "Mixed load", "quantity": 1}]}
    assert rw.build_required_work(order, []) == ["Wash & fold 1 Mixed load"]


def test_alteration_instruction_is_appended_from_item_field():
    order = {"service_display_name": "Alterations", "line_items": [
        {"name": "Trouser", "quantity": 2, "instruction": "Reduce length by 4 cm"},
    ]}
    out = rw.build_required_work(order, [])
    assert out == ["Alter 2 Trousers — Reduce length by 4 cm"]


def test_inspection_notes_become_work_lines():
    order = {"service_display_name": "Dry Clean", "line_items": [{"name": "Blazer", "quantity": 1}]}
    notes = [
        {"category": "INSPECTION_REQUIREMENT", "text": "stain on blue shirt sleeve", "status": "ACTIVE"},
        {"category": "INSPECTION_REQUIREMENT", "text": "Check lining is intact", "status": "ACTIVE"},
        {"category": "PICKUP_INSTRUCTION", "text": "Ring the bell", "status": "ACTIVE"},  # ignored
    ]
    out = rw.build_required_work(order, notes)
    assert "Dry clean 1 Blazer" in out
    assert "Inspect: stain on blue shirt sleeve" in out
    assert "Check lining is intact" in out  # already starts with an inspect verb
    assert all("Ring the bell" not in line for line in out)


def test_unknown_service_falls_back_to_service_label_not_invention():
    order = {"service_display_name": "Premium Care", "line_items": [{"name": "Jacket", "quantity": 3}]}
    # verb is the real service label, never a guessed action.
    assert rw.build_required_work(order, []) == ["Premium Care 3 Jackets"]


def test_legacy_items_array_and_dedup():
    order = {"service": "Wash & Fold", "items": [
        {"item": "Towel", "quantity": 2}, {"item": "Towel", "quantity": 2},
    ]}
    out = rw.build_required_work(order, [])
    assert out == ["Wash & fold 2 Towels"]  # duplicate collapsed


def test_empty_when_no_structured_items():
    assert rw.build_required_work({"service": "Wash & Fold"}, []) == []


def test_already_plural_name_not_double_pluralised():
    order = {"service": "Dry Clean", "line_items": [{"name": "Trousers", "quantity": 3}]}
    assert rw.build_required_work(order, []) == ["Dry clean 3 Trousers"]
