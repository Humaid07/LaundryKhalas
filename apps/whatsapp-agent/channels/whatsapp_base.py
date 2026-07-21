"""Common interface every WhatsApp channel implements. Mirrors the pattern
already used in the main backend's app/channels/base.py.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SendResult:
    message_id: str
    status: str  # "mock_sent" | "sent" | "failed"


class WhatsAppChannel(ABC):
    name: str

    @abstractmethod
    async def send_text(self, *, to_phone: str, text: str) -> SendResult: ...
