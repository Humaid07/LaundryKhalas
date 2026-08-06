"""Centralized facility ORDER-VIEW serializer (pure, PII-safe, testable).

ONE place that assembles the full facility order card + detail payload from
already-fetched structured data (order row, structured notes, photos, issues,
fee snapshot, review acknowledgement). It decides:

* the visual hierarchy contract (order header → required work → notes → photos →
  items → pickup → fee → issues → actions),
* which customer/location fields are shared (delegated to the FACILITY_SHARE_*
  config via services/facility_handoff),
* the operational priority of each note (services/note_priority),
* the grounded Required Work list (services/required_work),
* the version signals + review-acknowledgement freshness,
* the contextual next action + full available-actions list.

It NEVER exposes margin, Stripe fees, other facilities' rates, internal routing,
customer payment amount, or the raw conversation. The asyncpg wiring that gathers
the inputs lives in api/facility.py + the facility repos; everything here is a
pure function over dicts so the whole contract is unit-testable.
"""

from __future__ import annotations

from services import note_priority, required_work
from services import item_details
from services.facility_handoff import (
    FacilityShareConfig,
    _typed_address,  # reuse the exact typed-address whitelist
)
from services import order_store

# --- Note category → facility section ------------------------------------
# Sections are emitted in this order; the frontend renders them top-to-bottom.
_NOTE_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("customer_instructions", ("OTHER_OPERATIONAL_NOTE",)),
    ("pickup_instructions", ("PICKUP_INSTRUCTION",)),
    ("delivery_instructions", ("DELIVERY_INSTRUCTION",)),
    ("access_instructions", ("ACCESS_INSTRUCTION",)),
    ("contact_preferences", ("CONTACT_PREFERENCE",)),
    ("timing_preferences", ("TIMING_PREFERENCE",)),
    ("item_handling", ("ITEM_HANDLING",)),
    ("stains", ("STAIN_NOTE",)),
    ("existing_damage", ("EXISTING_DAMAGE",)),
    ("special_care", ("SPECIAL_CARE",)),
    ("inspection_requirements", ("INSPECTION_REQUIREMENT",)),
    ("operations_notes", ("FACILITY_INSTRUCTION",)),
)
_ALL_SECTION_KEYS = tuple(k for k, _ in _NOTE_SECTIONS) + ("amendments",)

# --- Facility action vocabulary ------------------------------------------
# label + which order statuses expose the action. Status-changing actions mirror
# services/facility_orders.ALLOWED_ACTIONS (single source for what a facility may
# actually do); non-status actions are always available in the right context.
_ACTION_LABELS: dict[str, str] = {
    "accept": "Accept Order",
    "mark_received": "Mark Order Received",
    "start_cleaning": "Start Processing",
    "move_to_qc": "Move to Quality Check",
    "mark_ready": "Mark Ready for Delivery",
    "confirm_handoff": "Confirm Handoff to Driver",
    "raise_issue": "Raise an Issue",
    "acknowledge_review": "Acknowledge Review",
}
# status → status-changing actions valid from it (mirrors ALLOWED_ACTIONS.from).
_STATUS_ACTIONS: dict[str, tuple[str, ...]] = {
    "active": ("accept", "mark_received"),
    "pickup_scheduled": ("accept", "mark_received"),
    "picked_up": ("start_cleaning",),
    "in_cleaning": ("mark_ready", "move_to_qc"),
    "ready_for_delivery": ("confirm_handoff",),
}
# The single primary "next required action" per status.
_PRIMARY_ACTION: dict[str, str] = {
    "active": "accept",
    "pickup_scheduled": "accept",
    "picked_up": "start_cleaning",
    "in_cleaning": "mark_ready",
    "ready_for_delivery": "confirm_handoff",
}
# Actions gated behind an up-to-date review acknowledgement.
_ACK_GATED = frozenset({"start_cleaning"})


# =========================================================================
# Version signals + review freshness
# =========================================================================
def compute_versions(*, notes_all: list[dict] | None, photo_count: int) -> dict[str, int]:
    """Deterministic integer version signals for an order's reviewable content.

    * ``notes_version`` — total order_notes rows (monotonic: every add / amendment
      / correction inserts a row, so a new instruction always bumps it).
    * ``photo_version`` — live (non-deleted) photo count (a new photo bumps it).
    * ``order_version`` — count of post-confirmation amendment notes (a new
      amendment / revised instruction bumps it).
    """
    notes_all = notes_all or []
    amendments = sum(1 for n in notes_all if n.get("is_amendment"))
    return {
        "notes_version": len(notes_all),
        "photo_version": int(photo_count or 0),
        "order_version": amendments,
    }


def build_review_ack(review: dict | None, current: dict[str, int]) -> dict:
    """Freshness of the facility's "details reviewed" acknowledgement.

    ``up_to_date`` is True only when a live acknowledgement exists AND every stored
    version still matches the current content (and it was not explicitly
    invalidated). A mismatch yields a human ``invalidation_reason`` naming what
    changed, so the UI can require a fresh acknowledgement before processing.
    """
    if not review:
        return {
            "acknowledged": False,
            "up_to_date": False,
            "required": True,
            "current_versions": current,
        }
    stored = {
        "notes_version": int(review.get("notes_version") or 0),
        "photo_version": int(review.get("photo_version") or 0),
        "order_version": int(review.get("order_version") or 0),
    }
    changed: list[str] = []
    if review.get("invalidated_at"):
        changed.append(review.get("invalidation_reason") or "review invalidated")
    if current["notes_version"] != stored["notes_version"]:
        changed.append("notes updated")
    if current["photo_version"] != stored["photo_version"]:
        changed.append("new photo added")
    if current["order_version"] != stored["order_version"]:
        changed.append("order amended")
    return {
        "acknowledged": True,
        "up_to_date": not changed,
        "required": bool(changed),
        "acknowledged_at": review.get("acknowledged_at"),
        "acknowledged_versions": stored,
        "current_versions": current,
        "invalidation_reason": "; ".join(changed) if changed else None,
    }


# =========================================================================
# Notes (grouped, prioritised)
# =========================================================================
def _note_dto(note: dict) -> dict:
    category = str(note.get("category", "")).upper()
    text = note.get("text")
    priority = note_priority.classify(category, text, explicit=note.get("priority"))
    return {
        "id": str(note.get("id") or note.get("note_id") or ""),
        "category": category,
        "priority": priority,
        "text": text,
        "item_id": note.get("order_item_id") or note.get("item_id"),
        "source": note.get("source"),
        "source_message_id": note.get("source_message_id"),
        "customer_confirmed": bool(note.get("customer_confirmed")),
        "is_amendment": bool(note.get("is_amendment")),
        "created_at": note.get("created_at"),
        "updated_at": note.get("updated_at"),
    }


def build_notes(active_notes: list[dict] | None) -> tuple[dict, list[dict]]:
    """Return (grouped-notes-by-section, flat-critical-list).

    Only ACTIVE notes are included. Each note is tagged with a derived priority.
    Post-confirmation amendments are additionally collected under ``amendments``.
    """
    actives = [n for n in (active_notes or []) if str(n.get("status", "ACTIVE")).upper() == "ACTIVE"]
    dtos = [_note_dto(n) for n in actives]
    by_category: dict[str, list[dict]] = {}
    for d in dtos:
        by_category.setdefault(d["category"], []).append(d)

    grouped: dict[str, list[dict]] = {}
    for section, cats in _NOTE_SECTIONS:
        bucket: list[dict] = []
        for c in cats:
            bucket.extend(by_category.get(c, []))
        if bucket:
            grouped[section] = bucket
    grouped["amendments"] = [d for d in dtos if d["is_amendment"]]

    critical = [d for d in dtos if d["priority"] == "CRITICAL"]
    return grouped, critical


# =========================================================================
# Photos (facility-facing DTO, per-item linkage)
# =========================================================================
_STAGE_SOURCE = {
    "intake": "FACILITY_BEFORE_PROCESSING",
    "pre_dispatch": "FACILITY_AFTER_PROCESSING",
    "issue_photo": "FACILITY_ISSUE",
    "damage_report": "INSPECTION",
    "customer_reference": "CUSTOMER",
}


def _photo_dto(row: dict) -> dict:
    stage = row.get("stage")
    source = row.get("source") or _STAGE_SOURCE.get(str(stage), "OPERATIONS")
    return {
        "id": str(row.get("id")),
        "item_id": row.get("order_item_id"),
        "stage": stage,
        "source": source,
        "media_type": row.get("content_type") or "image",
        "caption": row.get("caption"),
        "uploaded_by": row.get("uploaded_by") or row.get("uploaded_by_name"),
        "created_at": row.get("created_at"),
        "provider": row.get("provider") or row.get("storage_provider"),
        "url": row.get("url") or row.get("public_url"),
        "width": row.get("width"),
        "height": row.get("height"),
    }


def build_photos(photos: list[dict] | None) -> dict:
    """Facility-facing photo list, split into per-item and general order photos.

    Never returns a storage key; each photo is addressed by id (the frontend
    streams bytes via the Bearer content proxy or a short-lived signed URL)."""
    dtos = [_photo_dto(p) for p in (photos or [])]
    return {
        "all": dtos,
        "by_item": {i: [d for d in dtos if str(d["item_id"]) == str(i)]
                    for i in {d["item_id"] for d in dtos if d["item_id"]}},
        "general": [d for d in dtos if not d["item_id"]],
        "count": len(dtos),
    }


# =========================================================================
# Items (rich, category-aware per-line DTO)
# =========================================================================
def build_items(order: dict, fee_by_item: dict | None, photos_by_item: dict | None) -> list[dict]:
    """Rich, category-aware per-item DTOs (delegates to services.item_details).

    ``fee_by_item`` / ``photos_by_item`` are keyed by the SAME item id the detail
    builder derives (``id`` → ``item_code`` → ``line-<index>``), so per-item fees
    and photo counts line up."""
    service = order.get("service_display_name") or order.get("service_name_snapshot") or order.get("service") or ""
    status = order.get("status")
    raw = order.get("line_items") if isinstance(order.get("line_items"), list) and order.get("line_items") else order.get("items") or []
    if isinstance(raw, str):
        raw = [raw]
    out: list[dict] = []
    for idx, it in enumerate(raw):
        item = it if isinstance(it, dict) else {"name": str(it)}
        item_id = str(item.get("id") or item.get("item_code") or f"line-{idx}")
        out.append(item_details.build_item_detail(
            item,
            index=idx,
            order_service=service,
            order_status=status,
            fee=(fee_by_item or {}).get(item_id),
            photo_count=len((photos_by_item or {}).get(item_id, [])),
        ))
    return out


# =========================================================================
# Finance (facility fee only — never margin/Stripe/customer price)
# =========================================================================
def build_facility_finance(fee_snapshot: dict | None, order: dict) -> dict:
    """Facility payout-facing finance ONLY. Explicitly whitelisted: fee total,
    per-item fee, currency, payout status. There is no path for margin / Stripe
    fee / customer amount / other facilities' rates to appear — they are never
    read here."""
    snap = fee_snapshot if isinstance(fee_snapshot, dict) else {}
    total = order.get("facility_fee_total")
    if total is None:
        total = snap.get("facility_cost")
    per_item = []
    for line in (snap.get("lines") or snap.get("items") or []):
        if isinstance(line, dict):
            per_item.append({
                "name": line.get("name") or line.get("item"),
                "fee": line.get("facility_cost") if line.get("facility_cost") is not None else line.get("cost"),
            })
    return {
        "fee_total": float(total) if isinstance(total, (int, float)) else None,
        "currency": order.get("facility_fee_currency") or snap.get("currency") or "AED",
        "per_item": per_item,
        "complete": bool(snap.get("complete")) if "complete" in snap else (total is not None),
        "payout_status": order.get("payout_status") or "pending",
    }


def _fee_by_item(fee_snapshot: dict | None) -> dict:
    snap = fee_snapshot if isinstance(fee_snapshot, dict) else {}
    out: dict = {}
    for line in (snap.get("lines") or snap.get("items") or []):
        if isinstance(line, dict) and (line.get("id") or line.get("item_code")):
            out[str(line.get("id") or line.get("item_code"))] = (
                line.get("facility_cost") if line.get("facility_cost") is not None else line.get("cost")
            )
    return out


# =========================================================================
# Actions
# =========================================================================
def build_actions(status: str, review_ack: dict) -> tuple[list[dict], dict | None]:
    """Contextual (available_actions, next_action) for the current status.

    Status-changing actions are only those the backend actually permits from this
    status. ``start_cleaning`` (Start Processing) is disabled until the review is
    acknowledged and up to date."""
    up_to_date = bool(review_ack.get("up_to_date"))
    actions: list[dict] = []
    for action in _STATUS_ACTIONS.get(status, ()):  # status-changing
        gated = action in _ACK_GATED and not up_to_date
        actions.append({
            "action": action,
            "label": _ACTION_LABELS.get(action, action),
            "enabled": not gated,
            "requires_ack": action in _ACK_GATED,
            "reason": "Acknowledge the order details, notes and photos first."
                      if gated else None,
            # A gated action is never the primary CTA — the acknowledge action is.
            "primary": _PRIMARY_ACTION.get(status) == action and not gated,
        })
    # Always-available contextual actions (non-terminal only).
    if status not in ("completed", "cancelled", "abandoned"):
        if not up_to_date:
            actions.append({"action": "acknowledge_review", "label": _ACTION_LABELS["acknowledge_review"],
                            "enabled": True, "requires_ack": False, "reason": None,
                            "primary": True})
        actions.append({"action": "raise_issue", "label": _ACTION_LABELS["raise_issue"],
                        "enabled": True, "requires_ack": False, "reason": None, "primary": False})

    next_action = next((a for a in actions if a.get("primary")), None)
    if next_action is None:
        next_action = next((a for a in actions if a.get("enabled")), None)
    return actions, next_action


# =========================================================================
# Order header helpers
# =========================================================================
def _priority(order: dict) -> str:
    if order.get("is_express") or order.get("express_selected"):
        return "EXPRESS"
    hay = f"{order.get('turnaround_text','')} {order.get('service','')}".lower()
    return "EXPRESS" if "express" in hay else "STANDARD"


def _item_count(order: dict) -> int:
    raw = order.get("line_items") if isinstance(order.get("line_items"), list) and order.get("line_items") else order.get("items") or []
    if isinstance(raw, str):
        return 1
    total = 0
    for it in raw:
        q = it.get("quantity") if isinstance(it, dict) else None
        try:
            total += int(float(q)) if q is not None else 1
        except (TypeError, ValueError):
            total += 1
    return total


def _pickup_window(order: dict) -> dict:
    return {
        "start": order.get("pickup_start_time") or order.get("pickup_slot"),
        "end": order.get("pickup_end_time"),
        "date": (str(order["pickup_date"]) if order.get("pickup_date") else None),
        "label": order.get("pickup_slot_label") or order.get("pickup_slot"),
    }


def _customer_block(order: dict, customer: dict | None, share: FacilityShareConfig) -> dict:
    block: dict = {}
    name = order.get("customer_name") or (customer or {}).get("customer_name") or (customer or {}).get("display_name")
    if share.customer_name and name:
        block["name"] = name
    if share.customer_phone:
        phone = (customer or {}).get("normalized_contact_number") or (customer or {}).get("phone_e164")
        if phone:
            block["phone"] = phone
    return block


def _location_block(order: dict, share: FacilityShareConfig) -> dict:
    block: dict = {}
    if share.typed_address:
        addr = _typed_address(order)
        if addr:
            block["typed_address"] = addr
    else:
        block["area"] = order.get("pickup_area") or order.get("area")
        block["city"] = order.get("city")
    if share.location_pin and order.get("pickup_latitude") is not None and order.get("pickup_longitude") is not None:
        block["pin"] = {
            "latitude": order.get("pickup_latitude"),
            "longitude": order.get("pickup_longitude"),
            "type": order.get("location_type"),
            "name": order.get("location_name"),
        }
    block["pin_status"] = order.get("location_pin_status") or (
        "received" if order.get("pickup_latitude") is not None else "missing")
    return block


# =========================================================================
# Top-level assembler
# =========================================================================
def build_facility_order_view(
    *,
    order: dict,
    active_notes: list[dict] | None,
    notes_all: list[dict] | None,
    photos: list[dict] | None,
    issues: list[dict] | None,
    fee_snapshot: dict | None,
    review: dict | None,
    share: FacilityShareConfig,
    customer: dict | None = None,
    quote_revisions: list[dict] | None = None,
) -> dict:
    """Assemble the complete, PII-safe facility order-view payload.

    ``order`` is the raw orders row (this function reads only operational fields).
    All customer/location exposure is config-gated; margin/Stripe/customer price
    are never read.
    """
    status = order.get("status") or "active"
    active_notes = active_notes or []

    versions = compute_versions(notes_all=notes_all, photo_count=len(photos or []))
    review_ack = build_review_ack(review, versions)
    grouped_notes, critical_notes = build_notes(active_notes)
    photo_block = build_photos(photos)
    fee_by_item = _fee_by_item(fee_snapshot)
    items = build_items(order, fee_by_item, photo_block["by_item"])
    actions, next_action = build_actions(status, review_ack)

    return {
        "order": {
            "id": str(order.get("id")) if order.get("id") else None,
            "order_number": order.get("order_id"),
            "status": status,
            "status_label": order_store.status_label(status),
            "priority": _priority(order),
            "service_summary": order.get("service_display_name") or order.get("service"),
            "service_id": order.get("service_id"),
            "required_work_summary": required_work.build_required_work(order, active_notes),
            "pickup_window": _pickup_window(order),
            "expected_completion_at": order.get("estimated_delivery_end_at")
                                      or order.get("estimated_delivery_start_at"),
            "expected_completion_text": order.get("estimated_delivery_text"),
            "turnaround_text": order.get("turnaround_text"),
            "item_count": _item_count(order),
            "currency": order.get("facility_fee_currency") or "AED",
        },
        "items": items,
        "notes": grouped_notes,
        "critical_notes": critical_notes,
        "photos": photo_block,
        "customer": _customer_block(order, customer, share),
        "location": _location_block(order, share),
        "facility_finance": build_facility_finance(fee_snapshot, order),
        "issues": issues or [],
        "available_actions": actions,
        "next_action": next_action,
        "review_acknowledgement": review_ack,
        "quote_revisions": quote_revisions or [],
        "versions": versions,
    }


__all__ = [
    "build_facility_order_view",
    "compute_versions",
    "build_review_ack",
    "build_notes",
    "build_photos",
    "build_items",
    "build_facility_finance",
    "build_actions",
]
