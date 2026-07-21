"""Structured per-message logging and the administrator notification sink
(task Part 9). Two separate channels:

* Application log (`logs/laundry_class_agent.log`) — one JSON line per message,
  with the phone number **masked**. Never contains card details, OTPs, passwords,
  API secrets, or auth tokens.
* Admin handoff channel (`logs/admin_handoffs.log`) — the operations team's inbox
  for handoffs; keeps the full phone number because it is operationally required
  to act on the case. In production this would be a WhatsApp/Slack/email channel.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)
_APP_LOG = _LOG_DIR / "laundry_class_agent.log"
_ADMIN_LOG = _LOG_DIR / "admin_handoffs.log"

_PHONE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{6,}\d(?!\w)")


def mask_phone(phone: str | None) -> str:
    """+971500000101 -> +97150***01 (keeps enough to correlate, hides the middle)."""
    if not phone:
        return "unknown"
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 6:
        return "***"
    prefix = "+" if phone.strip().startswith("+") else ""
    return f"{prefix}{digits[:5]}***{digits[-2:]}"


def mask_text(text: str | None) -> str | None:
    if not text:
        return text
    return _PHONE.sub("[phone hidden]", text)


def log_turn(record: dict) -> None:
    """Append one masked JSON line describing an inbound message and its handling."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phone_masked": mask_phone(record.get("phone_number")),
        "thread_id": record.get("thread_id"),
        "detected_intent": record.get("detected_intent"),
        "kb_section": record.get("kb_section"),
        "current_order_id": record.get("current_order_id"),
        "memory_loaded": record.get("memory_loaded"),
        "handoff_triggered": record.get("handoff_triggered"),
        "handoff_reason": record.get("handoff_reason"),
        "response_status": record.get("response_status"),
        "error": record.get("error"),
    }
    with _APP_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


# Callback the runtime can override in tests to capture notifications in-memory.
_ADMIN_SINK = None


def set_admin_sink(callback) -> None:
    global _ADMIN_SINK
    _ADMIN_SINK = callback


def notify_admin(notification: str) -> None:
    """Deliver a structured handoff notification to the operations team channel."""
    stamped = f"----- {datetime.now(timezone.utc).isoformat()} -----\n{notification}\n"
    with _ADMIN_LOG.open("a", encoding="utf-8") as fh:
        fh.write(stamped + "\n")
    if _ADMIN_SINK is not None:
        _ADMIN_SINK(notification)
