"""Central loader for the WhatsApp agent's business & safety rule config.

Every configurable rule the agent follows lives in one of the config/*.json
rule files loaded here (once, cached with lru_cache) so the domain guard,
system prompt, quick actions, escalation handoff and mock-mode wording all
read the same single source of truth instead of hardcoding strings in code.

This module deliberately imports nothing from the agent (it is a leaf), so
any module may import it without creating a cycle. Restart the service
after editing a rule file to pick up the change.
"""
import json
from functools import lru_cache
from pathlib import Path

_CONFIG_DIR = Path(__file__).resolve().parent / "config"


@lru_cache(maxsize=None)
def _load(filename: str) -> dict:
    return json.loads((_CONFIG_DIR / filename).read_text(encoding="utf-8"))


# --- Raw rule files -------------------------------------------------------

def agent_rules() -> dict:
    return _load("whatsapp_agent_rules.json")


def services_config() -> dict:
    return _load("laundry_services.json")


def quick_actions_config() -> dict:
    return _load("quick_actions.json")


def escalation_rules() -> dict:
    return _load("escalation_rules.json")


def mock_mode_rules() -> dict:
    return _load("mock_mode_rules.json")


def tone_rules() -> dict:
    return _load("agent_tone_rules.json")


def pickup_instructions() -> list[dict]:
    """Stable [{code, label}] pickup-instruction options for the booking flow's
    instructions step. Source of truth: config/pickup_instructions.json."""
    return _load("pickup_instructions.json")["instructions"]


# --- Convenience accessors used across the agent --------------------------

def service_catalog() -> list[dict]:
    """List of {service_id/key, display_name/label, aliases/keywords, pricing,
    unit_type, category, requires_manual_quote, ...} — the configured services,
    synced to the live LaundryKhalas website taxonomy."""
    return services_config()["services"]


def active_service_catalog() -> list[dict]:
    """Only services with ``active`` truthy (default true) — what the agent
    offers and the dashboard/SEO taxonomy derive from."""
    return [s for s in service_catalog() if s.get("active", True)]


def service_labels() -> dict[str, str]:
    """service id -> display label."""
    return {s["key"]: s["label"] for s in service_catalog()}


def service_by_id(service_id: str | None) -> dict | None:
    """Full canonical service object for a service_id/key, or None."""
    if not service_id:
        return None
    for s in service_catalog():
        if s.get("service_id", s.get("key")) == service_id or s.get("key") == service_id:
            return s
    return None


def service_ids() -> list[str]:
    """Ordered list of canonical service ids."""
    return [s.get("service_id", s.get("key")) for s in service_catalog()]


def service_options() -> list[dict]:
    """[{id, label, unit_type, starting_price_aed, requires_manual_quote}] for the
    active services — the ordered options the WhatsApp agent shows when asking
    the customer which service they need, and the dashboard filter source."""
    return [
        {
            "id": s.get("service_id", s.get("key")),
            "label": s["label"],
            "unit_type": s.get("unit_type"),
            "starting_price_aed": s.get("starting_price_aed"),
            "requires_manual_quote": bool(s.get("requires_manual_quote")),
        }
        for s in active_service_catalog()
    ]


def promotional_items() -> list[dict]:
    """Verified item-level promo prices from the live site (illustrative/reference
    only — never auto-applied to a customer order)."""
    return services_config().get("promotional_items", [])


def service_promises() -> list[str]:
    """The customer-facing service promises shown on the live website."""
    return services_config().get("service_promises", [])


def refusal_message() -> str:
    return agent_rules()["domain"]["refusal_message"]


def welcome_message() -> str:
    return agent_rules()["welcome"]["message"]


def mock_tags() -> dict:
    """The demo-mode wording block (order_tag, support_tag, booking_ack, ...)."""
    return mock_mode_rules()["mock"]
