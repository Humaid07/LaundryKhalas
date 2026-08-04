"""Deterministic synthetic identities for conversation isolation.

Every replayed conversation gets its own non-routable synthetic customer so the
real agent pipeline (which keys customers/conversations by phone) keeps each
chat's state fully separate. The synthetic phone is in an UNASSIGNED country
code (+999...) so it can never route anywhere, and the capture-only transport
blocks sending regardless.

For CUSTOMER_HISTORY mode, all chats that share the SAME hashed real customer
map to the SAME synthetic phone, so returning-customer memory is exercised; the
chats are then replayed oldest-first.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..core.models import Conversation

# Unassigned country code prefix — guarantees non-routability.
_SYNTHETIC_PREFIX = "999000"


@dataclass
class SyntheticIdentity:
    index: int
    customer_id_label: str      # replay_customer_000001 (human label)
    phone: str                  # +999000000001 (E.164-shaped, non-routable)
    name: str                   # Replay Customer 1
    customer_hash: str          # one-way hash of the ORIGINAL number (matching only)

    @property
    def context_key(self) -> str:
        return self.customer_id_label


def synthetic_phone(index: int) -> str:
    return "+" + _SYNTHETIC_PREFIX + f"{index:06d}"


def build_identity(index: int, customer_hash: str) -> SyntheticIdentity:
    return SyntheticIdentity(
        index=index,
        customer_id_label=f"replay_customer_{index:06d}",
        phone=synthetic_phone(index),
        name=f"Replay Customer {index}",
        customer_hash=customer_hash,
    )


def assign_identities(
    conversations: list[Conversation],
    *,
    memory_mode: str = "CUSTOMER_HISTORY",
) -> dict[str, SyntheticIdentity]:
    """Map each conversation's source_chat_id -> SyntheticIdentity.

    ISOLATED_CHAT: one identity per chat.
    CUSTOMER_HISTORY: one identity per hashed customer (shared across their chats).
    """
    mapping: dict[str, SyntheticIdentity] = {}
    if memory_mode == "CUSTOMER_HISTORY":
        by_hash: dict[str, SyntheticIdentity] = {}
        next_index = 1
        for conv in conversations:
            ident = by_hash.get(conv.customer_identifier_hash)
            if ident is None:
                ident = build_identity(next_index, conv.customer_identifier_hash)
                by_hash[conv.customer_identifier_hash] = ident
                next_index += 1
            mapping[conv.source_chat_id] = ident
    else:  # ISOLATED_CHAT
        for i, conv in enumerate(conversations, start=1):
            mapping[conv.source_chat_id] = build_identity(i, conv.customer_identifier_hash)
    return mapping


def order_for_replay(
    conversations: list[Conversation],
    *,
    memory_mode: str = "CUSTOMER_HISTORY",
) -> list[Conversation]:
    """Order conversations for replay.

    CUSTOMER_HISTORY: group a customer's chats together, oldest-first, so saved
    details from an earlier chat are available in a later one.
    """
    if memory_mode != "CUSTOMER_HISTORY":
        return list(conversations)

    def sort_key(c: Conversation):
        first = c.first_inbound_at
        # (customer, chronological within customer)
        return (c.customer_identifier_hash, first.isoformat() if first else "")

    return sorted(conversations, key=sort_key)


def all_synthetic_numbers(identities: Iterable[SyntheticIdentity]) -> list[str]:
    seen = []
    out = []
    for ident in identities:
        if ident.phone not in seen:
            seen.append(ident.phone)
            out.append(ident.phone)
    return out
