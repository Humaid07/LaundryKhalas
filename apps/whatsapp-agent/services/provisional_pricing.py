"""Provisional vs exact pricing states + customer-facing presenter (pure).

The backend owns every price. This module names the pricing STATE and renders the
matching short WhatsApp wording — a provisional price is NEVER called final, and a
range is never presented as a guarantee unless a backend maximum is defined. It
does not compute prices (that stays in the pricing/markup layer); it only maps a
grounded price context to the correct customer sentence.
"""

from __future__ import annotations

from services import service_rules as sr

# --- pricing states (spec §4) ------------------------------------------------
PUBLISHED_EXACT = "PUBLISHED_EXACT"
PUBLISHED_FROM = "PUBLISHED_FROM"
PUBLISHED_RANGE = "PUBLISHED_RANGE"
PROVISIONAL_ESTIMATE = "PROVISIONAL_ESTIMATE"
AWAITING_FACILITY_QUOTE = "AWAITING_FACILITY_QUOTE"
FACILITY_QUOTE_RECEIVED = "FACILITY_QUOTE_RECEIVED"
CUSTOMER_PRICE_PENDING = "CUSTOMER_PRICE_PENDING"
CUSTOMER_PRICE_SENT = "CUSTOMER_PRICE_SENT"
CUSTOMER_PRICE_APPROVED = "CUSTOMER_PRICE_APPROVED"
CUSTOMER_PRICE_DECLINED = "CUSTOMER_PRICE_DECLINED"
QUOTE_EXPIRED = "QUOTE_EXPIRED"

PRICING_STATES = (
    PUBLISHED_EXACT, PUBLISHED_FROM, PUBLISHED_RANGE, PROVISIONAL_ESTIMATE,
    AWAITING_FACILITY_QUOTE, FACILITY_QUOTE_RECEIVED, CUSTOMER_PRICE_PENDING,
    CUSTOMER_PRICE_SENT, CUSTOMER_PRICE_APPROVED, CUSTOMER_PRICE_DECLINED, QUOTE_EXPIRED,
)

_PROVISIONAL_STATES = frozenset({
    PUBLISHED_FROM, PUBLISHED_RANGE, PROVISIONAL_ESTIMATE, AWAITING_FACILITY_QUOTE,
})
_FINAL_STATES = frozenset({FACILITY_QUOTE_RECEIVED, CUSTOMER_PRICE_SENT, CUSTOMER_PRICE_APPROVED})

# service_rules pricing mode -> initial customer-facing pricing state.
_MODE_STATE = {
    sr.EXACT: PUBLISHED_EXACT,
    sr.FROM: PUBLISHED_FROM,
    sr.RANGE: PUBLISHED_RANGE,
    sr.FACILITY_QUOTE: AWAITING_FACILITY_QUOTE,
    sr.MEASURED: PROVISIONAL_ESTIMATE,
    sr.WEIGHT_CONFIRMED: PROVISIONAL_ESTIMATE,
    sr.B2B_SALES_QUOTE: AWAITING_FACILITY_QUOTE,
}


def state_from_mode(pricing_mode: str) -> str:
    return _MODE_STATE.get(pricing_mode, AWAITING_FACILITY_QUOTE)


def is_provisional(state: str) -> bool:
    return state in _PROVISIONAL_STATES


def is_final(state: str) -> bool:
    return state in _FINAL_STATES


def _amt(v, currency: str = "AED") -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return f"{currency} 0"
    return f"{currency} {int(f) if f == int(f) else round(f, 2)}"


def present_price(
    state: str,
    *,
    currency: str = "AED",
    exact=None,
    minimum=None,
    maximum=None,
    item_label: str | None = None,
) -> str:
    """The short customer-facing price sentence for a pricing state. Provisional
    states are always qualified with 'confirm the exact amount after inspection';
    a final price ends with the single approval question."""
    label = (item_label or "This").strip()
    if state == PUBLISHED_EXACT and exact is not None:
        return f"{label} is {_amt(exact, currency)}."
    if state == PUBLISHED_FROM and minimum is not None:
        return f"{label} starts from {_amt(minimum, currency)}."
    if state == PUBLISHED_RANGE and minimum is not None and maximum is not None:
        return (f"{label} is usually around {_amt(minimum, currency)} to "
                f"{_amt(maximum, currency)}, depending on the item.")
    if state == PROVISIONAL_ESTIMATE and exact is not None:
        return (f"The estimated price is {_amt(exact, currency)}. "
                "We'll confirm the exact amount after inspection.")
    if state == PROVISIONAL_ESTIMATE and minimum is not None and maximum is not None:
        return (f"The estimated price is around {_amt(minimum, currency)} to "
                f"{_amt(maximum, currency)}. We'll confirm the exact amount after inspection.")
    if state == AWAITING_FACILITY_QUOTE:
        return "We'll collect the item and confirm the exact price after the facility checks it."
    if state in (FACILITY_QUOTE_RECEIVED, CUSTOMER_PRICE_SENT) and exact is not None:
        return f"The facility has checked the item. The final price is {_amt(exact, currency)}. Shall I proceed?"
    if state == QUOTE_EXPIRED:
        return "That quote has expired. We'll re-confirm the price with the facility."
    # Safe provisional default — never implies a final/confirmed price.
    return "We'll confirm the exact price after the facility checks the item."


def order_summary_price_line(state: str, *, currency: str = "AED", exact=None, minimum=None) -> str:
    """The price line for a provisional order SUMMARY (spec §5)."""
    if is_final(state) and exact is not None:
        return f"Price: {_amt(exact, currency)}"
    if state == PUBLISHED_EXACT and exact is not None:
        return f"Price: {_amt(exact, currency)}"
    if minimum is not None:
        return f"Estimated price: from {_amt(minimum, currency)}. Final price confirmed after inspection."
    return "Price: To be confirmed after facility inspection."
