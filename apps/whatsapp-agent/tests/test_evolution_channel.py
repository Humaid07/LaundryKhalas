"""Evolution channel: inbound webhook parsing + outbound send (mocked HTTP).

No real Evolution server is contacted — send_text is exercised against a fake
httpx client, and the inbound webhook endpoint is checked for its graceful
SQLite-mode behaviour (the inbox is a Supabase feature).
"""
import channels.evolution_whatsapp as evo
from channels.evolution_whatsapp import parse_evolution_webhook


def _upsert(text=None, from_me=False, jid="919372522055@s.whatsapp.net", name="Humaid", message=None):
    return {
        "event": "messages.upsert",
        "instance": "whatsapp-agent",
        "data": {
            "key": {"remoteJid": jid, "fromMe": from_me, "id": "3EB0ABC123"},
            "pushName": name,
            "message": message if message is not None else {"conversation": text},
        },
    }


# ------------------------------ parsing ------------------------------------
def test_parse_plain_text():
    out = parse_evolution_webhook(_upsert("I need a laundry pickup"))
    # The parser returns a uniform shape; interactive/location fields are None
    # for a plain text message.
    assert out == [
        {
            "phone": "919372522055",
            "text": "I need a laundry pickup",
            "name": "Humaid",
            "wa_message_id": "3EB0ABC123",
            "selection_id": None,
            "latitude": None,
            "longitude": None,
            "media_kind": "text",
            "location_event": None,
        }
    ]


def test_parse_extended_text():
    out = parse_evolution_webhook(_upsert(message={"extendedTextMessage": {"text": "hello there"}}))
    assert out[0]["text"] == "hello there"


def test_parse_image_caption():
    out = parse_evolution_webhook(_upsert(message={"imageMessage": {"caption": "this shirt is damaged"}}))
    assert out[0]["text"] == "this shirt is damaged"


def test_parse_ignores_from_me():
    assert parse_evolution_webhook(_upsert("echo", from_me=True)) == []


def test_parse_ignores_groups_and_status():
    assert parse_evolution_webhook(_upsert("hi", jid="12345@g.us")) == []
    assert parse_evolution_webhook(_upsert("hi", jid="status@broadcast")) == []


def test_parse_ignores_non_text_and_other_events():
    assert parse_evolution_webhook(_upsert(message={"reactionMessage": {}})) == []
    assert parse_evolution_webhook({"event": "messages.update", "data": {}}) == []


def test_parse_lid_addressing_resolves_real_number():
    """LID addressing: remoteJid is an opaque @lid id, the real phone-number JID
    is in remoteJidAlt. The parser must return the REAL number so allow-list
    matching, customer identity and the reply target are correct (the bug that
    made the agent stop replying)."""
    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {
                "remoteJid": "58239773319181@lid",
                "remoteJidAlt": "971543216640@s.whatsapp.net",
                "addressingMode": "lid",
                "fromMe": False,
                "id": "LID1",
            },
            "pushName": "Test",
            "message": {"conversation": "I need a laundry pickup"},
        },
    }
    out = parse_evolution_webhook(payload)
    assert out[0]["phone"] == "971543216640"


def test_parse_lid_without_alt_falls_back_to_lid_digits():
    """No remoteJidAlt available → still store the message (never silently drop),
    using the LID digits as a last resort."""
    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {"remoteJid": "58239773319181@lid", "fromMe": False, "id": "LID2"},
            "message": {"conversation": "hi"},
        },
    }
    out = parse_evolution_webhook(payload)
    assert out[0]["phone"] == "58239773319181"


def test_parse_strips_device_suffix():
    out = parse_evolution_webhook(_upsert("hi", jid="971543216640:12@s.whatsapp.net"))
    assert out[0]["phone"] == "971543216640"


def test_parse_lid_group_still_ignored():
    """A group stays ignored even under LID addressing (remoteJid is still @g.us)."""
    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {
                "remoteJid": "919372522055-1571388479@g.us",
                "participant": "270166378168570@lid",
                "participantAlt": "918828367593@s.whatsapp.net",
                "addressingMode": "lid",
                "fromMe": False,
                "id": "LID3",
            },
            "message": {"conversation": "group msg"},
        },
    }
    assert parse_evolution_webhook(payload) == []


def test_parse_handles_messages_list():
    payload = {"event": "messages.upsert", "data": {"messages": [
        {"key": {"remoteJid": "111@s.whatsapp.net", "fromMe": False, "id": "a"}, "message": {"conversation": "one"}},
        {"key": {"remoteJid": "222@s.whatsapp.net", "fromMe": True, "id": "b"}, "message": {"conversation": "mine"}},
    ]}}
    out = parse_evolution_webhook(payload)
    assert [m["text"] for m in out] == ["one"]


# ------------------------------- send --------------------------------------
class _FakeResp:
    content = b"{}"

    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class _FakeClient:
    last = {}

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, json, headers):
        _FakeClient.last = {"url": url, "json": json, "headers": headers}
        return _FakeResp({"key": {"id": "evo-msg-1"}})


async def test_send_text_hits_evolution_rest(monkeypatch):
    monkeypatch.setattr(evo.httpx, "AsyncClient", _FakeClient)
    channel = evo.EvolutionWhatsAppChannel("http://localhost:8080/", "APIKEY", "whatsapp-agent")
    result = await channel.send_text(to_phone="+971 50 220 4471", text="Hi there")

    assert _FakeClient.last["url"] == "http://localhost:8080/message/sendText/whatsapp-agent"
    assert _FakeClient.last["headers"]["apikey"] == "APIKEY"
    assert _FakeClient.last["json"] == {"number": "97150220 4471".replace(" ", ""), "text": "Hi there"}
    assert result.status == "sent"
    assert result.message_id == "evo-msg-1"


# ----------------------- webhook endpoint (sqlite mode) --------------------
async def test_evolution_webhook_graceful_in_sqlite(client):
    resp = await client.post("/webhooks/evolution", json=_upsert("I need laundry pickup today"))
    assert resp.status_code == 200
    body = resp.json()
    # sqlite (test) mode: acknowledged, not stored (inbox is a Supabase feature)
    assert body["status"] == "ok"
    assert body["stored"] is False


async def test_evolution_webhook_ignores_non_message(client):
    resp = await client.post("/webhooks/evolution", json={"event": "messages.update", "data": {}})
    assert resp.status_code == 200
    assert resp.json()["processed"] == 0
