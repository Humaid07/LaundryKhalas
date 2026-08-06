"""Controlled durable-memory operations (spec §28).

``save_confirmed_customer_memory`` / ``invalidate_customer_memory`` are the ONLY
write paths — Claude never writes SQL or mutates memory directly. Validation +
PATCH decisions come from the pure services/customer_memory_store.py; persistence
from db/repositories/customer_memory_repo.py. A null/unconfirmed value is rejected;
a correction supersedes the old row and records history.
"""
from __future__ import annotations

from db.repositories import customer_memory_repo as repo
from services import customer_memory_store as policy


async def save_confirmed_customer_memory(
    customer_id: str,
    *,
    memory_type: str,
    memory_key: str,
    memory_value,
    scope: str = policy.CUSTOMER_GLOBAL,
    customer_confirmed: bool = True,
    confidence=None,
    source_message_id: str | None = None,
    source_order_id: str | None = None,
) -> dict:
    """Validate + apply a durable customer-memory write. Returns
    ``{action, reason, memory?}``."""
    existing = await repo.list_active(customer_id)
    plan = policy.plan_memory_write(
        existing, memory_key=memory_key, memory_value=memory_value,
        scope=scope, customer_confirmed=customer_confirmed)
    if plan["action"] in ("reject", "noop"):
        return {"action": plan["action"], "reason": plan["reason"], "memory": None}

    old_value = None
    if plan["action"] == "supersede":
        prior = next((m for m in existing if str(m.get("id")) == plan.get("supersede_id")), None)
        old_value = (prior or {}).get("memory_value")
        await repo.mark_superseded(plan["supersede_id"])
        await repo.add_history(
            customer_id=customer_id, memory_id=plan["supersede_id"], memory_key=memory_key,
            old_value=old_value, new_value=str(memory_value), reason="correction")

    saved = await repo.insert(
        customer_id=customer_id, memory_type=memory_type, memory_key=memory_key,
        memory_value=str(memory_value), scope=scope, confidence=confidence,
        customer_confirmed=customer_confirmed, source_message_id=source_message_id,
        source_order_id=source_order_id)
    if saved is None:  # lost a race on the active-unique index
        return {"action": "noop", "reason": "conflict", "memory": None}
    return {"action": "updated" if plan["action"] == "supersede" else "created",
            "reason": plan["reason"], "memory": saved}


async def invalidate_customer_memory(customer_id: str, memory_key: str, *,
                                     scope: str = policy.CUSTOMER_GLOBAL, reason: str = "invalidated") -> dict:
    existing = await repo.list_active(customer_id)
    prior = next((m for m in existing
                  if str(m.get("memory_key")) == memory_key and str(m.get("scope")) == scope), None)
    await repo.invalidate(customer_id, memory_key, scope)
    if prior:
        await repo.add_history(
            customer_id=customer_id, memory_id=str(prior.get("id")), memory_key=memory_key,
            old_value=prior.get("memory_value"), new_value=None, reason=reason)
    return {"action": "invalidated", "memory_key": memory_key, "scope": scope}
