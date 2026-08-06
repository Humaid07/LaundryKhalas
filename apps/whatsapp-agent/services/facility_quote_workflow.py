"""Facility quote workflow — submit → price → operations-review gate → customer.

Ties the existing facility_quote_revisions scaffold to the immutable markup
snapshot (quote_pricing) and the customer approval store. The facility submits ONLY
its fee + findings; the backend computes the customer price and decides whether
Operations must review before the customer sees it. Reuses services/quote_revision.py
(state machine) — no parallel quotation system.
"""
from __future__ import annotations

from db.repositories import (
    customer_quote_repo,
    facility_issues_repo,
    facility_pricing_repo,
    facility_quote_revisions_repo,
    order_events_repo,
)
from services import provisional_pricing, quote_pricing, quote_revision


async def price_facility_quote(
    *,
    revision_id: str,
    order_id: str,
    order_item_id: str | None,
    quote_version: int,
    facility_fee,
    service_code: str | None = None,
    bespoke: bool = False,
    discount_percentage=0,
    delivery_charge=0,
    express_surcharge=0,
    currency: str = "AED",
    pricing_rule_version: str | None = None,
    luxury: bool = False,
    restoration: bool = False,
    wedding: bool = False,
    scope_revised: bool = False,
    severe_damage: bool = False,
    open_complaint: bool = False,
    review_config: dict | None = None,
    is_test_data: bool = False,
) -> dict:
    """Validate the facility fee, compute the customer price via the approved margin
    rule, persist an immutable snapshot, and decide whether Operations must review.
    Returns ``{ok, reason?, snapshot, requires_operations_review, review_reasons}``."""
    if not quote_revision.validate_fee(facility_fee):
        return {"ok": False, "reason": "invalid_fee"}

    margin_rule = await _margin_rule(service_code, bespoke)
    snapshot = quote_pricing.calculate_customer_price_from_facility_quote(
        facility_fee, margin_rule=margin_rule, discount_percentage=discount_percentage,
        delivery_charge=delivery_charge, express_surcharge=express_surcharge, currency=currency,
        markup_rule_id=(margin_rule or {}).get("id") or (margin_rule or {}).get("code"),
        pricing_rule_version=pricing_rule_version)

    requires_review, reasons = quote_pricing.requires_operations_review(
        snapshot, luxury=luxury, restoration=restoration, wedding=wedding,
        scope_revised=scope_revised, severe_damage=severe_damage, open_complaint=open_complaint,
        config=review_config)

    stored = await customer_quote_repo.create_snapshot(
        quote_revision_id=revision_id, order_id=order_id, order_item_id=order_item_id,
        quote_version=quote_version, snapshot=snapshot, is_test_data=is_test_data)

    return {
        "ok": True,
        "snapshot": stored,
        "final_customer_price": snapshot["final_customer_price"],
        "currency": snapshot["currency"],
        "requires_operations_review": requires_review,
        "review_reasons": reasons,
    }


async def _margin_rule(service_code: str | None, bespoke: bool) -> dict | None:
    """The approved margin rule (backend authoritative). Best-effort — defaults to
    the 30% rule inside quote_pricing when unavailable."""
    try:
        return await facility_pricing_repo.get_margin_rule(bespoke=bespoke, service_code=service_code)
    except Exception:  # noqa: BLE001 — a missing rule falls back to the documented default
        return None


async def record_customer_decision(
    *, order_id: str, order_item_id: str | None, revision_id: str | None,
    quote_version: int, decision: str, final_price=None, scope: str | None = None,
    customer_message_id: str | None = None, is_test_data: bool = False,
) -> dict | None:
    """Record the customer's decision on a SPECIFIC quote version (idempotent).
    An old approval never approves a newer version."""
    return await customer_quote_repo.record_approval(
        order_id=order_id, order_item_id=order_item_id, quote_revision_id=revision_id,
        quote_version=quote_version, decision=decision, final_price=final_price, scope=scope,
        customer_message_id=customer_message_id, is_test_data=is_test_data)


async def get_pending_quote_for_order(order_uuid: str) -> dict | None:
    """The facility-confirmed price awaiting the customer's approval for THIS order,
    with the short relay text. Customer-safe (no fee/markup). None when nothing is
    pending — the agent must never invent a facility price."""
    rev = await facility_quote_revisions_repo.latest_pending_for_order(order_uuid)
    if not rev or rev.get("customer_price") is None:
        return None
    present = provisional_pricing.present_price(
        provisional_pricing.CUSTOMER_PRICE_SENT, currency=rev.get("currency", "AED"),
        exact=rev["customer_price"])
    return {
        "revision_id": rev["id"],
        "order_item_id": rev.get("order_item_id"),
        "quote_version": rev.get("quote_version", 1),
        "final_price": rev["customer_price"],
        "currency": rev.get("currency", "AED"),
        "scope": rev.get("reason"),
        "relay_text": present,
    }


async def apply_customer_decision(
    order_uuid: str, order_ref: str | None, *, decision: str,
    customer_message_id: str | None = None, actor_label: str = "Customer",
    is_test_data: bool = False,
) -> dict:
    """Apply the customer's yes/no to the ORDER's pending facility quote: record the
    versioned approval (idempotent), advance the revision, and — on approval —
    resolve the blocking issue so the facility may proceed. ``decision`` is
    'approved' or 'declined'."""
    rev = await facility_quote_revisions_repo.latest_pending_for_order(order_uuid)
    if not rev:
        return {"ok": False, "reason": "no_pending_quote"}
    approved = str(decision).lower().startswith("approv") or str(decision).lower() in ("yes", "proceed")
    app_decision = "APPROVED" if approved else "DECLINED"
    rev_status = "customer_approved" if approved else "customer_rejected"

    await customer_quote_repo.record_approval(
        order_id=order_uuid, order_item_id=rev.get("order_item_id"), quote_revision_id=rev["id"],
        quote_version=rev.get("quote_version", 1), decision=app_decision,
        final_price=rev.get("customer_price"), customer_message_id=customer_message_id,
        is_test_data=is_test_data)
    await facility_quote_revisions_repo.set_customer_decision(rev["id"], status=rev_status)

    issue_id = rev.get("facility_issue_id")
    if approved and issue_id:
        # Customer approved the revised price → unblock the facility to proceed.
        await facility_issues_repo.set_status(issue_id, "resolved")
    if order_uuid:
        await order_events_repo.create(
            order_uuid=order_uuid,
            event_type="facility_processing_authorized" if approved else "customer_quote_declined",
            actor_type="customer", actor_name=actor_label,
            notes=("Customer approved the facility-confirmed price." if approved
                   else "Customer declined the facility-confirmed price."),
            metadata={"revision_id": rev["id"], "quote_version": rev.get("quote_version", 1),
                      "final_price": rev.get("customer_price")})
    return {"ok": True, "decision": app_decision, "revision_id": rev["id"],
            "quote_version": rev.get("quote_version", 1), "final_price": rev.get("customer_price"),
            "unblocked": bool(approved and issue_id)}
