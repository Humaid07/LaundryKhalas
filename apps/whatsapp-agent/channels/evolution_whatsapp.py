"""Evolution API WhatsApp channel — the CURRENT self-hosted provider.

Selected only when settings.evolution_live_ready is True (WHATSAPP_MODE=evolution
AND all EVOLUTION_* config present). Talks to the Evolution REST API over HTTP:

  send:    POST {base}/message/sendText/{instance}   header  apikey: <key>
  status:  GET  {base}/instance/connectionState/{instance}

Inbound arrives via Evolution's webhook (a `messages.upsert` event POSTed to
/webhooks/evolution) and is flattened by ``parse_evolution_webhook``. This is the
official Evolution gateway — no browser/WhatsApp-Web scraping.
"""
from __future__ import annotations

import re
import uuid

import httpx

from channels.whatsapp_base import SendResult, WhatsAppChannel
from settings import get_settings


def _to_number(phone: str) -> str:
    """Evolution accepts a bare number (digits only) or a full JID. Strip any
    formatting; if a JID (contains '@') was passed, keep it verbatim."""
    if "@" in (phone or ""):
        return phone
    return re.sub(r"[^\d]", "", phone or "")


def _send_result(data) -> SendResult:
    message_id = ""
    if isinstance(data, dict):
        message_id = (data.get("key") or {}).get("id", "") or data.get("id", "")
    return SendResult(message_id=message_id or str(uuid.uuid4()), status="sent")


class EvolutionWhatsAppChannel(WhatsAppChannel):
    name = "evolution"

    def __init__(self, base_url: str, api_key: str, instance: str) -> None:
        self._base_url = (base_url or "").rstrip("/")
        self._api_key = api_key
        self._instance = instance

    @classmethod
    def from_settings(cls) -> "EvolutionWhatsAppChannel":
        s = get_settings()
        return cls(s.evolution_api_base_url, s.evolution_api_key, s.evolution_instance_name)

    async def send_text(self, *, to_phone: str, text: str) -> SendResult:
        url = f"{self._base_url}/message/sendText/{self._instance}"
        payload = {"number": _to_number(to_phone), "text": text}
        headers = {"apikey": self._api_key, "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json() if response.content else {}

        message_id = ""
        if isinstance(data, dict):
            message_id = (data.get("key") or {}).get("id", "") or data.get("id", "")
        return SendResult(message_id=message_id or str(uuid.uuid4()), status="sent")

    async def _post(self, path: str, payload: dict) -> dict:
        url = f"{self._base_url}/{path}/{self._instance}"
        headers = {"apikey": self._api_key, "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json() if response.content else {}

    async def send_list(
        self,
        *,
        to_phone: str,
        body: str,
        button_text: str,
        rows: list[dict],
        section_title: str = "Options",
        header: str = "",
        footer: str = "",
    ) -> SendResult:
        """Send a WhatsApp interactive LIST (Evolution v2 /message/sendList).
        ``rows`` = [{"id","title","description"}]. Raises on failure so the caller
        can fall back to a numbered-text message."""
        payload = {
            "number": _to_number(to_phone),
            "title": header or "",
            "description": body,
            "buttonText": button_text,
            "footerText": footer or "",
            "sections": [{
                "title": section_title,
                "rows": [
                    # Evolution v2.3.x REJECTS a row with an empty description
                    # (400 "The description cannot be empty"), so always send a
                    # non-empty one — fall back to the title when none is given.
                    {"title": r["title"],
                     "description": (r.get("description") or "").strip() or r["title"],
                     "rowId": r["id"]}
                    for r in rows
                ],
            }],
        }
        data = await self._post("message/sendList", payload)
        return _send_result(data)

    async def send_buttons(
        self,
        *,
        to_phone: str,
        body: str,
        buttons: list[dict],
        header: str = "",
        footer: str = "",
    ) -> SendResult:
        """Send WhatsApp interactive reply BUTTONS (Evolution v2 /message/sendButtons).
        ``buttons`` = [{"id","title"}]. Raises on failure so the caller can fall
        back to a numbered-text message."""
        payload = {
            "number": _to_number(to_phone),
            "title": header or "",
            "description": body,
            "footer": footer or "",
            "buttons": [
                {"type": "reply", "displayText": b["title"], "id": b["id"]}
                for b in buttons
            ],
        }
        data = await self._post("message/sendButtons", payload)
        return _send_result(data)

    async def instance_status(self) -> dict:
        """Read-only connection state of the instance (open/close/connecting)."""
        url = f"{self._base_url}/instance/connectionState/{self._instance}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers={"apikey": self._api_key})
            response.raise_for_status()
            return response.json()


def _extract_text(message: dict) -> str:
    """Pull the human text out of the several shapes Evolution/Baileys uses for a
    message (plain conversation, extended text, or an image/video/doc caption)."""
    if not isinstance(message, dict):
        return ""
    if isinstance(message.get("conversation"), str):
        return message["conversation"]
    ext = message.get("extendedTextMessage")
    if isinstance(ext, dict) and isinstance(ext.get("text"), str):
        return ext["text"]
    for key in ("imageMessage", "videoMessage", "documentMessage"):
        sub = message.get(key)
        if isinstance(sub, dict) and isinstance(sub.get("caption"), str):
            return sub["caption"]
    return ""


def _extract_interactive(message: dict) -> tuple[str | None, str]:
    """Return (selection_id, display_text) for an interactive LIST or BUTTON reply.

    Handles the Baileys/Evolution shapes:
      * listResponseMessage -> singleSelectReply.selectedRowId (+ title)
      * buttonsResponseMessage -> selectedButtonId (+ selectedDisplayText)
      * templateButtonReplyMessage -> selectedId (+ selectedDisplayText)
    Returns (None, "") when the message is not an interactive reply.
    """
    if not isinstance(message, dict):
        return None, ""
    lst = message.get("listResponseMessage")
    if isinstance(lst, dict):
        row_id = (lst.get("singleSelectReply") or {}).get("selectedRowId")
        if row_id:
            return row_id, lst.get("title") or ""
    btn = message.get("buttonsResponseMessage")
    if isinstance(btn, dict) and btn.get("selectedButtonId"):
        return btn["selectedButtonId"], btn.get("selectedDisplayText") or ""
    tpl = message.get("templateButtonReplyMessage")
    if isinstance(tpl, dict) and tpl.get("selectedId"):
        return tpl["selectedId"], tpl.get("selectedDisplayText") or ""
    return None, ""


def _extract_location(message: dict) -> tuple[float | None, float | None]:
    if not isinstance(message, dict):
        return None, None
    loc = message.get("locationMessage")
    if isinstance(loc, dict):
        lat, lng = loc.get("degreesLatitude"), loc.get("degreesLongitude")
        if lat is not None and lng is not None:
            return float(lat), float(lng)
    return None, None


def parse_evolution_webhook(payload: dict) -> list[dict]:
    """Flatten an Evolution webhook payload into inbound customer messages
    ``[{phone, text, name, wa_message_id}]``.

    Only inbound (fromMe=False) TEXT messages from 1:1 chats are returned;
    fromMe echoes, group/status messages, and non-text/ack events are ignored.
    Evolution posts one event per request:
        {"event": "messages.upsert", "instance": "...", "data": {...}}
    where ``data`` is a single message dict or ``{"messages": [...]}``.
    """
    event = (payload.get("event") or "").lower().replace("_", ".")
    if event and event != "messages.upsert":
        return []

    data = payload.get("data") or {}
    raw = data.get("messages") if isinstance(data.get("messages"), list) else [data]

    results: list[dict] = []
    for msg in raw:
        if not isinstance(msg, dict):
            continue
        key = msg.get("key") or {}
        if key.get("fromMe"):
            continue
        remote_jid = key.get("remoteJid") or ""
        if remote_jid.endswith("@g.us") or remote_jid == "status@broadcast":
            continue
        message = msg.get("message") or {}
        text = _extract_text(message)
        selection_id, sel_text = _extract_interactive(message)
        latitude, longitude = _extract_location(message)
        # An interactive reply's display text is the human-visible message; a bare
        # location has no text. Keep any message that carries text, a selection, or
        # a location — only ack/receipt events with none of these are dropped.
        display = text or sel_text
        if not display and selection_id is None and latitude is None:
            continue
        phone = remote_jid.split("@", 1)[0] if "@" in remote_jid else remote_jid
        if not phone:
            continue
        results.append(
            {
                "phone": phone,
                "text": display,
                "name": msg.get("pushName") or "",
                "wa_message_id": key.get("id", ""),
                "selection_id": selection_id,
                "latitude": latitude,
                "longitude": longitude,
            }
        )
    return results
