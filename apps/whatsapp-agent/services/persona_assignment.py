"""Persistent per-customer WhatsApp AI-agent persona assignment (founder spec).

ONE approved persona name (Sara/Maya/Zoya/Hanna/Sofia/Max/Ben — configured via
``AGENT_PERSONA_NAMES``) is pinned to a customer for life:

  * chosen ONCE on the customer's first contact, by a deterministic/balanced backend
    strategy — here **deterministic customer hashing**, which is inherently
    concurrency-safe (the same customer key always maps to the same persona, so two
    simultaneous first messages can never pick two different names) and evenly
    distributes customers across the list;
  * PERSISTED on the customer record, so it never changes on a new order/conversation
    or after a backend/worker restart or deployment;
  * NEVER rotated between messages, and Claude may never invent a name off the list.

Only the DISPLAYED name differs between personas — all behaviour, rules, tools,
pricing/discount/booking/escalation logic are identical. AI personas are separate
from human Operations staff (who use their real names during a human takeover).

Pure selection here; persistence is delegated to an injected repo (production:
db.repositories.customers_repo; tests: a fake) so this stays unit-testable offline.
"""
from __future__ import annotations

import hashlib

from settings import get_settings


def _names() -> list[str]:
    raw = get_settings().agent_persona_names or ""
    seen: list[str] = []
    for part in raw.split(","):
        name = part.strip()
        if name and name not in seen:
            seen.append(name)
    return seen


def approved_personas() -> list[dict]:
    """The approved personas as ``[{id, name}]`` (id = lowercased name)."""
    return [{"id": n.lower(), "name": n} for n in _names()]


def assignment_mode() -> str:
    return get_settings().agent_persona_assignment_mode


def assignment_version() -> int:
    return int(get_settings().agent_persona_assignment_version)


def is_approved(name_or_id: str | None) -> bool:
    if not name_or_id:
        return False
    key = str(name_or_id).strip().lower()
    return any(p["id"] == key for p in approved_personas())


def select_for_key(key: str) -> dict:
    """Deterministically pick an approved persona for a stable customer key. Same key
    → same persona (restart-safe + concurrency-safe); a uniform hash spreads customers
    evenly across the list (balanced)."""
    personas = approved_personas()
    if not personas:
        raise ValueError("No approved personas configured (AGENT_PERSONA_NAMES is empty).")
    digest = hashlib.sha256(str(key).encode("utf-8")).hexdigest()
    return personas[int(digest, 16) % len(personas)]


def persona_from_customer(customer: dict | None) -> dict | None:
    """The persona already persisted on a customer record, or None. A persisted name
    that is no longer on the approved list is ignored (treated as unassigned) so a
    removed/renamed persona is never used."""
    if not customer:
        return None
    pid = customer.get("assigned_ai_persona_id")
    name = customer.get("assigned_ai_persona_name")
    if pid and name and is_approved(pid):
        return {"id": pid, "name": name}
    return None


def assistant_identity(persona: dict | None) -> dict:
    """The structured ``assistant_identity`` block injected into the model context
    before every Anthropic request. Empty display_name when no persona is resolved
    (the model then uses no personal name rather than inventing one)."""
    p = persona or {}
    return {
        "assistant_identity": {
            "persona_id": p.get("id"),
            "display_name": p.get("name"),
            "organization": "Laundry Khalaas",
            "persona_type": "VIRTUAL_ASSISTANT",
        }
    }


def _key_for(customer: dict) -> str:
    return str(customer.get("id") or customer.get("phone_hash")
               or customer.get("phone_e164") or "")


async def ensure_assigned(customer: dict, repo) -> dict:
    """Return the customer's persona, assigning + PERSISTING one on first contact.

    Idempotent and concurrency-safe: an already-assigned persona is returned
    unchanged; otherwise a deterministic pick is persisted via ``repo`` with a
    conditional write (assign only when still unassigned), and the persisted value —
    whoever won a race — is mirrored back onto the ``customer`` dict. Because the pick
    is deterministic by customer key, concurrent first messages pick the SAME name, so
    a race can never yield two different personas for one customer.
    """
    existing = persona_from_customer(customer)
    if existing:
        return existing
    persona = select_for_key(_key_for(customer))
    saved = await repo.assign_ai_persona(
        customer.get("id"), persona["id"], persona["name"], assignment_version())
    pid = (saved or {}).get("assigned_ai_persona_id") or persona["id"]
    name = (saved or {}).get("assigned_ai_persona_name") or persona["name"]
    customer["assigned_ai_persona_id"] = pid
    customer["assigned_ai_persona_name"] = name
    customer["ai_persona_assigned_at"] = (saved or {}).get("ai_persona_assigned_at")
    return {"id": pid, "name": name}
