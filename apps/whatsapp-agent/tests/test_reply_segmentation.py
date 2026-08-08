"""Phase 2: split a model reply into 1-3 validated WhatsApp messages (spec §3/§20)."""
from services.reply_segmentation import segment_reply


def test_no_delimiter_returns_single():
    assert segment_reply("Clean and Press for 5 shirts is AED 45.") == [
        "Clean and Press for 5 shirts is AED 45."
    ]


def test_empty_returns_empty_list():
    assert segment_reply("") == []
    assert segment_reply("   ") == []


def test_two_segments():
    txt = ("Yes, we clean suede shoes. Prices start from AED 50.\n---\n"
           "Send a photo for a better estimate, or we can collect and confirm after inspection.")
    out = segment_reply(txt)
    assert len(out) == 2
    assert out[0].startswith("Yes, we clean suede")
    assert out[1].startswith("Send a photo")


def test_caps_at_three_merging_overflow():
    txt = "Aye one.\n---\nBee two.\n---\nCee three.\n---\nDee four."
    out = segment_reply(txt)
    assert len(out) == 3
    assert out[2].endswith("Dee four.")  # 4th merged into 3rd


def test_drops_empty_and_one_word_fragments():
    txt = "Yes, we collect from Dubai Marina.\n---\n \n---\nok"
    assert segment_reply(txt) == ["Yes, we collect from Dubai Marina."]


def test_merges_mid_sentence_split():
    txt = "Prices start from AED 50 depending\n---\non the condition of the shoes."
    assert segment_reply(txt) == ["Prices start from AED 50 depending on the condition of the shoes."]


def test_dedup_adjacent_identical():
    txt = "Yes, we collect from Marina.\n---\nYes, we collect from Marina."
    assert segment_reply(txt) == ["Yes, we collect from Marina."]


def test_custom_max_segments():
    txt = "One sentence here.\n---\nTwo sentence here.\n---\nThree sentence here."
    assert len(segment_reply(txt, max_segments=2)) == 2
