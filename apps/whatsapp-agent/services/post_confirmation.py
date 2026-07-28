"""Post-confirmation terminal boundary for the WhatsApp booking flow.

Once an order is confirmed the booking workflow is DONE: the agent sends exactly
one confirmation and then stays silent until the customer sends a NEW, explicit
request. This module answers two questions the webhook needs:

  * ``is_confirmed_order(order)`` — is this conversation's latest order a confirmed
    (terminal-for-booking) order? The persisted ORDER state is the authority — a
    confirmed order (status past ``draft``, not cancelled/abandoned, or parked in
    the POST_ORDER conversation state) IS the terminal boundary, so we don't need
    a separate workflow_version column to know the booking is complete.
  * ``classify_post_confirmation_turn(text)`` — for a turn that arrives when there
    is NO active draft but a confirmed order exists, is it something to act on (a
    new order / an edit / a question) or something we must NOT turn into a booking
    message (a bare acknowledgement, a stale/duplicate "yes", or empty noise)?

Deterministic + offline (no LLM, no DB). Used by api/evolution_webhooks to block
the spurious discount/upsell/re-confirm/goodbye chatter that used to appear after
a confirmation because a missing draft made the model think a NEW booking had
started.
"""
from __future__ import annotations

import re
from enum import Enum

from services import booking_flow as bf
from services import order_store

# Booking-flow NON-terminal statuses. Anything NOT here is a confirmed /
# operational order → the booking flow is over.
_NON_CONFIRMED = frozenset({order_store.DRAFT, order_store.CANCELLED, order_store.ABANDONED})


class PostConfirmTurn(str, Enum):
    NEW_ORDER = "new_order"   # customer wants to place ANOTHER booking
    EDIT = "edit"             # change / add to / cancel the confirmed order
    QUERY = "query"           # a question (price / discount / status / when / where)
    THANKS = "thanks"         # bare gratitude / ack → at most a short reply
    NONE = "none"             # nothing to act on (stale confirm / empty / duplicate)

    @property
    def is_actionable(self) -> bool:
        """True when the agent SHOULD run a normal turn (new request from the
        customer). THANKS/NONE are handled without a booking turn."""
        return self in (PostConfirmTurn.NEW_ORDER, PostConfirmTurn.EDIT, PostConfirmTurn.QUERY)


def is_confirmed_order(order: dict | None) -> bool:
    if not order:
        return False
    status = order.get("status")
    if status and status not in _NON_CONFIRMED:
        return True
    # A draft explicitly parked in POST_ORDER is also terminal for the flow.
    return order.get("conversation_state") == bf.POST_ORDER


_EDIT_KW = ("change", "edit", "update", "modify", "reschedule", "cancel", "remove",
            "add ", "also add", "another item", "different", "swap", "replace",
            "move it", "make it")
_QUERY_KW = ("why", "how much", "price", "discount", "cheaper", "when", "where",
             "status", "track", "how long", "turnaround", "eta", "voucher", "offer",
             "coupon", "promo")
# Bare acknowledgements / filler that never restart booking logic.
_THANKS = frozenset({
    "ok", "okay", "k", "kk", "thanks", "thank", "thankyou", "thanku", "thx", "ty",
    "cool", "great", "nice", "fine", "done", "sure", "alright", "noted", "perfect",
    "awesome", "brilliant", "lovely", "cheers", "welcome",
})
# Gratitude tokens — if ANY appears (even alongside a name, "thank you Shinu"),
# the turn is gratitude → a brief optional reply, never a booking message.
_GRATITUDE = frozenset({"thanks", "thank", "thankyou", "thanku", "thx", "ty", "cheers"})
# A bare confirmation echo AFTER the order is already confirmed → stale/duplicate,
# must NOT produce a second confirmation.
_CONFIRMISH = frozenset({
    "yes", "y", "ya", "yeah", "yep", "yup", "confirm", "confirmed", "confirm it",
    "go ahead", "proceed", "book it", "please confirm", "yes please", "ok confirm",
    "yes confirm", "correct", "right",
})

_STRIP = re.compile(r"[^a-z0-9\s]")


def _norm(text: str | None) -> str:
    return " ".join(_STRIP.sub(" ", (text or "").lower()).split())


def classify_post_confirmation_turn(text: str | None,
                                    selection_id: str | None = None) -> PostConfirmTurn:
    """Classify a customer turn that arrives when the order is already confirmed.

    Only NEW_ORDER/EDIT/QUERY are actionable (run a normal turn). THANKS earns at
    most a brief reply; NONE (stale "yes", empty, or a leftover interactive tap)
    earns silence — never a fresh booking/upsell/discount message.
    """
    raw = (text or "").strip()
    norm = _norm(raw)
    low = f" {norm} "

    # A question or an edit to the CONFIRMED order (checked before the broad
    # book-pickup match, since "change my pickup" contains "pickup").
    if raw.endswith("?") or any(k in low for k in _QUERY_KW):
        return PostConfirmTurn.QUERY
    if any(k in low for k in _EDIT_KW):
        return PostConfirmTurn.EDIT
    # Otherwise an explicit "place another order" / book-a-pickup intent → new order.
    if bf.is_new_order_intent(raw) or bf.is_book_pickup_intent(raw):
        return PostConfirmTurn.NEW_ORDER

    if not norm:
        # Empty text or a bare (stale) interactive selection — nothing to do.
        return PostConfirmTurn.NONE

    tokens = norm.split()
    # A bare confirmation echo after we're already confirmed = stale/duplicate.
    if norm in _CONFIRMISH or all(t in _CONFIRMISH for t in tokens):
        return PostConfirmTurn.NONE
    # Gratitude (possibly with a name) or a bare acknowledgement → brief reply.
    if any(t in _GRATITUDE for t in tokens) or all(t in _THANKS for t in tokens):
        return PostConfirmTurn.THANKS

    # Unknown short chatter after confirmation — do NOT restart booking. Stay
    # silent rather than hallucinate a booking step (the reported bug).
    return PostConfirmTurn.NONE
