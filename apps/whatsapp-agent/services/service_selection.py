"""Service-selection helper for the WhatsApp Operations Agent.

When a customer asks to book a pickup WITHOUT naming a service (e.g. "Hi, I need
a laundry pickup service"), the agent must NOT guess a service. It asks which
service they need and offers the canonical options (the live LaundryKhalas
catalog) plus a "Not sure / Help me choose" fallback. The selected service id is
what gets stored on the order.

Everything here is deterministic (no LLM) and reads the SINGLE source of truth
(``config/laundry_services.json`` via ``rules``) so the option list can never
drift from the backend / dashboard / SEO taxonomy.
"""
from __future__ import annotations

from rules import service_options as _catalog_options

# The non-service escape hatch appended to the option list. Not a service (it has
# no id in the catalog) — selecting it routes the customer into a guided
# "help me choose" flow rather than storing a service.
HELP_ME_CHOOSE = {"id": "help_me_choose", "label": "Not sure / Help me choose"}

_CLARIFICATION_PROMPT = "Sure — which service do you need?"


def service_options(include_help: bool = True) -> list[dict]:
    """Ordered options the agent shows when asking which service is needed:
    every active canonical service, then (optionally) "Not sure / Help me choose".
    Each option is ``{id, label, unit_type, starting_price_aed, requires_manual_quote}``
    (the help option only has ``id``/``label``)."""
    options = list(_catalog_options())
    if include_help:
        options.append(dict(HELP_ME_CHOOSE))
    return options


def needs_service_clarification(details) -> bool:
    """True when we cannot yet tell which service the customer wants: no service
    was detected from their words AND no items were recognised that would imply a
    service. In that case the agent must ASK instead of picking one."""
    if getattr(details, "service_key", None):
        return False
    if getattr(details, "items", None):
        # Items were recognised but did not resolve to a service — still ambiguous
        # enough (e.g. bare "shirts") that we ask rather than assume.
        return getattr(details, "service_label", None) is None
    return True


def build_service_clarification(include_help: bool = True) -> dict:
    """The full clarification payload the agent sends: the question text and the
    ordered service options (ids + labels) to render as quick-reply buttons."""
    return {
        "prompt": _CLARIFICATION_PROMPT,
        "options": service_options(include_help=include_help),
    }


def clarification_text() -> str:
    """The question + a readable bulleted list of options, for channels/tests
    that render plain text rather than interactive buttons."""
    lines = [_CLARIFICATION_PROMPT, ""]
    for opt in service_options():
        lines.append(f"- {opt['label']}")
    return "\n".join(lines)
