"""Reply text templates for the WhatsApp Operations happy-path agent.

All customer-facing text is built here from DB/config-derived values only
(service labels, area, computed total, facility name) - never from
freeform LLM generation of facts. The templates are passed through
llm_service so every draft still goes through the audited gateway (see
llm/providers/mock.py), but the *content* is deterministic and reviewable.
"""

_SERVICE_LABELS = {
    "wash_and_fold": "Wash & Fold",
    "dry_cleaning": "Dry Cleaning",
    "ironing": "Ironing",
}

_FIELD_PROMPTS = {
    "service_type": "the type of service you'd like (wash & fold, dry cleaning, or ironing)",
    "area": "the pickup area/neighborhood",
    "pickup_when": "your preferred pickup day (today or tomorrow) and time of day",
}


def render_followup_question(customer_ctx: dict, *, missing_fields: list[str]) -> str:
    name = customer_ctx.get("name") or "there"
    asks = [_FIELD_PROMPTS[f] for f in missing_fields if f in _FIELD_PROMPTS]
    joined = "; and ".join(asks) if len(asks) <= 1 else "; ".join(asks[:-1]) + f"; and {asks[-1]}"
    return (
        f"Hi {name}! Happy to arrange your laundry pickup. "
        f"Could you please share {joined}?"
    )


def render_confirmation(
    customer_ctx: dict,
    *,
    service_type: str,
    pickup_when: str,
    total: float,
    currency: str,
    facility_name: str,
) -> str:
    name = customer_ctx.get("name") or "there"
    label = _SERVICE_LABELS.get(service_type, service_type)
    area_city = customer_ctx.get("area_city", "your area")
    return (
        f"Hi {name}! Your {label} pickup ({pickup_when}) near {area_city} is confirmed. "
        f"Estimated total: {currency} {total:.2f}. Your order will be processed by "
        f"{facility_name}. We'll follow up if anything needs to change."
    )


def render_escalation_notice(customer_ctx: dict) -> str:
    name = customer_ctx.get("name") or "there"
    return (
        f"Hi {name}, thanks for your patience - a member of our team will follow up "
        "shortly to make sure we get this exactly right for you."
    )
