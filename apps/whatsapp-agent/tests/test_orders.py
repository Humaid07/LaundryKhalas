"""Order-state API + stateful-conversation tests: the endpoints a dashboard
reads, and the guarantee that a chat booking actually creates an active
order behind the scenes and that marking it completed moves it across.
"""


async def test_seeded_demo_orders_split_active_vs_completed(client):
    active = (await client.get("/api/orders/active")).json()
    completed = (await client.get("/api/orders/completed")).json()

    active_ids = {o["order_id"] for o in active}
    completed_ids = {o["order_id"] for o in completed}

    # LK-AE-1024/1025/1026 are in flight; LK-AE-1027 is completed.
    assert {"LK-AE-1024", "LK-AE-1025", "LK-AE-1026"} <= active_ids
    assert "LK-AE-1027" in completed_ids
    assert "LK-AE-1027" not in active_ids
    assert all(o["is_demo"] for o in active + completed)


async def test_get_single_order_and_unknown_404(client):
    ok = await client.get("/api/orders/LK-AE-1024")
    assert ok.status_code == 200
    assert ok.json()["status"] == "pickup_scheduled"

    missing = await client.get("/api/orders/LK-AE-9999")
    assert missing.status_code == 404


async def test_mark_completed_moves_order_from_active_to_completed(client):
    before = {o["order_id"] for o in (await client.get("/api/orders/active")).json()}
    assert "LK-AE-1024" in before

    done = await client.post("/api/orders/LK-AE-1024/complete")
    assert done.status_code == 200
    assert done.json()["status"] == "completed"
    assert done.json()["completed_at"]

    active_ids = {o["order_id"] for o in (await client.get("/api/orders/active")).json()}
    completed_ids = {o["order_id"] for o in (await client.get("/api/orders/completed")).json()}
    assert "LK-AE-1024" not in active_ids
    assert "LK-AE-1024" in completed_ids


async def test_metrics_reflect_order_state(client):
    metrics = (await client.get("/api/orders/metrics")).json()
    assert metrics["active_orders"] >= 3
    assert metrics["completed_orders"] >= 1
    assert "orders_by_status" in metrics


async def test_status_update_validates_status(client):
    bad = await client.post(
        "/api/orders/LK-AE-1025/status", json={"status": "teleporting"}
    )
    assert bad.status_code == 422

    good = await client.post(
        "/api/orders/LK-AE-1025/status", json={"status": "out_for_delivery"}
    )
    assert good.status_code == 200
    assert good.json()["status"] == "out_for_delivery"


async def _book_full_order(client):
    """Drive a booking to an active order; returns (conversation_id, order_id)."""
    first = await client.post(
        "/api/test-chat/message",
        json={"message": "I'd like to book a dry cleaning pickup"},
    )
    cid = first.json()["conversation_id"]
    # service (via chip), then items, area, time as the flow asks.
    await client.post(
        "/api/test-chat/message",
        json={"conversation_id": cid, "message": "Dry Cleaning", "action_id": "dry_cleaning"},
    )
    await client.post(
        "/api/test-chat/message",
        json={"conversation_id": cid, "message": "2 suits"},
    )
    await client.post(
        "/api/test-chat/message",
        json={"conversation_id": cid, "message": "Dubai Marina"},
    )
    summary = await client.post(
        "/api/test-chat/message",
        json={"conversation_id": cid, "message": "tomorrow evening"},
    )
    # Summary step surfaces the draft order id and confirm buttons.
    assert any(a["id"] == "confirm_booking" for a in summary.json()["actions"])

    confirmed = await client.post(
        "/api/test-chat/message",
        json={"conversation_id": cid, "message": "Confirm Booking", "action_id": "confirm_booking"},
    )
    return cid, confirmed.json()


async def test_booking_flow_creates_active_order_behind_the_scenes(client):
    _cid, body = await _book_full_order(client)

    assert body["order_status"] == "active"
    order_id = body["order_id"]
    assert order_id and order_id.startswith("LK-")
    assert "demo mode" in body["agent_reply"].lower()

    # The freshly booked order is now queryable + listed as active.
    active_ids = {o["order_id"] for o in (await client.get("/api/orders/active")).json()}
    assert order_id in active_ids

    detail = (await client.get(f"/api/orders/{order_id}")).json()
    assert detail["service_type"] == "Dry Cleaning"
    assert detail["pickup_area"] == "Dubai Marina"
    assert detail["items"]  # item details were captured


async def test_add_items_updates_the_conversation_order(client):
    cid, body = await _book_full_order(client)
    order_id = body["order_id"]

    before = (await client.get(f"/api/orders/{order_id}")).json()
    before_count = len(before["items"])

    # Add-more-items in the same conversation attaches to that order.
    await client.post(
        "/api/test-chat/message",
        json={"conversation_id": cid, "message": "Add More Items", "action_id": "add_more_items"},
    )
    await client.post(
        "/api/test-chat/message",
        json={"conversation_id": cid, "message": "1 winter coat"},
    )

    after = (await client.get(f"/api/orders/{order_id}")).json()
    assert len(after["items"]) == before_count + 1
    assert any("coat" in i.lower() for i in after["items"])


async def test_cancel_flow_requests_support_not_auto_cancel(client):
    # Ask to cancel a known active order; agent must ask to confirm first.
    first = await client.post(
        "/api/test-chat/message",
        json={"message": "Cancel Order", "action_id": "cancel_order"},
    )
    cid = first.json()["conversation_id"]
    ask = await client.post(
        "/api/test-chat/message",
        json={"conversation_id": cid, "message": "LK-AE-1024"},
    )
    assert "cancellation request" in ask.json()["agent_reply"].lower()

    # Order is NOT cancelled just by asking.
    assert (await client.get("/api/orders/LK-AE-1024")).json()["status"] == "pickup_scheduled"

    # Confirm -> recorded as a cancellation request, never a live cancellation.
    confirm = await client.post(
        "/api/test-chat/message",
        json={"conversation_id": cid, "message": "yes please"},
    )
    reply = confirm.json()["agent_reply"].lower()
    assert "cancellation request" in reply
    assert "no live cancellation" in reply
    assert (await client.get("/api/orders/LK-AE-1024")).json()["status"] == "cancellation_requested"


async def test_change_pickup_time_records_request_without_confirming(client):
    first = await client.post(
        "/api/test-chat/message",
        json={"message": "Change Pickup Time", "action_id": "change_pickup_time"},
    )
    cid = first.json()["conversation_id"]
    await client.post(
        "/api/test-chat/message",
        json={"conversation_id": cid, "message": "LK-AE-1026, Friday morning"},
    )
    order = (await client.get("/api/orders/LK-AE-1026")).json()
    assert order["status"] == "pickup_change_requested"
    assert "friday" in (order["change_request"] or "").lower()


async def test_completed_order_cannot_be_cancelled_from_chat(client):
    first = await client.post(
        "/api/test-chat/message",
        json={"message": "Cancel Order", "action_id": "cancel_order"},
    )
    cid = first.json()["conversation_id"]
    ask = await client.post(
        "/api/test-chat/message",
        json={"conversation_id": cid, "message": "LK-AE-1027"},  # already completed
    )
    reply = ask.json()["agent_reply"].lower()
    assert "already completed" in reply
    assert (await client.get("/api/orders/LK-AE-1027")).json()["status"] == "completed"


async def test_settings_status_exposes_typing_delays(client):
    status = (await client.get("/api/settings/status")).json()
    assert status["agent_min_typing_delay_ms"] == 2000
    assert status["agent_max_typing_delay_ms"] == 3000
    assert status["agent_min_typing_delay_ms"] <= status["agent_max_typing_delay_ms"]
