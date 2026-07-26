"""Webhook delivery safety: the customer confirmation shows only the FINAL price
(no VAT wording), and no reply path can ever send an empty WhatsApp message
(task spec §§2/23/29).
"""
import datetime as _dt

from api import evolution_webhooks as w
from services import booking_flow


def test_confirmation_text_shows_final_price_and_no_vat():
    row = {
        "order_id": "LK-2026-000123",
        "service_display_name": "Wash & Fold",
        "estimated_total": 63, "pricing_is_estimated": False,
        "pickup_date": _dt.date(2026, 7, 27), "pickup_slot": "4pm – 6pm",
        "pickup_address": "Dubai Marina", "pickup_instruction_text": None,
    }
    text = w._final_confirmation_text(row)
    assert "AED 63" in text
    for banned in ("VAT", "vat", "Tax", "tax", "excl", "incl", "Subtotal"):
        assert banned not in text


class _CaptureChannel:
    def __init__(self):
        self.sent = []

    async def send_text(self, *, to_phone, text):
        self.sent.append(text)


async def test_send_reply_never_sends_empty_text():
    ch = _CaptureChannel()
    reply = booking_flow.BookingReply(text="", state=booking_flow.WAITING_FOR_SERVICE)
    returned = await w._send_reply(ch, "+971500000000", reply)
    assert ch.sent and ch.sent[0].strip()            # something was sent
    assert returned == ch.sent[0] == w._AI_FALLBACK_TEXT


async def test_send_reply_passes_through_real_text():
    ch = _CaptureChannel()
    reply = booking_flow.BookingReply(text="Your pickup is booked!",
                                      state=booking_flow.POST_ORDER)
    returned = await w._send_reply(ch, "+971500000000", reply)
    assert returned == "Your pickup is booked!" and ch.sent == ["Your pickup is booked!"]
