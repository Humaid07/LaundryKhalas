"""Grounded, read-only backend tools Claude may call while answering a
customer (task spec: "Claude requests a backend tool → backend validates and
executes → structured workflow is updated").

Design contract (CLAUDE.md §5-§9, task spec):
  * Every tool is READ-ONLY and reads the DETERMINISTIC engines (catalogue,
    pricing, delivery SLA, area gazetteer). None of them create/modify an
    order, take a payment, or advance the booking FSM — those stay in
    services/booking_flow.py and are never exposed to the model.
  * A tool NEVER invents data. When there is no confident match it says so and
    tells Claude to ask the customer / defer to the team, rather than guessing.
  * Every tool call is validated (name + inputs) and LOGGED here on the backend
    side (CLAUDE.md §11) — the model does not get to run arbitrary code.

Claude uses these to *understand and phrase* an answer with real figures; the
final reply is still Claude's, but the facts are the backend's.
"""
from __future__ import annotations

import json

import structlog

from agents.whatsapp_agent import tools as slot_tools
from services import catalogue, delivery

logger = structlog.get_logger(__name__)


# --- Tool schemas (Anthropic tool-use format) ------------------------------
# Order is stable (prompt-cache prefix) and each schema is strict-friendly
# (additionalProperties: false + required) so tool inputs validate exactly.
TOOL_SCHEMAS: list[dict] = [
    {
        "name": "lookup_item_price",
        "description": (
            "Look up the CURRENT catalogue price for a laundry/cleaning item the "
            "customer described (e.g. 'shirt', 'winter jacket', 'kandura'). Returns "
            "the exact per-unit price, or flags an item as priced-after-inspection "
            "or ambiguous. Use this before quoting ANY price — never state a price "
            "you did not get from this tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The item as the customer described it.",
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_service_categories",
        "description": (
            "List the service categories Laundry Khalas offers (Wash & Fold, Dry "
            "Cleaning, Press Only, etc.). Use when the customer asks what services "
            "are available."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "estimate_turnaround",
        "description": (
            "Estimate the delivery turnaround / SLA for an item or service the "
            "customer named (e.g. 'suit', 'wash and fold'). Returns the standard "
            "turnaround window and whether Express is available. Use for 'how long "
            "does it take' questions — never invent a turnaround."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The item or service to estimate turnaround for.",
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "check_service_area",
        "description": (
            "Check whether a pickup area the customer mentioned is a recognised "
            "Laundry Khalas service area. Returns the matched area or, if unknown, "
            "guidance to ask the customer and let the team confirm coverage."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "area": {
                    "type": "string",
                    "description": "The area / neighbourhood the customer mentioned.",
                }
            },
            "required": ["area"],
            "additionalProperties": False,
        },
    },
]

_TOOL_NAMES = {t["name"] for t in TOOL_SCHEMAS}


# --- Individual tool implementations ---------------------------------------
def _price_label_full(item: dict) -> dict:
    """Structured, honest price view of a single resolved catalogue item."""
    inspection = bool(item.get("requires_inspection"))
    starting = bool(item.get("is_starting_price"))
    measured = bool(item.get("requires_measurement"))
    firm = not (inspection or starting or measured) and item.get("current_price") is not None
    guidance = (
        "This is a firm per-unit price — you may quote it, and note prices exclude "
        "5% VAT unless stated."
        if firm
        else "This item is priced after inspection/measurement — do NOT quote an exact "
        "total; tell the customer the shown figure is a starting point and the team "
        "confirms the final price."
    )
    return {
        "match": "ok",
        "item_code": item["item_code"],
        "name": item["canonical_name"],
        "price_label": catalogue.item_price_label(item),
        "currency": item.get("currency") or catalogue.currency(),
        "is_firm_price": firm,
        "requires_inspection": inspection,
        "is_starting_price": starting,
        "requires_measurement": measured,
        "guidance": guidance,
    }


def _lookup_item_price(query: str) -> dict:
    codes, reason = catalogue.resolve_item_alias(query)
    if reason == "none" or not codes:
        return {
            "match": "none",
            "guidance": (
                "No catalogue item matched. Ask the customer to describe the item "
                "more specifically; do NOT invent a price."
            ),
        }
    if reason == "ambiguous":
        candidates = [
            {
                "item_code": c,
                "name": (catalogue.item_by_code(c) or {}).get("canonical_name", c),
                "price_label": catalogue.item_price_label(catalogue.item_by_code(c) or {}),
            }
            for c in codes
        ]
        return {
            "match": "ambiguous",
            "candidates": candidates,
            "guidance": "Multiple items match — ask the customer which one they mean.",
        }
    item = catalogue.item_by_code(codes[0])
    if not item:
        return {"match": "none", "guidance": "Item not found; ask the customer to clarify."}
    return _price_label_full(item)


def _list_service_categories() -> dict:
    return {
        "categories": [
            {"name": c["name"], "description": c.get("description")}
            for c in catalogue.categories()
        ]
    }


def _resolve_item_codes(query: str) -> list[str]:
    """Best-effort resolve free text to catalogue item code(s) for turnaround:
    a specific item first, else every item in a matched category."""
    codes, reason = catalogue.resolve_item_alias(query)
    if reason == "ok" and codes:
        return codes
    cat_code = catalogue.resolve_category_alias(query)
    if cat_code:
        return [i["item_code"] for i in catalogue.items_for_category(cat_code)]
    return []


def _estimate_turnaround(query: str) -> dict:
    codes = _resolve_item_codes(query)
    turnaround = delivery.order_turnaround(codes)  # [] → safe default rule
    options = delivery.delivery_options(codes)
    return {
        "matched_items": len(codes),
        "standard_turnaround": turnaround["display_text"],
        "express_available": bool(options.get("express_eligible")),
        "express": options.get("express"),
        "guidance": (
            "This is the configured SLA — quote the standard window. "
            "If no specific item matched, present it as a general estimate and say "
            "the team confirms once items are seen. Never promise an exact hour "
            "beyond this."
        ),
    }


def _check_service_area(area: str) -> dict:
    matched = slot_tools.extract_area(area or "")
    if matched:
        return {
            "recognised": True,
            "area": matched,
            "guidance": "Area recognised — you may confirm the team covers it.",
        }
    return {
        "recognised": False,
        "guidance": (
            "Area not recognised in the gazetteer. Do NOT say it is or isn't covered "
            "— ask the customer to confirm their area and tell them the team will "
            "confirm availability."
        ),
    }


# --- Dispatch --------------------------------------------------------------
async def execute_tool(name: str, tool_input: dict) -> tuple[str, bool]:
    """Validate + run one tool call. Returns (result_json, is_error).

    This is the ONLY bridge between the model and the deterministic engines.
    Unknown tools and bad inputs are rejected safely (never raise into the
    reply path); every call is logged for auditability."""
    tool_input = tool_input or {}
    if name not in _TOOL_NAMES:
        logger.warning("llm_tool_unknown", tool=name)
        return json.dumps({"error": f"Unknown tool '{name}'."}), True

    try:
        if name == "lookup_item_price":
            query = str(tool_input.get("query", "")).strip()
            if not query:
                return json.dumps({"error": "query is required."}), True
            result = _lookup_item_price(query)
        elif name == "list_service_categories":
            result = _list_service_categories()
        elif name == "estimate_turnaround":
            query = str(tool_input.get("query", "")).strip()
            if not query:
                return json.dumps({"error": "query is required."}), True
            result = _estimate_turnaround(query)
        elif name == "check_service_area":
            area = str(tool_input.get("area", "")).strip()
            if not area:
                return json.dumps({"error": "area is required."}), True
            result = _check_service_area(area)
        else:  # pragma: no cover - guarded by _TOOL_NAMES above
            return json.dumps({"error": f"Unhandled tool '{name}'."}), True
    except Exception as exc:  # noqa: BLE001 - a tool must never crash the reply path
        logger.warning("llm_tool_error", tool=name, error=str(exc))
        return json.dumps({"error": "Tool failed; ask the customer to rephrase."}), True

    logger.info("llm_tool_called", tool=name, input_keys=sorted(tool_input.keys()),
                outcome=result.get("match") or result.get("recognised") or "ok")
    return json.dumps(result, ensure_ascii=False), False
