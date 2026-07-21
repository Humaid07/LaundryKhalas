"""Interactive WhatsApp-style message actions (quick-reply buttons attached
to an agent message), and the mapping between a clicked action's id and the
intent it should deterministically resolve to - so a button click never
depends on re-parsing its own label text through the keyword guesser.

The button set and the id->intent map are configured in
config/quick_actions.json; the service-selection buttons come from
config/laundry_services.json. Nothing here is hardcoded - editing those
files (then restarting) changes the menu with no code change.
"""
from dataclasses import dataclass

from rules import quick_actions_config, service_catalog


@dataclass(frozen=True)
class Action:
    id: str
    label: str
    type: str = "quick_reply"

    def to_dict(self) -> dict:
        return {"id": self.id, "label": self.label, "type": self.type}


_MAIN_MENU_CFG = quick_actions_config()["main_menu"]

MAIN_MENU_ACTIONS: list[Action] = [Action(a["id"], a["label"]) for a in _MAIN_MENU_CFG]

# Service buttons: id = service key, label = service label (config-driven).
SERVICE_ACTIONS: list[Action] = [Action(s["key"], s["label"]) for s in service_catalog()]

_SERVICE_ACTION_IDS = {a.id for a in SERVICE_ACTIONS}

# Shown under the booking summary so the customer can commit (which creates
# the active mock order) or back out without typing.
CONFIRM_ACTIONS: list[Action] = [
    Action("confirm_booking", "Confirm Booking"),
    Action("cancel_booking", "Not now"),
]
_SERVICE_ACTION_INTENT = quick_actions_config()["service_action_intent"]

# A clicked main-menu action resolves directly to its configured intent,
# bypassing keyword guessing entirely - the most robust possible routing,
# since we know exactly which button was pressed.
ACTION_ID_TO_INTENT: dict[str, str] = {a["id"]: a["intent"] for a in _MAIN_MENU_CFG}

# Fast lookup for attaching specific buttons by id (e.g. escalation handoff).
ACTION_BY_ID: dict[str, Action] = {a.id: a for a in MAIN_MENU_ACTIONS}


def resolve_intent_override(action_id: str | None) -> str | None:
    """None means "no override, fall back to text-based detect_intent"."""
    if not action_id:
        return None
    if action_id in ACTION_ID_TO_INTENT:
        return ACTION_ID_TO_INTENT[action_id]
    if action_id in _SERVICE_ACTION_IDS:
        return _SERVICE_ACTION_INTENT
    return None


def actions_by_ids(ids: list[str]) -> list[Action]:
    """Resolve a list of main-menu action ids to Action objects, skipping
    any unknown id. Used to attach configured buttons (e.g. Call Support) to
    an escalation/handoff message."""
    return [ACTION_BY_ID[i] for i in ids if i in ACTION_BY_ID]
