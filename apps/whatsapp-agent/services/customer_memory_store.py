"""Durable customer-memory policy (pure).

Decides whether a proposed memory write is valid and how to apply it (PATCH
semantics): a null/empty extraction NEVER erases existing memory; an unconfirmed
LLM guess is never stored; a corrected value supersedes the old one while
preserving history; ORDER_ONLY memory can never influence another order. The
asyncpg persistence lives in db/repositories/customer_memory_repo.py.
"""

from __future__ import annotations

import re

CUSTOMER_GLOBAL = "CUSTOMER_GLOBAL"
ADDRESS_SPECIFIC = "ADDRESS_SPECIFIC"
SERVICE_SPECIFIC = "SERVICE_SPECIFIC"
ORDER_ONLY = "ORDER_ONLY"
MEMORY_SCOPES = (CUSTOMER_GLOBAL, ADDRESS_SPECIFIC, SERVICE_SPECIFIC, ORDER_ONLY)

_ALWAYS_RE = re.compile(r"\b(always|every time|from now on)\b", re.I)
_ORDER_ONLY_RE = re.compile(r"\b(for this order|this order only|just this order|this time)\b", re.I)


def _norm(v) -> str:
    return re.sub(r"\s+", " ", str(v or "").strip()).lower()


def resolve_scope(text: str | None, *, default: str = CUSTOMER_GLOBAL) -> str:
    """Promote/demote scope from explicit phrasing: 'always ...' → CUSTOMER_GLOBAL,
    'for this order' → ORDER_ONLY, else the caller's default."""
    t = text or ""
    if _ORDER_ONLY_RE.search(t):
        return ORDER_ONLY
    if _ALWAYS_RE.search(t):
        return CUSTOMER_GLOBAL
    return default if default in MEMORY_SCOPES else CUSTOMER_GLOBAL


def influences_other_orders(scope: str) -> bool:
    """ORDER_ONLY memory must never affect another order (spec §23)."""
    return scope != ORDER_ONLY


def plan_memory_write(
    existing_active: list[dict],
    *,
    memory_key: str,
    memory_value,
    scope: str = CUSTOMER_GLOBAL,
    customer_confirmed: bool = False,
) -> dict:
    """Decide how to apply a proposed durable-memory write.

    Returns ``{action, reason, supersede_id?}`` where action ∈
    {save, supersede, noop, reject}."""
    if memory_value is None or not str(memory_value).strip():
        return {"action": "reject", "reason": "null_never_erases"}
    if not customer_confirmed:
        # Never store an unconfirmed LLM guess as durable memory (spec §23).
        return {"action": "reject", "reason": "not_customer_confirmed"}
    if scope not in MEMORY_SCOPES:
        return {"action": "reject", "reason": "invalid_scope"}

    for m in existing_active:
        if str(m.get("status", "active")) != "active":
            continue
        if str(m.get("memory_key")) == str(memory_key) and str(m.get("scope")) == str(scope):
            if _norm(m.get("memory_value")) == _norm(memory_value):
                return {"action": "noop", "reason": "unchanged"}
            # Correction: supersede the old value, preserve it in history.
            return {"action": "supersede", "reason": "correction",
                    "supersede_id": str(m.get("id") or m.get("memory_id") or "")}
    return {"action": "save", "reason": "new"}


def active_for_scope(existing_active: list[dict], scope_filter: str | None = None) -> list[dict]:
    """Active memories, optionally filtered — and NEVER returning ORDER_ONLY rows
    when a global/other-order view is requested."""
    out = []
    for m in existing_active:
        if str(m.get("status", "active")) != "active":
            continue
        if scope_filter and str(m.get("scope")) != scope_filter:
            continue
        out.append(m)
    return out
