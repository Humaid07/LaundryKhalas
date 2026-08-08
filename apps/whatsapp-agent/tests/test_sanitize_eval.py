"""PII sanitiser + evaluation-dataset format/validation tests."""
from services import eval_dataset, sanitize


# --------------------------- sanitiser -----------------------------------
def test_masks_phone_email_url_order_id():
    s = sanitize.sanitize_text(
        "Call +971 50 123 4567 or email me at sara@example.com, order LK-AE-1024, "
        "photo https://cdn.example.com/x.jpg")
    assert "[PHONE]" in s and "[EMAIL]" in s and "[ORDER_ID]" in s and "[URL]" in s
    assert "971" not in s and "sara@example.com" not in s
    assert "LK-AE-1024" not in s and "cdn.example.com" not in s


def test_masks_address_and_long_digits_and_key():
    s = sanitize.sanitize_text("Villa 12, Street 4 Dubai Marina; acct 12345678; key sk-ant-abcdef123456")
    assert "[ADDRESS]" in s
    assert "[NUMBER]" in s or "[ADDRESS]" in s
    assert "[REDACTED_KEY]" in s and "sk-ant-abcdef123456" not in s


def test_names_masked_only_when_requested():
    assert "Sara" in sanitize.sanitize_text("Hi I'm Sara")
    assert "[NAME]" in sanitize.sanitize_text("Hi I'm Sara", mask_names=True, names=["Sara"])


# ------------------- conversational name scrubbing -----------------------
def test_scrub_masks_intro_names():
    for phrase, name in [
        ("Hi I'm Ahmed", "Ahmed"),
        ("Hello, this is Sara here", "Sara"),
        ("my name is Mohammed Ali", "Mohammed"),
        ("call me Fatima", "Fatima"),
        ("i am Rajesh", "Rajesh"),
    ]:
        out = sanitize.scrub_conversational_names(phrase)
        assert "[NAME]" in out, phrase
        assert name not in out, phrase


def test_scrub_keeps_intro_phrase_and_non_names():
    # The lead phrase survives; only the name is masked.
    assert sanitize.scrub_conversational_names("this is Sara") == "this is [NAME]"
    # Common words after an intro phrase are NOT masked.
    for benign in ["I'm fine", "this is Ok", "I am Ready", "I'm Here", "this is Good"]:
        assert "[NAME]" not in sanitize.scrub_conversational_names(benign), benign


def test_scrub_no_intro_phrase_leaves_text_untouched():
    # No blanket masking of capitalised words without an intro phrase.
    text = "Please collect the Kandoora from Dubai Marina tomorrow"
    assert sanitize.scrub_conversational_names(text) == text


def test_scrub_handles_empty():
    assert sanitize.scrub_conversational_names("") == ""
    assert sanitize.scrub_conversational_names(None) == ""


def test_sanitize_record_drops_pii_fields_and_scrubs_text():
    rec = {"intent": "book", "text": "call +971501234567 for pickup",
           "phone": "+971501234567", "pickup_address": "Villa 3", "quantity": 4}
    out = sanitize.sanitize_record(rec)
    assert "phone" not in out and "pickup_address" not in out
    assert out["quantity"] == 4
    assert "[PHONE]" in out["text"]


# --------------------------- eval dataset --------------------------------
def test_seed_dataset_loads_and_validates():
    records = eval_dataset.load_dataset()
    assert len(records) >= 10
    for r in records:
        errors = eval_dataset.validate_record(r)
        assert errors == [], f"{r.get('id')}: {errors}"


def test_seed_dataset_has_no_pii_keys():
    for r in eval_dataset.load_dataset():
        assert eval_dataset._FORBIDDEN_KEYS.isdisjoint(r.keys())


def test_seed_dataset_covers_key_groups():
    groups = eval_dataset.dataset_groups()
    for required in ("fragmented_messages", "price_enquiry_converted", "discount_request",
                     "bespoke_service", "complaint", "b2b_lead", "prompt_injection",
                     "duplicate_message", "order_edit", "repeat_customer"):
        assert required in groups, f"missing eval group: {required}"


def test_to_eval_record_sanitises():
    rec = eval_dataset.to_eval_record(
        id="x1", group="complaint", intent="complaint",
        message_fragments=["my shirt is damaged, call +971509999999"],
        expected_extracted_fields={"category": "damage"},
        expected_tool_calls=["create_complaint"],
        expected_response="Sorry — please share order LK-AE-2048 and a photo.",
        forbidden_response_behaviour=["promise refund"],
        funnel_stage="COMPLAINT_OPEN", service_category="CLEAN_PRESS",
        country="AE", outcome="logged")
    assert "[PHONE]" in rec["combined_turn"] and "+971509999999" not in rec["combined_turn"]
    assert "[ORDER_ID]" in rec["expected_response"]
    assert eval_dataset.validate_record(rec) == []


def test_validate_flags_missing_keys_and_pii():
    bad = {"id": "b", "group": "complaint", "phone": "+9715"}
    errors = eval_dataset.validate_record(bad)
    assert any("missing keys" in e for e in errors)
    assert any("PII keys present" in e for e in errors)
