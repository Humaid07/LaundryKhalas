"""Capture-only outbound transport.

The replay harness must NEVER transmit a real WhatsApp message. Several code
paths instantiate `EvolutionWhatsAppChannel.from_settings()` directly (escalation
acks, booking deliver, etc.), so swapping a single channel object is insufficient.

Instead we neutralize the outbound provider at the CLASS level: every
`send_text` / `send_list` / `send_buttons` / `_post` / `instance_status` on both
the Evolution and Meta channels is replaced with a capture implementation that
records the message into a process-wide sink and returns a `SendResult` WITHOUT
any network I/O. This holds no matter where or how the channel is constructed.

`install()` is idempotent and returns the sink. `self_test()` proves a probe
send is captured (never transmitted); the guard refuses to run otherwise.
"""
from __future__ import annotations

import contextvars
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from channels.whatsapp_base import SendResult

# Async-task-isolated context key: each concurrent conversation runs in its own
# asyncio task and sets this, so captured messages attribute correctly even when
# several conversations replay at once.
_CONTEXT_KEY: contextvars.ContextVar[str] = contextvars.ContextVar(
    "replay_capture_context", default=""
)


@dataclass
class CapturedMessage:
    to_phone: str
    kind: str  # text | list | buttons | post
    text: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    channel: str = "evolution"
    # Set by the runner so captures can be attributed to a conversation/turn.
    context_key: str = ""


class CaptureSink:
    """Thread-safe collector of everything the pipeline tried to 'send'."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._messages: list[CapturedMessage] = []

    def set_context(self, key: str) -> None:
        _CONTEXT_KEY.set(key)

    def clear_context(self) -> None:
        _CONTEXT_KEY.set("")

    def _context(self) -> str:
        return _CONTEXT_KEY.get() or ""

    def record(self, msg: CapturedMessage) -> None:
        msg.context_key = self._context()
        with self._lock:
            self._messages.append(msg)

    def all(self) -> list[CapturedMessage]:
        with self._lock:
            return list(self._messages)

    def for_context(self, key: str) -> list[CapturedMessage]:
        with self._lock:
            return [m for m in self._messages if m.context_key == key]

    def latest_text(self, key: str) -> Optional[str]:
        msgs = [m for m in self.for_context(key) if m.kind in ("text", "list", "buttons")]
        return msgs[-1].text if msgs else None

    def reset(self) -> None:
        with self._lock:
            self._messages.clear()

    def count(self) -> int:
        with self._lock:
            return len(self._messages)


# Process-wide singleton.
_SINK = CaptureSink()
_INSTALLED = False
_ORIGINALS: dict[str, Any] = {}


def get_sink() -> CaptureSink:
    return _SINK


def is_installed() -> bool:
    return _INSTALLED


# --- capture method implementations ---------------------------------------
async def _cap_send_text(self, *, to_phone: str, text: str) -> SendResult:
    _SINK.record(CapturedMessage(
        to_phone=to_phone, kind="text", text=text,
        channel=getattr(self, "name", "unknown"),
    ))
    return SendResult(message_id=f"captured-{uuid.uuid4().hex[:12]}", status="captured")


async def _cap_send_list(self, *, to_phone: str, body: str, button_text: str,
                         rows: list[dict], section_title: str = "Options",
                         header: str = "", footer: str = "") -> SendResult:
    _SINK.record(CapturedMessage(
        to_phone=to_phone, kind="list", text=body,
        payload={"button_text": button_text, "rows": rows, "header": header, "footer": footer},
        channel=getattr(self, "name", "unknown"),
    ))
    return SendResult(message_id=f"captured-{uuid.uuid4().hex[:12]}", status="captured")


async def _cap_send_buttons(self, *, to_phone: str, body: str, buttons: list[dict],
                            header: str = "", footer: str = "") -> SendResult:
    _SINK.record(CapturedMessage(
        to_phone=to_phone, kind="buttons", text=body,
        payload={"buttons": buttons, "header": header, "footer": footer},
        channel=getattr(self, "name", "unknown"),
    ))
    return SendResult(message_id=f"captured-{uuid.uuid4().hex[:12]}", status="captured")


async def _cap_post(self, path: str, payload: dict) -> dict:
    _SINK.record(CapturedMessage(
        to_phone=str(payload.get("number", "")), kind="post", payload={"path": path, **payload},
        channel=getattr(self, "name", "unknown"),
    ))
    return {"key": {"id": f"captured-{uuid.uuid4().hex[:12]}"}}


async def _cap_instance_status(self) -> dict:
    # Pretend the instance is connected so readiness checks pass without I/O.
    return {"instance": {"state": "open"}, "state": "open", "captured": True}


def install() -> CaptureSink:
    """Replace outbound transport methods with capture implementations. Idempotent."""
    global _INSTALLED
    if _INSTALLED:
        return _SINK

    from channels import evolution_whatsapp as ev
    targets = [("evolution", ev.EvolutionWhatsAppChannel)]
    try:
        from channels import meta_whatsapp as meta
        targets.append(("meta", meta.MetaWhatsAppChannel))
    except Exception:  # noqa: BLE001 - meta optional
        pass

    for name, cls in targets:
        for meth_name, impl in (
            ("send_text", _cap_send_text),
            ("send_list", _cap_send_list),
            ("send_buttons", _cap_send_buttons),
            ("_post", _cap_post),
            ("instance_status", _cap_instance_status),
        ):
            if hasattr(cls, meth_name):
                _ORIGINALS[f"{name}.{meth_name}"] = getattr(cls, meth_name)
                setattr(cls, meth_name, impl)

    _INSTALLED = True
    return _SINK


def uninstall() -> None:
    """Restore original transport methods (used by tests)."""
    global _INSTALLED
    if not _INSTALLED:
        return
    from channels import evolution_whatsapp as ev
    classes = {"evolution": ev.EvolutionWhatsAppChannel}
    try:
        from channels import meta_whatsapp as meta
        classes["meta"] = meta.MetaWhatsAppChannel
    except Exception:  # noqa: BLE001
        pass
    for key, original in list(_ORIGINALS.items()):
        cls_name, meth = key.split(".", 1)
        cls = classes.get(cls_name)
        if cls is not None:
            setattr(cls, meth, original)
    _ORIGINALS.clear()
    _INSTALLED = False


async def self_test() -> bool:
    """Prove a probe send is captured, not transmitted. Returns True on success."""
    if not _INSTALLED:
        return False
    from channels.evolution_whatsapp import EvolutionWhatsAppChannel
    before = _SINK.count()
    # Construct with junk connection details: if the patch failed, a real send
    # would attempt to reach this URL and raise — which also fails the test.
    probe = EvolutionWhatsAppChannel(
        base_url="http://127.0.0.1:9/never", api_key="x", instance="probe"
    )
    try:
        result = await probe.send_text(to_phone="+000000000000", text="__replay_probe__")
    except Exception:  # noqa: BLE001 - any network attempt means patch failed
        return False
    if result.status != "captured":
        return False
    if _SINK.count() != before + 1:
        return False
    # Remove the probe so it doesn't pollute real captures.
    with _SINK._lock:  # noqa: SLF001 - internal cleanup
        _SINK._messages.pop()
    return True
