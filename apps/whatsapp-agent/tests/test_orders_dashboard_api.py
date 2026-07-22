"""Orders-section dashboard API + demo-data guarding.

These run in local SQLite mode (no Supabase), so the Supabase-only endpoints
return their safe empty/zero shapes — which is exactly the contract the frontend
relies on. The live DB behaviour (filters, needs_attention, events, demo
exclusion) is verified by the live integration + Playwright E2E, not here.
"""
from settings import Settings


def test_enable_demo_data_defaults_false():
    # Production-safe default: demo rows are excluded unless explicitly enabled.
    assert Settings(_env_file=None).enable_demo_data is False


async def test_orders_search_shape_sqlite(client):
    r = await client.get("/api/orders/search?page=1&page_size=10&sort=new")
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"orders", "total", "page", "page_size"}
    assert body["page"] == 1 and body["page_size"] == 10
    assert isinstance(body["orders"], list)


async def test_orders_search_accepts_filters(client):
    # Every documented filter param is accepted (validated types).
    r = await client.get(
        "/api/orders/search",
        params={"search": "x", "status": "confirmed", "service_id": "s",
                "pickup_date": "2026-07-25", "source": "whatsapp",
                "needs_attention": "true", "sort": "attention", "page": 2, "page_size": 5},
    )
    assert r.status_code == 200
    assert r.json()["page"] == 2


async def test_orders_metrics_summary_shape(client):
    r = await client.get("/api/orders/metrics/summary")
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"new_today", "active_orders", "confirmed_pickups",
                         "completed", "cancelled", "needs_attention"}


async def test_order_status_update_accepts_actor(client):
    # PATCH route exists and validates; unknown order -> 404 (not 405/500).
    r = await client.patch("/api/orders/NOPE-9999/status",
                           json={"status": "completed", "actor_name": "Operations"})
    assert r.status_code in (404, 422)
