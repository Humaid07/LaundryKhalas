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
    "bulk_outsourcing", "facility_partnership", "airbnb", "other",
)

# The qualifying details the commercial team needs (spec §18 Commercial). Consumer
# pricing is NEVER given as a commercial quote — all commercial pricing goes to Sales.
QUALIFYING_FIELDS = (
    "first name", "business name", "email", "contact number", "required services",
    "estimated weekly volume", "volume unit", "frequency", "location",
    "preferred contact method",
)

_KEYWORD_TYPE: tuple[tuple[tuple[str, ...], str], ...] = (
    (("hotel", "guest laundry", "guest room", "hospitality", "resort"), "hotel"),
    (("airbnb", "air bnb", "short-term rental", "short term rental", "holiday home", "vacation rental"), "airbnb"),
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


def may_use_consumer_pricing(business_type: str) -> bool:
    """True only for an Airbnb enquiry — a SMALL Airbnb requirement may use the standard
    consumer service when the volume genuinely fits (spec §18). Every other commercial
    type is priced by Sales, never on consumer rates."""
    return business_type == "airbnb"


def trial_note() -> str:
    """The approved trial-collection stance (spec §18): small trials may be free, large
    ones may be chargeable — never promise a free large-volume trial."""
    return ("Small trial collections may be available at no charge. A larger trial may be "
            "chargeable, and the commercial team will confirm this.")


def acknowledgement(business_type: str) -> str:
    """A safe B2B acknowledgement: routes to the commercial team + asks for the key
    qualifying details (spec §18). Never quotes a price or promises terms."""
    label = {
        "hotel": "hotel laundry",
        "restaurant": "restaurant / linen",
        "uniform": "uniform cleaning",
        "commercial_laundry": "commercial laundry",
        "bulk_outsourcing": "bulk / outsourced laundry",
        "facility_partnership": "partnership",
        "airbnb": "Airbnb laundry",
    }.get(business_type, "business laundry")
    msg = (
        f"Thanks for reaching out about {label}. I've passed this to our commercial "
        "partnerships team, who'll get in touch. To help them prepare, could you share "
        "your company name, business email, the services you need, your approximate weekly "
        "volume, how often you need collection, and your location?"
    )
    if business_type == "airbnb":
        msg += (" If it's just a small Airbnb requirement, we may be able to handle it on our "
                "standard service.")
    return msg
