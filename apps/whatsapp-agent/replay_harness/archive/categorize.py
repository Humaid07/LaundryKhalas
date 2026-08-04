"""Best-effort conversation categorization from inbound customer text.

Pre-replay, keyword-based. Used only for filtering/reporting (`--category`), NOT
for evaluation. The agent's own service resolution is authoritative at runtime.
"""
from __future__ import annotations

from ..core.models import Conversation

# Ordered: first match wins for the primary category. Keep specific before generic.
_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("refund", ("refund", "money back", "chargeback")),
    ("complaint", ("complaint", "not happy", "unhappy", "terrible", "worst", "ruined", "damaged", "damage", "stain still", "poor service")),
    ("missing_item", ("missing", "lost my", "didn't get back", "not returned", "where is my")),
    ("wrong_delivery", ("wrong delivery", "wrong order", "not mine", "someone else")),
    ("delivery_delay", ("where is my delivery", "delivery late", "still not delivered", "delayed delivery")),
    ("pickup_delay", ("pickup late", "no one came", "driver didn't", "waiting for pickup")),
    ("carpet", ("carpet", "rug")),
    ("curtain", ("curtain",)),
    ("shoes", ("shoe", "sneaker", "boots", "espadrille")),
    ("bags", ("handbag", "bag care", "backpack", "wallet", "suitcase", "briefcase")),
    ("alterations", ("alter", "shorten", "shortening", "take in", "hemming", "hem ", "resize", "tailor", "stitch")),
    ("repair", ("repair", "fix", "broken zip", "zipper", "torn", "rip ")),
    ("leather", ("leather", "suede")),
    ("wedding_dress", ("wedding dress", "bridal", "gown")),
    ("toys", ("soft toy", "mascot", "teddy")),
    ("restoration", ("restore", "restoration", "yellowing")),
    ("bedding", ("duvet", "comforter", "bed sheet", "bedding", "blanket", "mattress")),
    ("press_only", ("press only", "iron only", "just press", "just iron")),
    ("b2b", ("hotel", "restaurant", "company", "bulk", "corporate", "b2b", "wholesale", "monthly contract")),
    ("campaign_reply", ("stop", "unsubscribe", "promo code", "offer i received")),
    ("location_pickup", ("pick up", "pickup", "collect", "collection", "location", "area", "marina", "jbr", "downtown")),
    ("price_negotiation", ("too expensive", "discount", "best price", "cheaper", "any offer", "lower price")),
    ("pricing_enquiry", ("how much", "price", "pricing", "rate", "cost", "charges")),
    ("wash_fold", ("wash and fold", "wash & fold", "wash fold", "laundry")),
    ("clean_press", ("dry clean", "clean and press", "wash and iron")),
    ("new_booking", ("book", "order", "pickup today", "collect today", "need laundry")),
    ("human_request", ("speak to", "call me", "agent", "human", "manager")),
]


def categorize(conv: Conversation) -> str:
    text = " ".join(
        (m.text or m.caption or "") for m in conv.inbound_messages
    ).lower()
    if not text.strip():
        return "empty_or_unusable"
    for label, keywords in _RULES:
        if any(k in text for k in keywords):
            return label
    return "general_enquiry"
