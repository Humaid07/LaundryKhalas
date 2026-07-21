"""Official Meta WhatsApp Cloud API channel. Only ever selected when
settings.meta_live_ready is True (WHATSAPP_MODE=meta AND all META_WHATSAPP_*
config present) - see api/webhooks.py and how the agent layer picks a channel.
No unofficial automation, no browser/WhatsApp-Web scraping - this talks to
graph.facebook.com only.
"""
import hashlib
import hmac

import httpx

from channels.whatsapp_base import SendResult, WhatsAppChannel

_GRAPH_API_VERSION = "v20.0"


class MetaWhatsAppChannel(WhatsAppChannel):
    name = "meta"

    def __init__(self, access_token: str, phone_number_id: str, app_secret: str = "") -> None:
        self._access_token = access_token
        self._phone_number_id = phone_number_id
        self._app_secret = app_secret

    async def send_text(self, *, to_phone: str, text: str) -> SendResult:
        url = (
            f"https://graph.facebook.com/{_GRAPH_API_VERSION}/"
            f"{self._phone_number_id}/messages"
        )
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "text",
            "text": {"body": text},
        }
        headers = {"Authorization": f"Bearer {self._access_token}"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        message_id = data.get("messages", [{}])[0].get("id", "")
        return SendResult(message_id=message_id, status="sent")

    def verify_webhook_signature(self, *, payload_body: bytes, signature_header: str) -> bool:
        """Validates X-Hub-Signature-256 against META_WHATSAPP_APP_SECRET."""
        if not self._app_secret or not signature_header:
            return False
        expected = "sha256=" + hmac.new(
            self._app_secret.encode(), payload_body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature_header)


def parse_inbound_webhook(payload: dict) -> list[dict]:
    """Extracts a flat list of {phone, text, wa_message_id} from a Meta
    webhook payload. Ignores status-callback entries (delivered/read), which
    have no 'messages' key.
    """
    results: list[dict] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []):
                if message.get("type") != "text":
                    continue
                results.append(
                    {
                        "phone": message.get("from", ""),
                        "text": message.get("text", {}).get("body", ""),
                        "wa_message_id": message.get("id", ""),
                    }
                )
    return results
