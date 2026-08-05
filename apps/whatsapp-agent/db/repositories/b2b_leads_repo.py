"""B2B lead records (Supabase dev/test schema).

A B2B enquiry gets its own lead entity routed to the commercial team — kept out
of the consumer order funnel and consumer conversion metrics. ``create`` inserts
one row with a generated ``lead_ref`` (B2B-XXXXXXXX). ``update_details`` fills in
qualifying fields as they're collected.
"""
from __future__ import annotations

from db import database
from services import b2b as b2b_svc

_COLS = (
    "id, lead_ref, customer_id, conversation_id, company_name, contact_person, "
    "business_type, location, market, estimated_volume, required_services, "
    "frequency, current_provider, preferred_meeting_time, email, "
    "preferred_contact_method, notes, assigned_team, "
    "status, source, created_at, updated_at"
)

_UPDATABLE = frozenset({
    "company_name", "contact_person", "business_type", "location", "market",
    "estimated_volume", "required_services", "frequency", "current_provider",
    "preferred_meeting_time", "email", "preferred_contact_method", "notes", "status",
})


def _serialize(row: dict | None) -> dict | None:
    if not row:
        return None
    d = dict(row)
    for k in ("id", "customer_id", "conversation_id"):
        if d.get(k) is not None:
            d[k] = str(d[k])
    return d


async def get_open_for_conversation(conversation_id: str) -> dict | None:
    """Reuse an existing non-terminal lead for this conversation (idempotency)."""
    row = await database.fetchrow(
        f"select {_COLS} from b2b_leads where conversation_id = $1 "
        "and status not in ('won','lost') order by created_at desc limit 1",
        conversation_id,
    )
    return _serialize(row)


async def create(
    *,
    customer_id: str | None,
    conversation_id: str | None,
    business_type: str = "other",
    company_name: str | None = None,
    location: str | None = None,
    market: str | None = None,
    notes: str | None = None,
    source: str = "whatsapp",
) -> dict | None:
    if business_type not in b2b_svc.BUSINESS_TYPES:
        business_type = "other"
    row = await database.fetchrow(
        f"""
        insert into b2b_leads
            (lead_ref, customer_id, conversation_id, business_type, company_name,
             location, market, notes, source, status)
        values (
            'B2B-' || upper(substr(replace(gen_random_uuid()::text, '-', ''), 1, 8)),
            $1, $2, $3, $4, $5, $6, $7, $8, 'new'
        )
        returning {_COLS}
        """,
        customer_id, conversation_id, business_type, company_name,
        location, market, notes, source,
    )
    return _serialize(row)


async def update_details(lead_id: str, **fields) -> dict | None:
    """Patch qualifying fields (only whitelisted columns are writable)."""
    sets, values = [], []
    for k, v in fields.items():
        if k in _UPDATABLE and v is not None:
            values.append(v)
            sets.append(f"{k} = ${len(values)}")
    if not sets:
        return await get(lead_id)
    values.append(lead_id)
    row = await database.fetchrow(
        f"update b2b_leads set {', '.join(sets)} where id = ${len(values)} returning {_COLS}",
        *values,
    )
    return _serialize(row)


async def get(lead_id: str) -> dict | None:
    row = await database.fetchrow(f"select {_COLS} from b2b_leads where id = $1", lead_id)
    return _serialize(row)


async def list_open(limit: int = 100) -> list[dict]:
    rows = await database.fetch(
        f"select {_COLS} from b2b_leads where status not in ('won','lost') "
        f"order by created_at desc limit {max(1, min(int(limit), 200))}"
    )
    return [_serialize(r) for r in rows]
