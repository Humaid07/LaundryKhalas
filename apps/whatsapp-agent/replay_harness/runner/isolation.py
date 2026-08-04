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

import hashlib
from dataclasses import dataclass
from typing import Iterable

from ..core.models import Conversation

# Unassigned country code prefix (999) — guarantees non-routability. A per-run
# 3-digit tag namespaces each run so leaked state from a prior run (e.g. a
# conversation left in human_takeover) can NEVER contaminate a new run: different
# run_id -> different phone range -> brand-new customers/conversations.
_SYNTHETIC_CC = "999"

# All synthetic numbers share this prefix so cleanup can match them.
SYNTHETIC_PREFIX = _SYNTHETIC_CC


@dataclass
class SyntheticIdentity:
    index: int
    customer_id_label: str      # replay_customer_000001 (human label)
    phone: str                  # +999<tag><index> (E.164-shaped, non-routable)
    name: str                   # Replay Customer 1
    customer_hash: str          # one-way hash of the ORIGINAL number (matching only)

    @property
    def context_key(self) -> str:
        return self.phone


def _run_tag(run_id: str) -> str:
    """Deterministic 3-digit namespace tag from the run id."""
    h = int(hashlib.sha256((run_id or "default").encode()).hexdigest(), 16)
    return f"{h % 1000:03d}"


def synthetic_phone(index: int, run_tag: str) -> str:
    # +999 <3-digit run tag> <5-digit index> = 11 digits (non-routable).
    return "+" + _SYNTHETIC_CC + run_tag + f"{index:05d}"


def build_identity(index: int, customer_hash: str, run_tag: str) -> SyntheticIdentity:
    return SyntheticIdentity(
        index=index,
        customer_id_label=f"replay_customer_{index:06d}",
        phone=synthetic_phone(index, run_tag),
        name=f"Replay Customer {index}",
        customer_hash=customer_hash,
    )


def assign_identities(
    conversations: list[Conversation],
    *,
    memory_mode: str = "ISOLATED_CHAT",
    run_id: str = "default",
) -> dict[str, SyntheticIdentity]:
    """Map each conversation's source_chat_id -> SyntheticIdentity.

    ISOLATED_CHAT (default): one identity per chat — each historical conversation
    is replayed independently, so a takeover/complaint in one chat can never hold
    another chat's turns.
    CUSTOMER_HISTORY: one identity per hashed customer (shared across their chats)
    to exercise returning-customer memory. Caveat: because the pipeline keys a
    conversation by phone, a takeover in an earlier chat will hold later chats for
    that same customer — use only when testing returning-customer behaviour.
    """
    run_tag = _run_tag(run_id)
    mapping: dict[str, SyntheticIdentity] = {}
    if memory_mode == "CUSTOMER_HISTORY":
        by_hash: dict[str, SyntheticIdentity] = {}
        next_index = 1
        for conv in conversations:
            ident = by_hash.get(conv.customer_identifier_hash)
            if ident is None:
                ident = build_identity(next_index, conv.customer_identifier_hash, run_tag)
                by_hash[conv.customer_identifier_hash] = ident
                next_index += 1
            mapping[conv.source_chat_id] = ident
    else:  # ISOLATED_CHAT
        for i, conv in enumerate(conversations, start=1):
            mapping[conv.source_chat_id] = build_identity(i, conv.customer_identifier_hash, run_tag)
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
