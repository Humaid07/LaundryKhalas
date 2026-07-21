"""Meta WhatsApp Cloud API adapter - STUB ONLY.

Not implemented in this task. Exists so config/routing code has a real
class to point at once live WhatsApp is approved (see
docs/checklists/live-whatsapp-readiness.md). Any attempt to use this raises
immediately - there is no live WhatsApp call path in this codebase.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.base import InboundResult, OutboundResult, WhatsAppChannel


class MetaWhatsAppStub(WhatsAppChannel):
    async def receive_inbound(
        self,
        db: AsyncSession,
        *,
        market_code: str,
        phone_number: str,
        customer_name: str | None,
        message: str,
    ) -> InboundResult:
        raise NotImplementedError(
            "Live Meta WhatsApp Cloud API integration is not implemented. "
            "See docs/checklists/live-whatsapp-readiness.md."
        )

    async def send_outbound(
        self, db: AsyncSession, *, conversation_id: str, message: str
    ) -> OutboundResult:
        raise NotImplementedError(
            "Live Meta WhatsApp Cloud API integration is not implemented. "
            "See docs/checklists/live-whatsapp-readiness.md."
        )
