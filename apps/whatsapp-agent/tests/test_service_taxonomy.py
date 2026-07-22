"""Tests for the canonical LaundryKhalas service taxonomy synced to the live
website (config/laundry_services.json + rules + order_extraction +
service_selection + taxonomy_sync + the SEO taxonomy + the orders repo mapping).

Covers requirement #9 of the service-taxonomy sync task:
  * the service option list contains every live service
  * item/word -> service mapping (dry cleaning suits -> Boutique Clean & Press,
    shoes -> Artisan Shoe Restoration, carpet -> Deep Carpet & Curtain Care)
  * a bare "laundry pickup" asks for clarification instead of guessing
  * the selected service is persisted (repo mapping) with id + display name
  * an order round-trips onto the dashboard shape with its service
  * dashboard/SEO taxonomies match the backend (sync check is in_sync)
"""
from db.repositories import orders_repo
from rules import service_by_id, service_ids, service_options
from seo_agents.taxonomy import service_names as seo_service_names
from seo_agents.taxonomy import taxonomy_service_ids
from services import service_selection
from services.order_extraction import (
    OrderDetails,
    accumulate_from_messages,
    extract_customer_order_details,
)
from services.taxonomy_sync import check_taxonomy_sync

# The eight live services from https://laundrykhalas.com/en-ae/personal-laundry/
LIVE_SERVICE_IDS = {
    "premium_wash_fold",
    "boutique_clean_press",
    "steam_pressing_only",
    "luxe_bed_bath_care",
    "artisan_shoe_restoration",
    "luxury_bag_spa",
    "tailoring_alterations",
    "deep_carpet_curtain_care",
}
LIVE_SERVICE_NAMES = {
    "Premium Wash & Fold",
    "Boutique Clean & Press",
    "Steam Pressing Only",
    "Luxe Bed & Bath Care",
    "Artisan Shoe Restoration",
    "Luxury Bag Spa",
    "Tailoring & Alterations",
    "Deep Carpet & Curtain Care",
}


# --- catalog / dropdown ----------------------------------------------------
def test_backend_catalog_is_the_eight_live_services():
    assert set(service_ids()) == LIVE_SERVICE_IDS


def test_service_options_contains_all_live_services_plus_help():
    opts = service_selection.service_options()
    ids = [o["id"] for o in opts]
    assert LIVE_SERVICE_IDS.issubset(set(ids))
    assert ids[-1] == "help_me_choose"  # the "Not sure / Help me choose" escape hatch
    labels = {o["label"] for o in opts}
    assert LIVE_SERVICE_NAMES.issubset(labels)


def test_service_options_matches_rules_options():
    # service_selection is derived from rules — the ids must line up.
    catalog_ids = [o["id"] for o in service_options()]
    assert catalog_ids == list(service_ids())


# --- word / item -> service mapping ----------------------------------------
def test_dry_cleaning_two_suits_maps_to_boutique_clean_press():
    d = extract_customer_order_details("I need dry cleaning for two suits")
    assert d.service_key == "boutique_clean_press"
    assert d.service_label == "Boutique Clean & Press"
    assert {"item": "Suit", "quantity": 2} in d.items


def test_shoes_map_to_artisan_shoe_restoration():
    assert extract_customer_order_details("I need my shoes cleaned").service_key == (
        "artisan_shoe_restoration"
    )
    assert extract_customer_order_details("can you restore my sneakers").service_key == (
        "artisan_shoe_restoration"
    )


def test_carpet_maps_to_deep_carpet_curtain_care():
    assert extract_customer_order_details("I need carpet cleaning").service_key == (
        "deep_carpet_curtain_care"
    )
    assert extract_customer_order_details("please clean my curtains").service_key == (
        "deep_carpet_curtain_care"
    )


def test_bag_of_clothes_maps_to_premium_wash_fold():
    assert extract_customer_order_details("just my weekly laundry, a bag of clothes").service_key == (
        "premium_wash_fold"
    )


def test_duvet_maps_to_luxe_bed_bath_care():
    assert extract_customer_order_details("I have a duvet and some towels").service_key == (
        "luxe_bed_bath_care"
    )


def test_alterations_map_to_tailoring():
    assert extract_customer_order_details("can you hem my trousers and fix a zip").service_key == (
        "tailoring_alterations"
    )


def test_handbag_maps_to_luxury_bag_spa():
    assert extract_customer_order_details("clean my designer handbag").service_key == (
        "luxury_bag_spa"
    )


# --- clarification: never guess --------------------------------------------
def test_bare_laundry_pickup_does_not_auto_pick_a_service():
    d = extract_customer_order_details("Hi, I need a laundry pickup service")
    assert d.service_key is None
    assert service_selection.needs_service_clarification(d) is True


def test_clarification_prompt_and_options():
    payload = service_selection.build_service_clarification()
    assert payload["prompt"] == "Sure — which service do you need?"
    ids = [o["id"] for o in payload["options"]]
    assert LIVE_SERVICE_IDS.issubset(set(ids))
    text = service_selection.clarification_text()
    assert "Premium Wash & Fold" in text
    assert "Deep Carpet & Curtain Care" in text


def test_no_clarification_once_service_known():
    d = extract_customer_order_details("I need dry cleaning for two suits")
    assert service_selection.needs_service_clarification(d) is False


# --- unit type + manual quote ----------------------------------------------
def test_unit_types_from_catalog():
    assert service_by_id("premium_wash_fold")["unit_type"] == "bag"
    assert service_by_id("artisan_shoe_restoration")["unit_type"] == "pair"
    assert service_by_id("luxe_bed_bath_care")["unit_type"] == "set"
    assert service_by_id("deep_carpet_curtain_care")["unit_type"] == "sqm"


def test_manual_quote_services_flagged():
    for sid in ("luxury_bag_spa", "tailoring_alterations", "deep_carpet_curtain_care"):
        assert service_by_id(sid)["requires_manual_quote"] is True
    for sid in ("premium_wash_fold", "boutique_clean_press", "steam_pressing_only"):
        assert service_by_id(sid)["requires_manual_quote"] is False


def test_extraction_carries_unit_and_manual_quote():
    d = extract_customer_order_details("I need carpet cleaning")
    assert d.unit_type == "sqm"
    assert d.requires_manual_quote is True


# --- pricing: never invent a manual-quote total ----------------------------
def test_estimate_amount_for_per_item_service():
    d = OrderDetails(
        service_key="boutique_clean_press",
        service_label="Boutique Clean & Press",
        unit_type="item",
        items=[{"item": "Suit", "quantity": 2}],
    )
    # 2 items x from-11 AED, floored at the 11 minimum -> 22.
    assert orders_repo._estimate_amount(d) == 22.0


def test_estimate_amount_none_for_manual_quote_service():
    d = OrderDetails(
        service_key="deep_carpet_curtain_care",
        service_label="Deep Carpet & Curtain Care",
        unit_type="sqm",
        requires_manual_quote=True,
        items=[{"item": "Carpet", "quantity": 1}],
    )
    assert orders_repo._estimate_amount(d) is None


# --- repo mapping: selected service is persisted + shown on the dashboard ---
def test_order_row_maps_service_fields_to_dashboard_shape():
    # Simulate a Supabase orders row written by the capture flow.
    row = {
        "id": "00000000-0000-0000-0000-000000000001",
        "order_id": "LC-TEST-1001",
        "conversation_id": None,
        "customer_name": "Amaan",
        "service": "Boutique Clean & Press",
        "service_id": "boutique_clean_press",
        "service_display_name": "Boutique Clean & Press",
        "unit_type": "item",
        "requires_manual_quote": False,
        "items": [{"item": "Suit", "quantity": 2}],
        "area": "Dubai Marina",
        "status": "active",
        "amount": 22.0,
    }
    read = orders_repo.to_read(row)
    assert read["service_type"] == "Boutique Clean & Press"
    assert read["service_id"] == "boutique_clean_press"
    assert read["service_display_name"] == "Boutique Clean & Press"
    assert read["unit_type"] == "item"
    assert read["requires_manual_quote"] is False
    assert read["items"] == ["2x Suit"]


# --- cross-surface sync -----------------------------------------------------
def test_seo_taxonomy_matches_backend():
    assert taxonomy_service_ids() == set(service_ids())
    assert set(seo_service_names()) == LIVE_SERVICE_NAMES


def test_taxonomy_sync_check_is_in_sync():
    report = check_taxonomy_sync()
    assert report["in_sync"] is True, report["mismatches"]


# --- API --------------------------------------------------------------------
async def test_service_taxonomy_api_lists_live_services(client):
    resp = await client.get("/api/service-taxonomy")
    assert resp.status_code == 200
    body = resp.json()
    ids = {s["service_id"] for s in body["services"]}
    assert ids == LIVE_SERVICE_IDS
    assert body["promotional_items"]  # verified promo prices are exposed
    assert body["service_promises"]


async def test_service_taxonomy_health_reports_in_sync(client):
    resp = await client.get("/api/service-taxonomy/health")
    assert resp.status_code == 200
    assert resp.json()["in_sync"] is True


async def test_service_taxonomy_options_endpoint(client):
    resp = await client.get("/api/service-taxonomy/options")
    assert resp.status_code == 200
    ids = [o["id"] for o in resp.json()["options"]]
    assert LIVE_SERVICE_IDS.issubset(set(ids))
    assert "help_me_choose" in ids
