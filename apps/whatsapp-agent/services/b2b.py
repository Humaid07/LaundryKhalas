"""B2B enquiry classification + acknowledgement (pure, deterministic).

Hotel / restaurant / uniform / commercial / bulk-outsourcing / partnership
enquiries are routed to the commercial team and tracked as their own lead entity
— never pushed through the consumer pickup funnel, never counted in consumer
conversion metrics. This module classifies the business type and composes a safe
acknowledgement (no pricing promises). Detection of *whether* a message is B2B
already lives in ``services/escalation`` (category ``b2b_quotation``); persistence
lives in ``db/repositories/b2b_leads_repo.py``.
"""
from __future__ import annotations

BUSINESS_TYPES = (
    "hotel", "restaurant", "uniform", "commercial_laundry",
    "bulk_outsourcing", "facility_partnership", "other",
)

_KEYWORD_TYPE: tuple[tuple[tuple[str, ...], str], ...] = (
    (("hotel", "guest laundry", "guest room", "hospitality", "resort"), "hotel"),
    (("restaurant", "linen", "napkin", "tablecloth", "cafe", "catering"), "restaurant"),
    (("uniform", "staff clothing", "workwear", "scrubs"), "uniform"),
    (("partner", "partnership", "become a facility", "supply you", "vendor"), "facility_partnership"),
    (("bulk", "outsourc", "large volume", "wholesale", "contract"), "bulk_outsourcing"),
    (("commercial laundry", "commercial", "business laundry", "company laundry", "b2b"), "commercial_laundry"),
)


def classify_business_type(text: str | None) -> str:
    t = (text or "").lower()
    for keywords, btype in _KEYWORD_TYPE:
        if any(k in t for k in keywords):
            return btype
    return "other"


def acknowledgement(business_type: str) -> str:
    """A safe B2B acknowledgement: routes to the commercial team + asks for the
    key qualifying details. Never quotes a price or promises terms."""
    label = {
        "hotel": "hotel laundry",
        "restaurant": "restaurant / linen",
        "uniform": "uniform cleaning",
        "commercial_laundry": "commercial laundry",
        "bulk_outsourcing": "bulk / outsourced laundry",
        "facility_partnership": "partnership",
    }.get(business_type, "business laundry")
    return (
        f"Thanks for reaching out about {label}. I've passed this to our commercial "
        "partnerships team, who'll get in touch. To help them prepare, could you share "
        "your company name, the services you need, and your approximate volume?"
    )
