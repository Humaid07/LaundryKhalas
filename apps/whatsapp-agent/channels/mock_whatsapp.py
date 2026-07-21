"""Local/mock WhatsApp channel - zero external calls, always available.
Used for the /chat test console and as the default in every environment
until WHATSAPP_MODE=live and Meta credentials are configured.
"""
import uuid

from channels.whatsapp_base import SendResult, WhatsAppChannel


class MockWhatsAppChannel(WhatsAppChannel):
    name = "mock"

    async def send_text(self, *, to_phone: str, text: str) -> SendResult:
        return SendResult(message_id=str(uuid.uuid4()), status="mock_sent")
