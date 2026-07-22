"""Interactive service-selection tests (spec: "Replace numbered service selection
with an interactive WhatsApp list").

Hermetic: the FSM + Evolution channel payload builder are exercised directly. The
channel's HTTP call is stubbed, so no network/DB is touched.
"""
import asyncio

from channels.evolution_whatsapp import EvolutionWhatsAppChannel
from rules import active_service_catalog
from services import booking_flow as bf
from services.booking_flow import Booking, Inbound

TODAY_SLOTS = [{"slot_id": "morning_08_11", "label": "8–11 AM",
                "start_time": __import__("datetime").time(8),
                "end_time": __import__("datetime").time(11)}]


async def _slots(*_a, **_k):
    return list(TODAY_SLOTS)


def _advance(b, inbound):
    import datetime as _dt
    return asyncio.run(bf.advance(b, inbound, today=_dt.date(2026, 7, 22), available_slots=_slots))


# 1 — active services are loaded from the DB catalogue, not hardcoded -----------
def test_service_options_come_from_active_catalogue():
    catalog_ids = [s.get("service_id", s.get("key")) for s in active_service_catalog()]
    opt_ids = [o.id.split(":", 1)[1] for o in bf._service_options()]
    assert opt_ids == catalog_ids
    assert len(opt_ids) >= 5


# 2 — the interactive LIST payload carries the correct service row ids ----------
def test_list_payload_has_service_ids_and_nonempty_descriptions():
    ch = EvolutionWhatsAppChannel("http://x", "k", "inst")
    captured = {}

    async def fake_post(path, payload):
        captured["path"] = path
        captured["payload"] = payload
        return {"key": {"id": "m1"}}

    ch._post = fake_post  # type: ignore[method-assign]
    rows = [{"id": o.id, "title": o.title, "description": o.description}
            for o in bf._service_options()]
    asyncio.run(ch.send_list(to_phone="+971500000000", body="Which service?",
                             button_text="Choose", rows=rows, section_title="Services"))
    assert captured["path"] == "message/sendList"
    sent_rows = captured["payload"]["sections"][0]["rows"]
    assert [r["rowId"] for r in sent_rows] == [o.id for o in bf._service_options()]
    # the empty-description fix: Evolution 2.3.x rejects empty row descriptions
    assert all(r["description"].strip() for r in sent_rows)


# 3 — a selected row id resolves to the correct service ------------------------
def test_selected_row_id_resolves_to_service():
    sid = active_service_catalog()[2]["service_id"]
    got, reason = bf.resolve_service(Inbound(selection_id=f"service:{sid}"))
    assert reason == "ok" and got == sid


# 4/5 — disabled/unknown row ids are rejected safely (never resolve) -----------
def test_unknown_or_disabled_service_id_rejected():
    got, reason = bf.resolve_service(Inbound(selection_id="service:not_a_real_or_disabled_service"))
    assert got is None and reason == "invalid"


# 6 — buttons are used when the option count is small (date step: 3 options) ----
def test_buttons_used_for_small_option_sets():
    assert bf._date_prompt("X").interactive.kind == "buttons"
    assert len(bf._date_prompt("X").interactive.options) == 3


# 7 — a list/dropdown is used when the count exceeds the button limit ----------
def test_list_used_for_service_catalogue():
    prompt = bf._service_prompt()
    assert prompt.interactive.kind == "list"
    assert len(prompt.interactive.options) >= 6


# 8 — text fallback renders every option and stays selectable by number --------
def test_numbered_fallback_lists_all_services():
    fallback = bf.numbered_fallback(bf._service_prompt().interactive)
    for o in bf._service_options():
        assert o.title in fallback
    assert "Reply with the number" in fallback


# 9 — selecting a service progresses the SAME booking (never restarts) ---------
def test_service_selection_progresses_without_restart():
    sid = active_service_catalog()[0]["service_id"]
    reply = _advance(Booking(conversation_state=bf.WAITING_FOR_SERVICE),
                     Inbound(selection_id=f"service:{sid}", text="Premium Wash & Fold"))
    assert reply.state == bf.WAITING_FOR_NAME                 # forward (name next), not back to start
    assert reply.updates["service_id"] == sid


# 10 — two numbers select different services with no shared state --------------
def test_two_numbers_select_different_services_independently():
    s0 = active_service_catalog()[0]["service_id"]
    s1 = active_service_catalog()[1]["service_id"]
    a = _advance(Booking(conversation_state=bf.WAITING_FOR_SERVICE),
                 Inbound(selection_id=f"service:{s0}"))
    b = _advance(Booking(conversation_state=bf.WAITING_FOR_SERVICE),
                 Inbound(selection_id=f"service:{s1}"))
    assert a.updates["service_id"] == s0
    assert b.updates["service_id"] == s1
    assert a.updates["service_id"] != b.updates["service_id"]
