"""Order-event (audit trail) writes against the dev/test Supabase schema.

Every meaningful order change during the WhatsApp capture flow writes one
``order_events`` row: order_created, service_selected, items_added,
address_added, pickup_slot_added, payment_method_added, order_confirmed,
order_status_changed, cancellation_requested, pickup_change_requested,
human_handoff_created. ``order_id`` here is the orders table UUID (FK), not the
business id.
"""
from __future__ import annotations

from db import database

_SELECT = """
  select id, order_id, event_type, from_status, to_status, actor_type,
         actor_name, notes, metadata, is_test_data, is_demo, environment,
         test_scenario_id, created_at
    from order_events
"""


async def create(
    *,
    order_uuid: str,
    event_type: str,
    from_status: str | None = None,
    to_status: str | None = None,
    actor_type: str = "agent",
    actor_name: str = "WhatsApp Agent",
    notes: str | None = None,
    metadata: dict | None = None,
    is_test_data: bool = True,
    test_scenario_id: str | None = "whatsapp_live_capture",
) -> dict | None:
    return await database.fetchrow(
        """
        insert into order_events
            (order_id, event_type, from_status, to_status, actor_type, actor_name,
             notes, metadata, is_test_data, is_demo, environment, test_scenario_id,
             created_by_seed)
        values ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, false, 'dev', $10, false)
        returning id, order_id, event_type, from_status, to_status, actor_type,
                  actor_name, notes, metadata, created_at
        """,
        order_uuid,
        event_type,
        from_status,
        to_status,
        actor_type,
        actor_name,
        notes,
        metadata or {},
        is_test_data,
        test_scenario_id,
    )


async def list_for_order(order_uuid: str) -> list[dict]:
    return await database.fetch(
        _SELECT + " where order_id = $1 order by created_at asc", order_uuid
    )
