"""Phase 2: the turn finalizer composes the CTA guard + segmentation, and the
webhook wiring imports cleanly."""
from services.reply_segmentation import finalize_reply


def test_finalize_single_message_no_history():
    assert finalize_reply("Clean and Press for 5 shirts is AED 45.", []) == [
        "Clean and Press for 5 shirts is AED 45."
    ]


def test_finalize_splits_into_ordered_segments():
    txt = ("Yes, we clean suede shoes. Prices start from AED 50.\n---\n"
           "Send a photo for a better estimate.")
    out = finalize_reply(txt, [])
    assert len(out) == 2
    assert out[0].startswith("Yes, we clean suede")
    assert out[1].startswith("Send a photo")


def test_finalize_strips_repeated_cta_when_recent_cta_used():
    recent = ["24 hours turnaround. Would you like to book?"]  # a recent CTA
    txt = "Yes, we collect from Dubai Marina. Would you like me to book a pickup?"
    assert finalize_reply(txt, recent) == ["Yes, we collect from Dubai Marina."]


def test_finalize_keeps_cta_when_no_recent_cta():
    txt = "Yes, we collect from Dubai Marina. Would you like me to book a pickup?"
    # no recent CTA -> guard does not trigger; segmentation keeps it as one message
    assert finalize_reply(txt, []) == [txt]


def test_finalize_never_strips_operational_question():
    recent = ["Would you like to book?"]
    txt = "The final price is AED 140. Shall I proceed with the work?"
    assert finalize_reply(txt, recent) == [txt]


def test_webhook_module_imports_finalizer():
    # Guards the wiring: the webhook references reply_segmentation.finalize_reply.
    import api.evolution_webhooks as wh
    assert hasattr(wh.reply_segmentation, "finalize_reply")


def test_tone_avoid_list_has_cta_and_filler_guidance():
    import rules
    avoid = " ".join(rules.tone_rules()["avoid"]).lower()
    assert "cta" in avoid
    assert "filler" in avoid


def test_general_prompt_injects_tone_avoidance():
    from agents.whatsapp_agent.prompts import build_system_prompt
    prompt = build_system_prompt().lower()
    assert "filler" in prompt or "unnecessary booking ctas" in prompt
