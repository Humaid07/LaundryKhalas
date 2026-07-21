"""Layer 1 of the domain guard: a cheap, deterministic keyword/pattern check
that runs before any LLM call. Layer 2 (the system prompt's own domain
restriction) lives in agents/whatsapp_agent/prompts.py - the two layers are
independent, so a prompt-injection attempt that somehow bypasses the system
prompt still can't get an in-domain LLM call for an out-of-domain message,
and a false negative here still gets caught by the system prompt.
"""
import re
from enum import Enum

from rules import refusal_message


class Domain(str, Enum):
    IN_DOMAIN = "in_domain"
    OUT_OF_DOMAIN = "out_of_domain"
    UNCERTAIN = "uncertain"


_IN_DOMAIN_KEYWORDS = [
    # core services
    "laundry", "laundr", "dry clean", "dryclean", "cleaning", "clean my",
    "wash and fold", "wash & fold", "ironing", "iron my", "press my",
    "stain", "carpet", "curtain", "sofa", "upholstery", "duvet", "blanket",
    # fulfilment
    "pickup", "pick up", "pick-up", "delivery", "deliver", "drop off", "drop-off",
    "collect", "collection",
    # brand / commercial
    "laundrykhalaas", "laundrykhalas", "laundry khalas", "laundry khalaas",
    "price", "pricing", "cost", "how much", "rate", "charge",
    "order", "booking", "book a", "schedule", "reschedule", "cancel my order",
    "policy", "service area", "area you cover", "do you cover",
    "status of my order", "track my order", "add items", "add more",
    "customer support", "customer service", "speak to support",
    "speak to a human", "speak to an agent", "call support",
    "business laundry", "wash & fold", "wash and fold",
    # everyday laundry situations
    "spilled", "spill", "dirty clothes", "dirty shirt", "smell", "smelly",
    "wrinkle", "shrink", "coffee stain", "wine stain", "grease stain",
]

_OUT_OF_DOMAIN_KEYWORDS = [
    "python", "javascript", "code", "programming", "sql", "html", "css",
    "president", "election", "politics", "political", "government", "war",
    "religion", "god", "quran", "bible", "prayer", "islam", "christianity",
    "stock", "crypto", "bitcoin", "invest", "finance", "loan", "mortgage",
    "diagnos", "symptom", "medicine", "prescription", "doctor", "disease",
    "joke", "funny story", "poem", "recipe", "cook", "weather",
    "relationship advice", "dating advice", "who is", "what is the capital",
    "ignore previous instructions", "ignore your instructions", "system prompt",
    "api key", "your instructions", "you are actually", "pretend you are",
    "act as", "jailbreak",
]

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.I),
    re.compile(r"reveal\s+(your\s+)?(system\s+prompt|instructions)", re.I),
    re.compile(r"(what|tell me)\s+.*\bapi\s*key\b", re.I),
    re.compile(r"pretend\s+you\s+are", re.I),
    re.compile(r"act\s+as\s+(a|an)\s+", re.I),
    re.compile(r"you\s+are\s+now\s+", re.I),
]


def classify(text: str) -> Domain:
    lowered = text.lower().strip()
    if not lowered:
        return Domain.UNCERTAIN

    if any(p.search(lowered) for p in _INJECTION_PATTERNS):
        return Domain.OUT_OF_DOMAIN

    has_in_domain = any(kw in lowered for kw in _IN_DOMAIN_KEYWORDS)
    has_out_of_domain = any(kw in lowered for kw in _OUT_OF_DOMAIN_KEYWORDS)

    if has_out_of_domain and not has_in_domain:
        return Domain.OUT_OF_DOMAIN
    if has_in_domain:
        return Domain.IN_DOMAIN

    # Short greetings / acks are fine to let through to the agent, which will
    # ask a clarifying laundry-related question rather than refuse outright.
    if len(lowered.split()) <= 4:
        return Domain.UNCERTAIN

    return Domain.UNCERTAIN


# RULE 1 — the exact out-of-domain refusal is configured in
# config/whatsapp_agent_rules.json (domain.refusal_message).
REFUSAL_MESSAGE = refusal_message()
