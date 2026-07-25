"""Claude-orchestrated booking via CONTROLLED backend write-tools.

Design contract (integration spec §§9-11, CLAUDE.md §5-§9):
  * Claude may DECIDE which field to capture next and phrase the reply, but it
    NEVER writes the database directly. Every mutation goes through a narrow,
    schema-validated tool here, which:
      - validates the value with the SAME deterministic resolvers the
        deterministic FSM uses (services/booking_flow.py) — no reimplementation,
        so validation can't drift;
      - is scoped to ONE conversation/order (the BookingContext is bound to a
        single conversation_id + order_uuid) → conversation ownership by
        construction; a tool can never touch another customer's order;
      - persists via the existing orders_repo helpers (column-whitelisted,
        idempotent confirm) — the DB stays the single source of truth for which
        fields are complete;
      - returns a structured result + the refreshed workflow state, or a safe
        error the model turns into a clarification question.
  * There is NO unrestricted tool (no execute_sql / update_any_order).
  * The pricing/VAT/SLA math is the backend's (services.pricing / delivery); the
    model only reads the numbers.

Persistence is injected (``repo``) so the whole layer is unit-testable offline
without a database — production passes ``db.repositories.orders_repo``.
"""
from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass, field
from typing import Any

import structlog

from agents.whatsapp_agent import tools as slot_tools
from services import booking_flow as bf
from services import catalogue, order_store

logger = structlog.get_logger(__name__)


# --- Context (binds every tool call to ONE conversation's workflow) ---------
@dataclass
class BookingContext:
    """Everything a booking turn needs, scoped to a single conversation/order.

    ``repo`` is the persistence adapter (production: db.repositories.orders_repo;
    tests: an in-memory fake). ``available_slots`` is a callable returning the
    bookable pickup slots (as the FSM expects). ``today`` anchors date parsing.
    """
    conversation_id: str
    order_uuid: str
    repo: Any
    today: _dt.date
    available_slots: Any                       # async callable -> list[slot dict]
    customer: dict | None = None
    profile_name: str | None = None
    verified_name: str | None = None
    tool_calls: list[str] = field(default_factory=list)


# --- Structured workflow-state block (spec §7) ------------------------------
def _booking_from_row(row: dict, ctx: BookingContext) -> bf.Booking:
    return bf.Booking(
        conversation_state=row.get("conversation_state"),
        customer_name=row.get("customer_name"),
        service_id=row.get("service_id"),
        service_name_snapshot=row.get("service_name_snapshot") or row.get("service"),
        line_items=row.get("line_items"),
        browse_service_code=row.get("browse_service_code"),
        pending_item_code=row.get("pending_item_code"),
        pickup_date=row.get("pickup_date"),
        pickup_slot_id=row.get("pickup_slot_id"),
        pickup_slot_label=row.get("pickup_slot"),
        pickup_address=row.get("pickup_address"),
        pickup_area=row.get("pickup_area") or row.get("area"),
        pickup_instruction_code=row.get("pickup_instruction_code"),
        pickup_instruction_text=row.get("pickup_instruction_text"),
        whatsapp_profile_name=ctx.profile_name,
        verified_name=ctx.verified_name,
    )


def workflow_state_block(row: dict) -> dict:
    """Concise, PII-light structured state for the model (spec §7). Internal DB
    UUIDs are NOT exposed; the public order number is included for reference."""
    line_items = row.get("line_items") or []
    items = [
        {"item_code": li.get("item_code"), "name": li.get("name"),
         "quantity": li.get("quantity"), "line_kind": li.get("line_kind")}
        for li in line_items
    ]
    have_service = bool(row.get("service_id") or items)
    missing = []
    if not have_service:
        missing.append("service_items")
    if not row.get("pickup_date"):
        missing.append("pickup_date")
    if not row.get("pickup_slot"):
        missing.append("pickup_time_window")
    if not (row.get("pickup_address") or row.get("pickup_area") or row.get("area")):
        missing.append("pickup_address")
    if not row.get("customer_name"):
        missing.append("customer_name")
    d = row.get("pickup_date")
    return {
        "order_number": row.get("order_id"),
        "workflow_state": row.get("conversation_state"),
        "status": row.get("status"),
        "customer": {"confirmed_name": row.get("customer_name")},
        "order": {
            "service_category": row.get("service_name_snapshot") or row.get("service"),
            "service_items": items,
            "pickup_date": d.isoformat() if isinstance(d, _dt.date) else (d or None),
            "pickup_time_window": row.get("pickup_slot"),
            "pickup_address_present": bool(row.get("pickup_address")),
            "pickup_area": row.get("pickup_area") or row.get("area"),
            "special_instructions": row.get("pickup_instruction_text"),
            "estimated_total_incl_vat": (
                float(row["estimated_total"]) if row.get("estimated_total") is not None else None
            ),
            "pricing_is_estimated": bool(row.get("pricing_is_estimated")),
        },
        "missing_fields": missing,
        "ready_to_confirm": not missing,
    }


# --- Tool schemas -----------------------------------------------------------
BOOKING_TOOL_SCHEMAS: list[dict] = [
    {"name": "get_current_workflow",
     "description": "Return the current booking's structured state (fields collected + still missing). "
                    "Call this first if unsure what has been captured. Never assume a field is set.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "list_service_categories",
     "description": "List the service categories the customer can choose from.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "list_service_items",
     "description": "List the items in a chosen service category (by its code from list_service_categories).",
     "input_schema": {"type": "object",
                      "properties": {"category_code": {"type": "string"}},
                      "required": ["category_code"], "additionalProperties": False}},
    {"name": "save_customer_name",
     "description": "Save the customer's confirmed name. Only call with a name the customer actually gave — "
                    "never a WhatsApp profile name they didn't confirm.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}},
                      "required": ["name"], "additionalProperties": False}},
    {"name": "save_service_selection",
     "description": "Set the service category the customer wants (free text like 'dry cleaning' or a category code). "
                    "Rejected if it doesn't resolve to a real category, or ambiguous (then ask the customer).",
     "input_schema": {"type": "object", "properties": {"service": {"type": "string"}},
                      "required": ["service"], "additionalProperties": False}},
    {"name": "save_order_item",
     "description": "Add an item to the order with a quantity (and measure in sqm for per-sqm items). "
                    "Validated against the catalogue; pricing is recomputed by the backend.",
     "input_schema": {"type": "object",
                      "properties": {"item": {"type": "string"},
                                     "quantity": {"type": "integer", "minimum": 1},
                                     "measure": {"type": "number"}},
                      "required": ["item", "quantity"], "additionalProperties": False}},
    {"name": "save_pickup_date",
     "description": "Save the pickup date. Accepts natural text ('tomorrow', 'Saturday', '27/07'); the backend "
                    "resolves it in Asia/Dubai and rejects past/invalid dates.",
     "input_schema": {"type": "object", "properties": {"date_text": {"type": "string"}},
                      "required": ["date_text"], "additionalProperties": False}},
    {"name": "save_pickup_time",
     "description": "Save the pickup time window from the available slots (by number, id, or label).",
     "input_schema": {"type": "object", "properties": {"slot": {"type": "string"}},
                      "required": ["slot"], "additionalProperties": False}},
    {"name": "save_pickup_address",
     "description": "Save the pickup address text. The backend extracts the area; coverage is confirmed by the team.",
     "input_schema": {"type": "object", "properties": {"address": {"type": "string"}},
                      "required": ["address"], "additionalProperties": False}},
    {"name": "save_special_instructions",
     "description": "Save optional pickup/handling instructions the customer gave.",
     "input_schema": {"type": "object", "properties": {"instructions": {"type": "string"}},
                      "required": ["instructions"], "additionalProperties": False}},
    {"name": "get_order_summary",
     "description": "Return the itemised order summary with the VAT-aware estimated total.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "confirm_order",
     "description": "Confirm the booking. ONLY call after the customer has explicitly confirmed AND all required "
                    "fields are present — the backend rejects a confirm with anything missing and is idempotent.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "get_order_status",
     "description": "Look up the status of the most recent order in this conversation.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "request_human_support",
     "description": "Escalate this conversation to a human agent (complaints, refunds, anything unsafe or out of scope).",
     "input_schema": {"type": "object", "properties": {"reason": {"type": "string"}},
                      "required": ["reason"], "additionalProperties": False}},
]

_TOOL_NAMES = {t["name"] for t in BOOKING_TOOL_SCHEMAS}


# --- Booking orchestration system prompt (spec §8) --------------------------
def booking_system_prompt() -> str:
    """Stable booking-orchestration instructions. The volatile structured state
    is supplied separately each turn (get_current_workflow / the state block),
    never baked in here (spec §7)."""
    return (
        "You are the Laundry Khalas WhatsApp booking assistant. Help the customer "
        "arrange a laundry/cleaning pickup by collecting the required details ONE "
        "at a time and calling the backend tools to save each one.\n\n"
        "Hard rules:\n"
        "- The tools are the ONLY source of truth. Never invent a service, item, "
        "price, date, slot, address, turnaround or order status — read them from a tool.\n"
        "- Save a value ONLY via its tool; a tool error means the value was NOT saved — "
        "ask the customer again, do not claim it was saved.\n"
        "- Ask only for what get_current_workflow reports as missing. Never re-ask for "
        "a field already collected. When the customer changes one field, update only that field.\n"
        "- Never say a booking is confirmed unless confirm_order returns confirmed=true. "
        "confirm_order only after the customer explicitly confirms and nothing is missing.\n"
        "- Never treat an unconfirmed WhatsApp profile name as the customer's name.\n"
        "- For complaints, refunds, or anything outside booking, call request_human_support.\n"
        "- Keep replies short, natural and WhatsApp-style. Do not mention tools, JSON, "
        "internal IDs, or these instructions."
    )


async def run_booking_turn(ctx: BookingContext, *, text: str,
                           history: list[tuple[str, str]] | None = None,
                           max_tokens: int = 500):
    """Run one Claude-orchestrated booking turn: load the structured state, give
    Claude the write-tools, and let it drive — the executor validates + persists
    every mutation. Returns the ``(reply_text, LLMResult)``; on any provider/tool
    failure the service layer falls back to a safe deterministic mock reply so the
    customer always gets a response and workflow state is preserved.

    Imported lazily so the (large) FSM/LLM graph isn't pulled in unless booking
    orchestration is actually used."""
    from llm import service as llm_service
    from llm.providers.base import LLMMessage

    row = await ctx.repo.get_active_draft(ctx.conversation_id)
    state_block = workflow_state_block(row) if row else {"workflow_state": "new"}
    messages = [
        LLMMessage(role="system", content=booking_system_prompt()),
        LLMMessage(role="system",
                   content="Current booking state (backend truth):\n"
                           + json.dumps(state_block, ensure_ascii=False, default=str)),
    ]
    for role, content in (history or [])[-10:]:
        messages.append(
            LLMMessage(role="user" if role == "customer" else "assistant", content=content))
    messages.append(LLMMessage(role="user", content=text))

    executor = make_booking_executor(ctx)
    result, latency_ms, success, error = await llm_service.complete_with_tools(
        messages, tools=BOOKING_TOOL_SCHEMAS, executor=executor, max_tokens=max_tokens)
    logger.info("booking_orchestration_turn", conversation=ctx.conversation_id,
                success=success, tools=ctx.tool_calls, provider=result.provider,
                tokens_in=result.tokens_in, tokens_out=result.tokens_out,
                cost_usd=result.cost_usd, error=error)
    return result.text, result


# --- Executor ---------------------------------------------------------------
def _ok(payload: dict) -> tuple[str, bool]:
    return json.dumps(payload, ensure_ascii=False, default=str), False


def _err(message: str) -> tuple[str, bool]:
    return json.dumps({"error": message}, ensure_ascii=False), True


def make_booking_executor(ctx: BookingContext):
    """Build the tool executor bound to ``ctx`` (one conversation/order). Returns
    an async ``execute(name, input) -> (result_json, is_error)`` for the tool
    loop. Every call re-reads the draft so decisions use current DB state."""

    async def _current_row() -> dict | None:
        # Always operate on THIS conversation's open draft — ownership by scope.
        return await ctx.repo.get_active_draft(ctx.conversation_id)

    async def _apply(updates: dict, state: str | None = None) -> dict | None:
        row = await _current_row()
        if row is None:
            return None
        new_state = state or row.get("conversation_state") or bf.WAITING_FOR_SERVICE
        return await ctx.repo.apply_booking_updates(row["id"], updates, new_state)

    async def execute(name: str, tool_input: dict) -> tuple[str, bool]:
        tool_input = tool_input or {}
        if name not in _TOOL_NAMES:
            logger.warning("booking_tool_unknown", tool=name)
            return _err(f"Unknown tool '{name}'.")
        ctx.tool_calls.append(name)
        try:
            return await _dispatch(name, tool_input)
        except Exception as exc:  # noqa: BLE001 - a tool must never crash the turn
            logger.warning("booking_tool_error", tool=name, error=str(exc))
            return _err("That step failed; ask the customer to rephrase or try again.")

    async def _dispatch(name: str, ti: dict) -> tuple[str, bool]:
        row = await _current_row()
        if row is None and name not in (
            "get_order_status", "request_human_support", "confirm_order"
        ):
            return _err("No active booking for this conversation.")

        if name == "get_current_workflow":
            return _ok({"workflow": workflow_state_block(row)})

        if name == "list_service_categories":
            return _ok({"categories": [
                {"code": c["code"], "name": c["name"], "description": c.get("description")}
                for c in catalogue.categories()]})

        if name == "list_service_items":
            code = str(ti.get("category_code", "")).strip()
            if not catalogue.category_by_code(code):
                return _err("Unknown category_code. Call list_service_categories first.")
            return _ok({"items": [
                {"item_code": it["item_code"], "name": it["canonical_name"],
                 "price_label": catalogue.item_price_label(it)}
                for it in catalogue.items_for_category(code)]})

        if name == "save_customer_name":
            name_val = bf.validate_name(str(ti.get("name", "")))
            if not name_val:
                return _err("That doesn't look like a valid name. Ask the customer for their name.")
            await _apply({"customer_name": name_val})
            return _ok({"saved": True, "customer_name": name_val,
                        "workflow": workflow_state_block(await _current_row())})

        if name == "save_service_selection":
            code, reason = bf.resolve_service(bf.Inbound(text=str(ti.get("service", ""))))
            if reason == "ambiguous":
                return _err("Ambiguous service — ask the customer to pick Clean & Press vs Press Only "
                            "(or a specific category from list_service_categories).")
            if reason != "ok" or not code:
                return _err("That service isn't in the catalogue. Show list_service_categories and ask.")
            cat = catalogue.category_by_code(code)
            await _apply({"service_id": code, "service": cat["name"],
                          "service_display_name": cat["name"],
                          "service_name_snapshot": cat["name"],
                          "catalogue_category_code": code,
                          "catalogue_category_name": cat["name"],
                          "_touch_service_selected_at": True},
                         state=bf.WAITING_FOR_ITEM)
            return _ok({"saved": True, "service_category": cat["name"], "category_code": code,
                        "workflow": workflow_state_block(await _current_row())})

        if name == "save_order_item":
            if not (row.get("service_id") or row.get("line_items")):
                return _err("No service category set yet — call save_service_selection first.")
            code, reason = bf.resolve_item(
                bf.Inbound(text=str(ti.get("item", ""))), None, row.get("service_id"))
            if reason == "ambiguous":
                return _err("Ambiguous item — ask the customer which specific item they mean.")
            if reason != "ok" or not code:
                return _err("That item isn't in the catalogue for this category. "
                            "Use list_service_items and ask the customer to choose.")
            item = catalogue.item_by_code(code)
            qty = int(ti.get("quantity") or 1)
            measure = ti.get("measure")
            if item.get("requires_measurement") and measure is None:
                return _err(f"{item['canonical_name']} is priced per sqm — ask the customer for the area (sqm).")
            booking = _booking_from_row(row, ctx)
            raw = bf._raw_lines(booking)
            raw.append({"item_code": code, "quantity": qty, "measure": measure})
            updates = bf._pricing_updates(
                raw, row.get("service_id"), row.get("service_name_snapshot") or row.get("service"))
            await _apply(updates, state=bf.WAITING_FOR_MORE_ITEMS)
            return _ok({"saved": True, "item": item["canonical_name"], "quantity": qty,
                        "workflow": workflow_state_block(await _current_row())})

        if name == "save_pickup_date":
            date, reason = bf.parse_pickup_date(
                bf.Inbound(text=str(ti.get("date_text", ""))), ctx.today)
            if reason == "past":
                return _err("That date is in the past — ask the customer for a future pickup date.")
            if reason != "ok" or not date:
                return _err("Couldn't understand that date — ask the customer for a clear pickup day.")
            await _apply({"pickup_date": date}, state=bf.WAITING_FOR_PICKUP_SLOT)
            return _ok({"saved": True, "pickup_date": date.isoformat(),
                        "workflow": workflow_state_block(await _current_row())})

        if name == "save_pickup_time":
            if not row.get("pickup_date"):
                return _err("Set the pickup date first (save_pickup_date) before the time window.")
            slots = await ctx.available_slots(
                row.get("pickup_date"), row.get("pickup_area"), row.get("service_id"))
            slot, reason = bf.resolve_slot(bf.Inbound(text=str(ti.get("slot", ""))), slots)
            if reason != "ok" or not slot:
                labels = [s.get("label") for s in slots]
                return _err(f"That time slot isn't available. Offer these: {labels}")
            await _apply({"pickup_slot_id": slot.get("slot_id"), "pickup_slot": slot.get("label")},
                         state=bf.WAITING_FOR_ADDRESS)
            return _ok({"saved": True, "pickup_time_window": slot.get("label"),
                        "workflow": workflow_state_block(await _current_row())})

        if name == "save_pickup_address":
            address = str(ti.get("address", "")).strip()
            if len(address) < 5:
                return _err("Address looks too short — ask the customer for a full pickup address.")
            area = slot_tools.extract_area(address)
            await _apply({"pickup_address": address, "pickup_area": area, "address_source": "customer"},
                         state=bf.WAITING_FOR_CONFIRMATION)
            return _ok({"saved": True, "area_recognised": area,
                        "workflow": workflow_state_block(await _current_row())})

        if name == "save_special_instructions":
            text = str(ti.get("instructions", "")).strip()
            await _apply({"pickup_instruction_text": text, "pickup_instruction_code": "custom"})
            return _ok({"saved": True, "workflow": workflow_state_block(await _current_row())})

        if name == "get_order_summary":
            from services import pricing
            booking = _booking_from_row(row, ctx)
            quote = pricing.calculate_estimate(bf._raw_lines(booking))
            return _ok({"summary_lines": pricing.format_quote_lines(quote),
                        "estimated_total_incl_vat": quote.estimated_total_including_vat,
                        "is_estimated": quote.is_estimated,
                        "workflow": workflow_state_block(row)})

        if name == "confirm_order":
            if row is None:
                # No open draft — a duplicate confirm after the booking already
                # flipped. Report the existing confirmed order idempotently
                # instead of creating anything (spec §10: no double side effects).
                latest = await ctx.repo.get_latest_for_conversation(ctx.conversation_id)
                if latest and latest.get("status") not in (
                    order_store.DRAFT, order_store.CANCELLED, order_store.ABANDONED
                ):
                    return _ok({"confirmed": True, "created_now": False,
                                "order_number": latest.get("order_id"),
                                "status": latest.get("status")})
                return _err("No active booking to confirm.")
            state = workflow_state_block(row)
            if state["missing_fields"]:
                return _err(f"Cannot confirm — still missing: {state['missing_fields']}. "
                            "Collect these first; do not tell the customer it's confirmed.")
            confirmed, created_now = await ctx.repo.confirm_booking(row["id"])
            if confirmed is None:
                return _err("Confirmation failed on the backend; escalate to a human.")
            await ctx.repo.set_conversation_state(confirmed["id"], bf.POST_ORDER)
            return _ok({"confirmed": True, "created_now": created_now,
                        "order_number": confirmed.get("order_id"),
                        "status": confirmed.get("status")})

        if name == "get_order_status":
            latest = await ctx.repo.get_latest_for_conversation(ctx.conversation_id)
            if not latest:
                return _ok({"found": False})
            return _ok({"found": True, "order_number": latest.get("order_id"),
                        "status": latest.get("status")})

        if name == "request_human_support":
            return _ok({"escalated": True,
                        "message": "Connect the customer with the team; do not attempt to resolve it yourself."})

        return _err(f"Unhandled tool '{name}'.")  # pragma: no cover

    return execute
