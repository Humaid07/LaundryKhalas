"""Channel adapter interface.

Every WhatsApp-like channel (mock now, Meta Cloud API later) implements this
interface so calling code (approvals, agent, admin) never needs to know
whether a message actually left the building or was only stored.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class InboundResult:
    conversation_id: str
    message_id: str
    customer_id: str


@dataclass
class OutboundResult:
    message_id: str
    status: str


class WhatsAppChannel(ABC):
    @abstractmethod
    async def receive_inbound(
        self,
        db: AsyncSession,
        *,
        market_code: str,
        phone_number: str,
        customer_name: str | None,
        message: str,
    ) -> InboundResult:
        ...

    @abstractmethod
    async def send_outbound(
        self, db: AsyncSession, *, conversation_id: str, message: str
    ) -> OutboundResult:
        ...
