"""Order reads/writes against the dev/test Supabase schema.

Rows are mapped to the existing ``OrderRead`` shape so the same FastAPI order
endpoints serve either SQLite (local) or Supabase (dev/test) data unchanged.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from db import database
from db.repositories import conversations_repo, order_events_repo
from services import order_store  # reuse status_label + active-status logic
from settings import get_settings

_TERMINAL = {order_store.COMPLETED, order_store.CANCELLED, order_store.ABANDONED}
_TERMINAL_STATUSES = _TERMINAL  # statuses a dashboard status-change may not leave
_HIDDEN_FROM_ACTIVE = _TERMINAL | {order_store.DRAFT}

_SELECT = "select * from orders"


def _item_label(item) -> str:
    """Human label for a stored item — dicts ({item, quantity}) render as
    '2x Suit'; plain strings pass through."""
    if isinstance(item, dict):
        name = item.get("item") or item.get("name") or "Item"
        qty = item.get("quantity")
        return f"{qty}x {name}" if qty else str(name)
    return str(item)


def to_read(row: dict, *, include_address: bool = False) -> dict:
    """Map a Supabase orders row to the OrderRead schema shape.

    ``include_address`` is False for broad list responses (privacy: the full
    pickup address is never returned in a list) and True only for the secure
    single-order detail endpoint (CLAUDE.md §7)."""
    status = row.get("status") or "active"
    items = row.get("items") or []
    if isinstance(items, str):
        items = [items]
    return {
        "id": str(row["id"]),
        "order_id": row["order_id"],
        "conversation_id": str(row["conversation_id"]) if row.get("conversation_id") else None,
        "customer_name": row.get("customer_name"),
        "service_type": row.get("service"),
        "service_id": row.get("service_id"),
        "service_display_name": row.get("service_display_name") or row.get("service"),
        "unit_type": row.get("unit_type"),
        "requires_manual_quote": bool(row.get("requires_manual_quote")),
        "items": [_item_label(i) for i in items],
        "pickup_area": row.get("pickup_area") or row.get("area"),
        "pickup_address": row.get("pickup_address") if include_address else None,
        # New booking orders store a normalized pickup_date + a slot label; legacy
        # capture orders only had a free-text pickup_slot — fall back to it.
        "pickup_date": (str(row["pickup_date"]) if row.get("pickup_date")
                        else row.get("pickup_slot")),
        "pickup_time": row.get("pickup_slot") if row.get("pickup_date") else None,
        "pickup_instructions": row.get("pickup_instruction_text"),
        "booking_state": row.get("conversation_state"),
        "city": row.get("city"),
        "delivery_preference": row.get("delivery_slot"),
        "status": status,
        "status_label": order_store.status_label(status),
        "notes": row.get("notes"),
        "change_request": row.get("change_request"),
        "amount": float(row["amount"]) if row.get("amount") is not None else None,
        "currency": "AED",
        "facility": row.get("facility"),
        "driver": row.get("driver"),
        "payment": row.get("payment_status"),
        "source_channel": row.get("source_channel") or "whatsapp",
        "is_demo": bool(row.get("is_demo")),
        # Dashboard-only joined fields (present on list_for_dashboard rows; None on
        # the plain list/get queries that don't join conversations/customers).
        "customer_phone": row.get("customer_masked_phone"),
        "needs_attention": bool(row.get("needs_attention")),
        "conversation_status": row.get("conversation_status"),
        "human_takeover": row.get("conversation_status") == "human_takeover",
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "completed_at": row.get("completed_at"),
    }


# Demo (is_demo=true) rows are excluded from dashboard order APIs unless
# ENABLE_DEMO_DATA=true. Real WhatsApp orders are is_demo=false, so they always
# show. This is the "production excludes demo by default" rule (spec §2).
def _include_demo() -> bool:
    return get_settings().enable_demo_data


async def list_active_read() -> list[dict]:
    rows = await database.fetch(
        _SELECT + " where status <> all($1::text[]) and (is_demo = false or $2) "
        "order by updated_at desc",
        list(_HIDDEN_FROM_ACTIVE), _include_demo(),
    )
    return [to_read(r) for r in rows]


async def list_completed_read() -> list[dict]:
    rows = await database.fetch(
        _SELECT + " where status = $1 and (is_demo = false or $2) "
        "order by completed_at desc nulls last",
        order_store.COMPLETED, _include_demo(),
    )
    return [to_read(r) for r in rows]


async def list_read(status: str | None = None) -> list[dict]:
    if status:
        rows = await database.fetch(
            _SELECT + " where status = $1 and (is_demo = false or $2) "
            "order by updated_at desc", status, _include_demo())
    else:
        rows = await database.fetch(
            _SELECT + " where (is_demo = false or $1) order by updated_at desc",
            _include_demo())
    return [to_read(r) for r in rows]


# An order "needs attention" when its conversation is flagged for a human or its
# status is an operational-exception state. SQL literal (no bind param) so it can
# appear in SELECT / WHERE / ORDER BY without param-count juggling.
_ATTENTION_SQL = (
    "(coalesce(c.human_intervention_required, false) "
    "or o.status in ('support_required', 'cancellation_requested', 'pickup_change_requested'))"
)
_DASHBOARD_SORTS = {
    "new": "o.created_at desc",
    "old": "o.created_at asc",
    "pickup": "o.pickup_date asc nulls last, o.pickup_start_time asc nulls last",
    "updated": "o.updated_at desc",
    "attention": f"{_ATTENTION_SQL} desc, o.created_at desc",
}


async def list_for_dashboard(
    *, search: str | None = None, status: str | None = None,
    service_id: str | None = None, pickup_date=None, source: str | None = None,
    needs_attention: bool | None = None, sort: str = "attention",
    page: int = 1, page_size: int = 25, include_demo: bool | None = None,
) -> tuple[list[dict], int]:
    """Filtered, sorted, paginated orders for the dashboard Orders section.
    Returns (orders_as_read, total_count). Joins the conversation (for
    needs_attention / human_takeover) and customer (masked phone)."""
    if include_demo is None:
        include_demo = _include_demo()
    params: list = []

    def p(v):
        params.append(v)
        return f"${len(params)}"

    conds = [f"(o.is_demo = false or {p(include_demo)})"]
    if status:
        conds.append(f"o.status = {p(status)}")
    if service_id:
        conds.append(f"o.service_id = {p(service_id)}")
    if source:
        conds.append(f"o.source_channel = {p(source)}")
    if pickup_date is not None:
        conds.append(f"o.pickup_date = {p(pickup_date)}")
    if needs_attention is True:
        conds.append(_ATTENTION_SQL)
    elif needs_attention is False:
        conds.append(f"not {_ATTENTION_SQL}")
    if search:
        s = p(f"%{search.strip()}%")
        conds.append(
            f"(o.order_id ilike {s} or o.customer_name ilike {s} "
            f"or cust.masked_phone ilike {s} or cust.phone_e164 ilike {s})"
        )

    base = (
        "from orders o "
        "left join conversations c on c.id = o.conversation_id "
        "left join customers cust on cust.id = o.customer_id "
        f"where {' and '.join(conds)}"
    )
    total = await database.fetchval(f"select count(*) {base}", *params)

    order_by = _DASHBOARD_SORTS.get(sort, _DASHBOARD_SORTS["attention"])
    limit_ph = p(max(1, min(page_size, 100)))
    offset_ph = p(max(0, (max(1, page) - 1) * page_size))
    rows = await database.fetch(
        f"select o.*, cust.masked_phone as customer_masked_phone, "
        f"c.status as conversation_status, c.assigned_team as conversation_team, "
        f"{_ATTENTION_SQL} as needs_attention {base} "
        f"order by {order_by} limit {limit_ph} offset {offset_ph}",
        *params,
    )
    return [to_read(r) for r in rows], total


async def get_read(order_id: str) -> dict | None:
    row = await database.fetchrow(
        _SELECT + " where upper(replace(order_id,' ','')) = upper(replace($1,' ','')) ",
        order_id,
    )
    # Secure single-order detail: the full pickup address IS included here (and
    # only here) — list responses never expose it.
    return to_read(row, include_address=True) if row else None


async def complete(order_id: str) -> dict | None:
    row = await database.fetchrow(
        "update orders set status = 'completed', completed_at = now() "
        "where upper(replace(order_id,' ','')) = upper(replace($1,' ','')) returning *",
        order_id,
    )
    return to_read(row) if row else None


async def set_status(
    order_id: str, status: str, *, actor_name: str | None = None, actor_type: str = "staff"
) -> dict | None:
    if status not in order_store.ORDER_STATUSES:
        raise ValueError(f"Unknown status: {status}")
    existing = await database.fetchrow(
        "select id, status from orders "
        "where upper(replace(order_id,' ','')) = upper(replace($1,' ','')) ",
        order_id,
    )
    if existing is None:
        return None
    # Transition guard (spec §16): a terminal order can't be moved to another
    # status. Forward/corrective moves between non-terminal statuses are allowed;
    # the backend remains the sole authority on status changes.
    if existing["status"] in _TERMINAL_STATUSES and status != existing["status"]:
        raise ValueError(f"Cannot change a {existing['status']} order.")
    completed_at = ", completed_at = now()" if status == order_store.COMPLETED else ""
    row = await database.fetchrow(
        f"update orders set status = $2{completed_at} where id = $1 returning *",
        existing["id"], status,
    )
    # Audit trail (spec §12): every operational status change is recorded.
    if existing["status"] != status:
        await order_events_repo.create(
            order_uuid=existing["id"], event_type="status_changed",
            from_status=existing["status"], to_status=status,
            actor_type=actor_type, actor_name=actor_name,
            notes=f"Status changed to {status}"
            + (f" by {actor_name}" if actor_name else " from the dashboard."),
        )
    return to_read(row) if row else None


# --------------------------------------------------------------------------
# WhatsApp order capture — draft create/update from a live conversation
# --------------------------------------------------------------------------
# Public order-number format for WhatsApp-captured orders: LK-YYYY-######
# (spec §14.6, e.g. LK-2026-000123). The sequence is per calendar year, zero
# padded to 6 digits. Replaces the earlier "LC-TEST-####" scheme (the "LC-"
# prefix was a legacy "Laundry Coloss" leftover; the brand is Laundry Khalas).
_ORDER_NUMBER_PREFIX = "LK"

# orders column -> order_events event_type, emitted the first time a field is set.
_FIELD_EVENTS = {
    "service": "service_selected",
    "items": "items_added",
    "pickup_address": "address_added",
    "pickup_slot": "pickup_slot_added",
    "payment_method": "payment_method_added",
}


async def next_test_order_id() -> str:
    """Next public order number in LK-YYYY-###### format (spec §14.6).

    Sequence is per calendar year, derived from the current max suffix so it
    survives restarts and stays unique (the confirm path is idempotent per
    conversation). Zero-padded to 6 digits, e.g. ``LK-2026-000123``.
    """
    year = datetime.now(timezone.utc).year
    prefix = f"{_ORDER_NUMBER_PREFIX}-{year}-"
    rows = await database.fetch(
        "select order_id from orders where order_id like $1", prefix + "%"
    )
    highest = 0
    for r in rows:
        m = re.search(r"(\d+)\s*$", r.get("order_id") or "")
        if m:
            highest = max(highest, int(m.group(1)))
    return f"{prefix}{highest + 1:06d}"


async def get_open_for_conversation(conversation_id: str) -> dict | None:
    """Most recent non-terminal order linked to a conversation (draft or active)."""
    return await database.fetchrow(
        _SELECT + " where conversation_id = $1 and status <> all($2::text[]) "
        "order by created_at desc limit 1",
        conversation_id,
        list(_TERMINAL),
    )


def _estimate_amount(details) -> float | None:
    """Best-effort 'from' estimate ONLY for per-item services with known
    quantities and a firm price (e.g. Boutique Clean & Press from 11 AED/item).
    Never invents a price for per-bag/set/pair/sqm services, nor for any service
    flagged ``requires_manual_quote`` (bag spa, tailoring, carpet/curtain) —
    those stay null and are quoted manually (RULE 7/8)."""
    from agents.whatsapp_agent import tools

    if not details.service_key or not details.items:
        return None
    if getattr(details, "requires_manual_quote", False):
        return None
    price = tools.lookup_price(details.service_key)
    if not price or price.get("unit") != "item":
        return None
    total_qty = sum(int(i.get("quantity", 1) or 1) for i in details.items)
    amount = total_qty * float(price["price"])
    if price.get("min_price"):
        amount = max(amount, float(price["min_price"]))
    return round(amount, 2)


def _confirmed_status(details) -> str:
    """Status a confirmed booking lands in: pickup_scheduled when a pickup slot
    is known, otherwise active."""
    return order_store.PICKUP_SCHEDULED if details.pickup_slot else order_store.ACTIVE


async def create_or_update_draft_from_conversation(
    *, conversation_id: str, customer: dict | None, details
) -> dict:
    """Create (or update-in-place) the draft order for a conversation from the
    accumulated ``OrderDetails`` and write the matching order_events.

    Returns ``{"row": <orders row>, "created": bool, "confirmed_now": bool}``.
    The order stays ``draft`` until the customer confirms AND enough detail
    exists (service/items + a pickup area/address); only then is it promoted to
    pickup_scheduled/active. Never creates duplicates — an open order for the
    conversation is updated instead. ``linked_order_id`` is set on the
    conversation so the inbox/dashboard can cross-reference.
    """
    existing = await get_open_for_conversation(conversation_id)
    amount = _estimate_amount(details)
    confirmable = details.confirmed and details.is_confirmable()

    target = {
        "customer_name": details.name or (customer or {}).get("display_name"),
        "service": details.service_label,
        "service_id": details.service_key,
        "service_display_name": details.service_label,
        "unit_type": getattr(details, "unit_type", None),
        "requires_manual_quote": bool(getattr(details, "requires_manual_quote", False)),
        "items": details.items or None,
        "city": details.city,
        "area": details.area,
        "pickup_address": details.address,
        "pickup_slot": details.pickup_slot,
        "delivery_slot": details.delivery_slot,
        "payment_method": details.payment_method,
        "amount": amount,
    }

    if existing is None:
        status = _confirmed_status(details) if confirmable else order_store.DRAFT
        order_id = await next_test_order_id()
        row = await database.fetchrow(
            """
            insert into orders
                (order_id, conversation_id, customer_id, customer_name, service,
                 service_id, service_display_name, unit_type, requires_manual_quote,
                 items, city, area, pickup_address, pickup_slot, delivery_slot,
                 payment_method, amount, status, source_channel, notes,
                 is_test_data, is_demo, environment, test_scenario_id, created_by_seed)
            values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11, $12, $13,
                    $14, $15, $16, $17, $18, 'whatsapp', $19,
                    true, false, 'dev', 'whatsapp_live_capture', false)
            returning *
            """,
            order_id,
            conversation_id,
            (customer or {}).get("id"),
            target["customer_name"],
            target["service"],
            target["service_id"],
            target["service_display_name"],
            target["unit_type"],
            target["requires_manual_quote"],
            target["items"] or [],
            target["city"],
            target["area"],
            target["pickup_address"],
            target["pickup_slot"],
            target["delivery_slot"],
            target["payment_method"],
            target["amount"],
            status,
            "Created from WhatsApp conversation.",
        )
        await conversations_repo.link_order(conversation_id, order_id)
        await order_events_repo.create(
            order_uuid=row["id"], event_type="order_created", to_status=status,
            notes=f"Draft order {order_id} created from WhatsApp.",
        )
        for col, event_type in _FIELD_EVENTS.items():
            if target.get(col):
                await order_events_repo.create(
                    order_uuid=row["id"], event_type=event_type,
                    notes=f"{col} captured.",
                )
        if confirmable:
            await order_events_repo.create(
                order_uuid=row["id"], event_type="order_confirmed", to_status=status,
                notes="Customer confirmed the booking.",
            )
        return {"row": row, "created": True, "confirmed_now": confirmable}

    # --- update in place: only set fields that are newly known -----------------
    changed_cols: list[str] = []
    sets: list[str] = []
    values: list = []
    for col, new_val in target.items():
        if new_val and existing.get(col) != new_val:
            values.append(new_val)
            cast = "::jsonb" if col == "items" else ""
            sets.append(f"{col} = ${len(values)}{cast}")
            changed_cols.append(col)

    confirmed_now = (
        confirmable and existing.get("status") == order_store.DRAFT
    )
    new_status = _confirmed_status(details) if confirmed_now else None
    if new_status:
        values.append(new_status)
        sets.append(f"status = ${len(values)}")

    row = existing
    if sets:
        values.append(existing["id"])
        row = await database.fetchrow(
            f"update orders set {', '.join(sets)} where id = ${len(values)} returning *",
            *values,
        )

    for col in changed_cols:
        event_type = _FIELD_EVENTS.get(col)
        if event_type and not existing.get(col):  # newly-added field
            await order_events_repo.create(
                order_uuid=existing["id"], event_type=event_type, notes=f"{col} captured.",
            )
    if confirmed_now:
        await order_events_repo.create(
            order_uuid=existing["id"], event_type="order_confirmed",
            from_status=order_store.DRAFT, to_status=new_status,
            notes="Customer confirmed the booking.",
        )
        await order_events_repo.create(
            order_uuid=existing["id"], event_type="order_status_changed",
            from_status=order_store.DRAFT, to_status=new_status,
        )

    return {"row": row, "created": False, "confirmed_now": confirmed_now}


# --------------------------------------------------------------------------
# WhatsApp BOOKING STATE MACHINE — persistence for services/booking_flow.py
# --------------------------------------------------------------------------
# Columns the FSM is allowed to write on the draft. conversation_state and the
# timestamps are handled explicitly below; everything else is ignored (the LLM
# can never write an arbitrary column).
_BOOKING_COLS = frozenset({
    "customer_name",
    "service_id", "service", "service_display_name", "service_name_snapshot",
    "unit_type", "requires_manual_quote", "pickup_date", "pickup_slot_id",
    "pickup_slot", "pickup_start_time", "pickup_end_time", "pickup_address",
    "pickup_area", "area", "pickup_emirate", "pickup_latitude", "pickup_longitude",
    "address_source", "pickup_instruction_code", "pickup_instruction_text",
})
_BOOKING_CONFIRMED = "booking_confirmed"
_BOOKING_CANCELLED = "booking_cancelled"


async def get_active_booking(conversation_id: str) -> dict | None:
    """The open draft acting as this conversation's booking (or None)."""
    return await get_open_for_conversation(conversation_id)


async def get_active_draft(conversation_id: str) -> dict | None:
    """The IN-PROGRESS draft for a conversation (status='draft' only). Unlike
    get_open_for_conversation, this excludes confirmed/scheduled orders, so a
    completed order never looks like an in-progress workflow (spec §state-model:
    a completed workflow must not block a new one)."""
    return await database.fetchrow(
        _SELECT + " where conversation_id = $1 and status = $2 "
        "order by created_at desc limit 1",
        conversation_id, order_store.DRAFT,
    )


async def get_latest_for_conversation(conversation_id: str) -> dict | None:
    """Most recent order for a conversation, ANY status (for a status check)."""
    return await database.fetchrow(
        _SELECT + " where conversation_id = $1 order by created_at desc limit 1",
        conversation_id,
    )


async def set_conversation_state(order_uuid: str, state: str) -> dict | None:
    """Set only the conversation_state on an order (e.g. mark a confirmed order
    POST_ORDER so the conversation can offer next actions)."""
    return await database.fetchrow(
        "update orders set conversation_state = $2 where id = $1 returning *",
        order_uuid, state,
    )


async def start_booking(conversation_id: str, customer: dict | None) -> dict:
    """Create ONE draft booking in state waiting_for_service with every booking
    field left null — no service/date/address/etc. is assumed.

    Idempotent: if a fresh, empty draft already exists for this conversation
    (waiting_for_service with no service picked yet), it is REUSED rather than
    duplicated — so repeated "place another order" taps never create multiple
    drafts (spec §idempotency)."""
    existing = await get_active_draft(conversation_id)
    if existing and existing.get("conversation_state") in (
        None, "waiting_for_service"
    ) and not existing.get("service_id"):
        return existing
    order_id = await next_test_order_id()
    row = await database.fetchrow(
        """
        insert into orders
            (order_id, conversation_id, customer_id, customer_name, status,
             conversation_state, source_channel, notes,
             is_test_data, is_demo, environment, test_scenario_id, created_by_seed)
        values ($1, $2, $3, $4, $5, 'waiting_for_service', 'whatsapp',
                'WhatsApp booking in progress.', true, false, 'dev',
                'whatsapp_booking', false)
        returning *
        """,
        order_id,
        conversation_id,
        (customer or {}).get("id"),
        # customer_name starts NULL: the confirmed booking name is collected in the
        # flow. The WhatsApp profile name (customers.display_name) is NEVER copied
        # here automatically — it is only offered for the customer to confirm.
        None,
        order_store.DRAFT,
    )
    await conversations_repo.link_order(conversation_id, order_id)
    await order_events_repo.create(
        order_uuid=row["id"], event_type="order_created", to_status=order_store.DRAFT,
        notes=f"Booking draft {order_id} started from WhatsApp.",
    )
    return row


async def get_confirmed_customer_name(customer_id) -> str | None:
    """The most recent CONFIRMED booking name for a customer (from a prior real
    order — not a draft/cancelled/abandoned one). Used to offer name reuse on a
    later order. Returns None when the customer has never confirmed a name."""
    if not customer_id:
        return None
    row = await database.fetchrow(
        "select customer_name from orders where customer_id = $1 "
        "and customer_name is not null and status <> all($2::text[]) "
        "order by created_at desc limit 1",
        customer_id, [order_store.DRAFT, order_store.CANCELLED, order_store.ABANDONED],
    )
    return row["customer_name"] if row else None


async def apply_booking_updates(order_uuid: str, updates: dict, state: str) -> dict | None:
    """Persist the FSM's field updates + the new conversation_state. Only
    whitelisted booking columns are written; unknown keys are ignored."""
    data = dict(updates or {})
    touch_service = data.pop("_touch_service_selected_at", False)

    sets = ["conversation_state = $1"]
    values: list = [state]
    for col, val in data.items():
        if col in _BOOKING_COLS:
            values.append(val)
            sets.append(f"{col} = ${len(values)}")
    if touch_service:
        sets.append("service_selected_at = now()")

    values.append(order_uuid)
    return await database.fetchrow(
        f"update orders set {', '.join(sets)} where id = ${len(values)} returning *",
        *values,
    )


async def confirm_booking(order_uuid: str) -> tuple[dict | None, bool]:
    """Flip the draft to a confirmed operational order EXACTLY once. Returns
    (row, created_now). A redelivered/duplicate confirm returns created_now=False
    and writes no second event — so the operational order is created only once."""
    row = await database.fetchrow(
        """
        update orders
           set status = $2, conversation_state = $3, confirmed_at = now()
         where id = $1 and status = $4 and conversation_state is distinct from $3
        returning *
        """,
        order_uuid, order_store.PICKUP_SCHEDULED, _BOOKING_CONFIRMED, order_store.DRAFT,
    )
    if row is None:
        current = await database.fetchrow(_SELECT + " where id = $1", order_uuid)
        return current, False
    await order_events_repo.create(
        order_uuid=order_uuid, event_type="order_confirmed",
        from_status=order_store.DRAFT, to_status=order_store.PICKUP_SCHEDULED,
        actor_type="customer", notes="Customer confirmed the booking via WhatsApp.",
    )
    return row, True


async def cancel_booking(order_uuid: str) -> dict | None:
    row = await database.fetchrow(
        "update orders set status = $2, conversation_state = $3 where id = $1 returning *",
        order_uuid, order_store.CANCELLED, _BOOKING_CANCELLED,
    )
    if row:
        await order_events_repo.create(
            order_uuid=order_uuid, event_type="order_status_changed",
            to_status=order_store.CANCELLED, actor_type="customer",
            notes="Booking cancelled by customer via WhatsApp.",
        )
    return row


async def dashboard_metrics() -> dict:
    """Real metric-card numbers for the Orders section (spec §13). Demo rows
    excluded unless ENABLE_DEMO_DATA=true. 'new today' uses the Asia/Dubai day."""
    inc = _include_demo()
    row = await database.fetchrow(
        """
        select
          count(*) filter (
            where created_at >= (date_trunc('day', now() at time zone 'Asia/Dubai')
                                 at time zone 'Asia/Dubai')) as new_today,
          count(*) filter (where status <> all($2::text[]))  as active,
          count(*) filter (where status = 'pickup_scheduled') as confirmed_pickups,
          count(*) filter (where status = 'completed')        as completed,
          count(*) filter (where status = 'cancelled')        as cancelled
        from orders
        where (is_demo = false or $1)
        """,
        inc, list(_HIDDEN_FROM_ACTIVE),
    )
    attention = await database.fetchval(
        "select count(*) from orders o "
        "left join conversations c on c.id = o.conversation_id "
        f"where (o.is_demo = false or $1) and {_ATTENTION_SQL}",
        inc,
    )
    return {
        "new_today": row["new_today"], "active_orders": row["active"],
        "confirmed_pickups": row["confirmed_pickups"], "completed": row["completed"],
        "cancelled": row["cancelled"], "needs_attention": attention,
    }


async def metrics() -> dict:
    rows = await database.fetch("select status from orders")
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    return {
        "active_orders": sum(v for k, v in by_status.items() if k not in _HIDDEN_FROM_ACTIVE),
        "completed_orders": by_status.get(order_store.COMPLETED, 0),
        "cancellation_requests": by_status.get(order_store.CANCELLATION_REQUESTED, 0),
        "pickup_change_requests": by_status.get(order_store.PICKUP_CHANGE_REQUESTED, 0),
        "support_required": by_status.get(order_store.SUPPORT_REQUIRED, 0),
        "total_orders": len(rows),
        "orders_by_status": by_status,
    }
