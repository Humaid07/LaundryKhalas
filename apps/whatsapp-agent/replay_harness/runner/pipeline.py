"""Drive the REAL agent pipeline for one turn and snapshot the resulting state.

We feed each turn through the production Evolution webhook endpoint in-process
(ASGI), so the full path runs: normalization -> dedup -> persistence ->
(webhook aggregation off, we pre-group) -> customer memory -> conversation state
-> Anthropic agent -> tool loop -> workflow update -> deliver. The only swapped
component is the outbound transport (capture-only) — nothing else is mocked.

Captured per turn: the customer-facing reply (from the capture sink), all LLM
usage + tool calls (from the instrument wrapper), and the backend workflow state
(read from the DB via the same repos the pipeline uses).
"""
from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Optional

from ..core.config import ReplayConfig
from ..core.models import ModelUsage, ToolCallCapture
from ..safety import capture_channel
from . import instrument
from .grouping import TurnGroup


# ---------------------------------------------------------------------------
# Environment bootstrap — must run BEFORE settings/app import so the cached
# settings object reflects replay overrides.
# ---------------------------------------------------------------------------
def bootstrap_env(cfg: ReplayConfig, synthetic_numbers: list[str]) -> None:
    """Set replay env overrides and reload cached settings."""
    os.environ["WHATSAPP_REPLAY_MODE"] = "true"
    os.environ["WHATSAPP_REPLAY_CAPTURE_ONLY"] = "true"
    # Model override for the replay (does NOT touch .env).
    if cfg.model:
        os.environ["ANTHROPIC_WHATSAPP_MODEL"] = cfg.model
    # We pre-group fragments and feed one combined message per turn, so turn OFF
    # the webhook's own debounce/aggregation to get one deterministic reply/turn.
    os.environ["WHATSAPP_MESSAGE_AGGREGATION_ENABLED"] = "false"
    # Allow-list must include every synthetic sender (test-mode gate).
    existing = os.environ.get("EVOLUTION_ALLOWED_TEST_NUMBERS", "")
    numbers = [n for n in synthetic_numbers if n]
    joined = ",".join(dict.fromkeys(([existing] if existing else []) + numbers))
    os.environ["EVOLUTION_ALLOWED_TEST_NUMBERS"] = joined
    # Keep agent in TEST mode (never live) and facility notifications mock.
    os.environ.setdefault("WHATSAPP_AGENT_MODE", "test")
    os.environ.setdefault("FACILITY_NOTIFICATIONS_MODE", "mock")

    # Reload cached settings so the above take effect.
    from settings import get_settings

    get_settings.cache_clear()


def install_all() -> None:
    """Install capture transport + instrumentation. Idempotent."""
    capture_channel.install()
    instrument.install()


@asynccontextmanager
async def app_context():
    """Start the FastAPI app lifespan + an in-process ASGI client."""
    from httpx import ASGITransport, AsyncClient

    from main import app

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://replay") as client:
            yield client


# ---------------------------------------------------------------------------
# Payload construction (Baileys/Evolution shape the parser understands)
# ---------------------------------------------------------------------------
def _jid(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    return f"{digits}@s.whatsapp.net"


def build_payload(group: TurnGroup, phone: str, name: str) -> dict:
    """Build one inbound Evolution webhook payload for a turn group."""
    media = group.media_message
    key = {"remoteJid": _jid(phone), "fromMe": False, "id": f"replay-{uuid.uuid4().hex[:16]}"}
    if media is not None:
        if media.message_type.value == "audio":
            message: dict[str, Any] = {"audioMessage": {"ptt": True, "seconds": 3}}
        elif media.message_type.value == "image":
            message = {"imageMessage": {"caption": media.caption or ""}}
        elif media.message_type.value == "video":
            message = {"videoMessage": {"caption": media.caption or ""}}
        elif media.message_type.value == "document":
            message = {"documentMessage": {"caption": media.caption or "", "fileName": media.media_reference}}
        else:
            message = {"conversation": media.caption or media.text or ""}
    elif group.first.location_data:
        loc = group.first.location_data
        message = {"locationMessage": {"degreesLatitude": loc.get("lat"), "degreesLongitude": loc.get("lon")}}
    else:
        message = {"conversation": group.combined_text}
    return {
        "event": "messages.upsert",
        "instance": os.environ.get("EVOLUTION_INSTANCE_NAME", "whatsapp-agent"),
        "data": {"key": key, "message": message, "pushName": name},
    }


# ---------------------------------------------------------------------------
# Workflow snapshot (read real backend state)
# ---------------------------------------------------------------------------
@dataclass
class WorkflowSnapshot:
    order_state: str = ""
    service: str = ""
    service_code: str = ""
    pricing_type: str = ""
    unit_price: Optional[float] = None
    quantity: Optional[float] = None
    pre_discount_total: Optional[float] = None
    discount_percentage: Optional[float] = None
    discount_amount: Optional[float] = None
    final_total: Optional[float] = None
    pickup_slot: str = ""
    pickup_area: str = ""
    facility_result: str = ""
    additional_notes: str = ""
    confirmation_status: str = ""
    conversation_status: str = ""
    missing_fields: list[str] = field(default_factory=list)
    catalogue_version: str = ""


async def _ids_for_phone(phone: str, name: str) -> tuple[Optional[str], Optional[str], str]:
    """Return (customer_id, conversation_id, conversation_status) for a synthetic
    phone, using the SAME repos + external_id the pipeline used."""
    from db.repositories import conversations_repo, customers_repo
    from services.privacy import normalize_e164

    try:
        customer = await customers_repo.get_or_create_by_phone(phone, name)
        sender = normalize_e164(phone)
        convo = await conversations_repo.get_or_create_for_customer(
            customer["id"], external_id=f"evo:{sender}"
        )
        return customer["id"], convo["id"], convo.get("status", "")
    except Exception:  # noqa: BLE001
        return None, None, ""


async def snapshot_workflow(phone: str, name: str) -> WorkflowSnapshot:
    """Read the current order/conversation state for a synthetic customer."""
    snap = WorkflowSnapshot()
    customer_id, convo_id, convo_status = await _ids_for_phone(phone, name)
    snap.conversation_status = convo_status
    if not convo_id:
        return snap
    from db.repositories import orders_repo

    try:
        order = await orders_repo.get_latest_for_conversation(convo_id)
    except Exception:  # noqa: BLE001
        order = None
    if not order:
        return snap
    snap.order_state = str(order.get("status") or order.get("state") or "")
    snap.service = str(order.get("service_type") or order.get("service_display_name") or "")
    snap.service_code = str(order.get("service_id") or "")
    snap.pickup_area = str(order.get("pickup_area") or "")
    snap.pickup_slot = str(order.get("pickup_slot") or order.get("pickup_slot_label") or "")
    snap.final_total = _f(order.get("final_price"))
    snap.pre_discount_total = _f(order.get("eligible_subtotal"))
    snap.discount_amount = _f(order.get("discount_amount"))
    snap.discount_percentage = _f(order.get("discount_percentage"))
    snap.facility_result = str(order.get("facility_name") or order.get("facility_id") or "")
    snap.additional_notes = str(order.get("notes") or order.get("confirmed_notes_snapshot") or "")
    snap.confirmation_status = "confirmed" if _is_confirmed(order) else str(order.get("status") or "")
    snap.catalogue_version = str(order.get("catalogue_version") or "")
    return snap


def _f(v) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _is_confirmed(order: dict) -> bool:
    status = str(order.get("status") or "").lower()
    return status not in ("", "draft", "abandoned", "cancelled")


# ---------------------------------------------------------------------------
# Per-turn execution
# ---------------------------------------------------------------------------
@dataclass
class TurnResult:
    reply_text: str
    llm_records: list  # list[instrument.LLMCallRecord]
    snapshot: WorkflowSnapshot
    error: str = ""


async def run_turn(client, group: TurnGroup, phone: str, name: str, context_key: str) -> TurnResult:
    """Feed one turn through the pipeline and capture reply + usage + state."""
    sink = capture_channel.get_sink()
    sink.set_context(context_key)
    before_count = len(sink.for_context(context_key))
    records = instrument.begin_turn_capture()

    payload = build_payload(group, phone, name)
    error = ""
    try:
        resp = await client.post("/webhooks/evolution", json=payload)
        if resp.status_code >= 500:
            error = f"webhook {resp.status_code}: {resp.text[:200]}"
    except Exception as exc:  # noqa: BLE001
        error = f"post failed: {exc}"

    instrument.end_turn_capture()
    # Reply = newest captured message for this context beyond what existed before.
    ctx_msgs = sink.for_context(context_key)
    new_msgs = ctx_msgs[before_count:]
    reply_text = ""
    for m in reversed(new_msgs):
        if m.kind in ("text", "list", "buttons") and m.text:
            reply_text = m.text
            break

    snap = await snapshot_workflow(phone, name)
    return TurnResult(reply_text=reply_text, llm_records=records, snapshot=snap, error=error)


def usage_from_records(records: list) -> tuple[ModelUsage, list[ToolCallCapture]]:
    """Aggregate LLM call records into a ModelUsage + tool-call captures."""
    usage = ModelUsage()
    tool_caps: list[ToolCallCapture] = []
    for r in records:
        usage.add(ModelUsage(
            model_id=r.model,
            input_tokens=r.tokens_in,
            output_tokens=r.tokens_out,
            cache_read_input_tokens=r.cache_read,
            cache_creation_input_tokens=r.cache_write,
            latency_ms=int(r.latency_ms),
            stop_reason=r.stop_reason,
            tool_loop_rounds=r.tool_rounds,
            estimated_cost_usd=r.cost_usd,
        ))
        for tc in r.tool_calls:
            tool_caps.append(ToolCallCapture(
                tool_name=getattr(tc, "name", "") or "",
                validated_arguments=dict(getattr(tc, "input", {}) or {}),
                safe_result_summary=str(getattr(tc, "result", ""))[:300],
                success=not getattr(tc, "is_error", False),
                failure_type="tool_error" if getattr(tc, "is_error", False) else "",
                state_changed=_tool_mutates(getattr(tc, "name", "")),
            ))
    return usage, tool_caps


_MUTATING_TOOLS = {
    "start_booking", "update_booking", "confirm_order", "set_pickup_slot",
    "apply_discount", "calculate_applicable_order_discount", "add_note",
    "request_human_support",
}


def _tool_mutates(name: str) -> bool:
    return name in _MUTATING_TOOLS


async def cleanup_replay_state() -> int:
    """Delete synthetic replay_* customers (phones under +999000...) and their
    conversations/orders/messages from the TEST db, for a clean run. Returns the
    number of customers removed. Best-effort; never raises."""
    from db import database

    if not database.is_supabase_mode():
        return 0
    try:
        # Cascade-safe order: messages -> orders -> conversations -> customers.
        await database.execute(
            "delete from messages where conversation_id in "
            "(select c.id from conversations c join customers cu on cu.id=c.customer_id "
            "where cu.phone like '999000%' or cu.phone like '+999000%')"
        )
        await database.execute(
            "delete from orders where conversation_id in "
            "(select c.id from conversations c join customers cu on cu.id=c.customer_id "
            "where cu.phone like '999000%' or cu.phone like '+999000%')"
        )
        await database.execute(
            "delete from conversations where customer_id in "
            "(select id from customers where phone like '999000%' or phone like '+999000%')"
        )
        removed = await database.fetchval(
            "with d as (delete from customers where phone like '999000%' "
            "or phone like '+999000%' returning 1) select count(*) from d"
        )
        return int(removed or 0)
    except Exception:  # noqa: BLE001
        return 0
