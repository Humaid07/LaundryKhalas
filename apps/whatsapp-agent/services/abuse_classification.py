"""Deterministic abuse / threat classification for the WhatsApp agent.

Backend-authoritative classifier that decides whether a customer's (aggregated)
turn is genuinely ABUSIVE / THREATENING — and therefore needs human intervention
with the AI paused — versus ordinary DISSATISFACTION (unhappy but civil), which
stays in the normal complaint/support flow. Claude may PROPOSE a classification,
but this deterministic layer is the enforcement mechanism (CLAUDE.md §6: risky
actions are backend-decided, never left to the model alone).

Pure + config-driven (config/abuse_rules.json). No LLM call, no DB, no network —
so it is fast enough to run inline on every aggregated turn and fully unit-testable.

Key distinctions it makes:
  * Profanity ABOUT the service ("this service is fucking slow") → angry/profane
    but NOT takeover, vs profanity/insult AT a person ("you are a fucking idiot")
    → DIRECT_INSULT → takeover.
  * Ordinary dissatisfaction ("expensive", "too slow", "terrible service",
    "nobody replied") → negative sentiment, NO abuse flag, NO takeover.
  * Threats to staff/drivers/facility ("I'll hurt the driver") → THREAT with a
    severity, immediate takeover, critical priority.
  * Repetition across the aggregated turn / prior events escalates the category
    and severity (REPEATED_ABUSE / SEVERE_HOSTILITY).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

_CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "abuse_rules.json"

# --- Vocabularies -----------------------------------------------------------
SENTIMENT_POSITIVE = "POSITIVE"
SENTIMENT_NEUTRAL = "NEUTRAL"
SENTIMENT_NEGATIVE = "NEGATIVE"
SENTIMENT_ANGRY = "ANGRY"

ANGER_NONE, ANGER_LOW, ANGER_MEDIUM, ANGER_HIGH, ANGER_EXTREME = (
    "NONE", "LOW", "MEDIUM", "HIGH", "EXTREME")

# Abuse categories (spec).
CAT_NONE = "NONE"
CAT_GENERAL_PROFANITY = "GENERAL_PROFANITY"
CAT_DIRECT_INSULT = "DIRECT_INSULT"
CAT_DEROGATORY = "DEROGATORY_LANGUAGE"
CAT_HATE_OR_SLUR = "HATE_OR_SLUR"
CAT_SEXUAL_HARASSMENT = "SEXUAL_HARASSMENT"
CAT_THREAT = "THREAT"
CAT_REPEATED_ABUSE = "REPEATED_ABUSE"
CAT_SEVERE_HOSTILITY = "SEVERE_HOSTILITY"

# Targets (spec).
TGT_NONE = "NONE"
TGT_BUSINESS = "BUSINESS"
TGT_AI_AGENT = "AI_AGENT"
TGT_HUMAN_STAFF = "HUMAN_STAFF"
TGT_DRIVER = "DRIVER"
TGT_FACILITY = "FACILITY"
TGT_OTHER_PERSON = "OTHER_PERSON"
TGT_UNSPECIFIED = "UNSPECIFIED"

# Threat severities (spec).
THREAT_NONE, THREAT_LOW, THREAT_MEDIUM, THREAT_HIGH, THREAT_IMMINENT = (
    "NONE", "LOW", "MEDIUM", "HIGH", "IMMINENT")

# Recommended Operations priority.
PRIO_NORMAL, PRIO_MEDIUM, PRIO_HIGH, PRIO_CRITICAL = ("NORMAL", "MEDIUM", "HIGH", "CRITICAL")

# Customer-safe response type the reply layer should use.
RESP_NORMAL = "NORMAL"                       # no special handling
RESP_COMPLAINT_EMPATHY = "COMPLAINT_EMPATHY" # unhappy/profane-about-service → empathise, keep helping
RESP_TRANSFER_HOLDING = "TRANSFER_HOLDING"   # abuse/threat → one calm transfer message, pause AI

_SEVERITY_ORDER = {THREAT_NONE: 0, THREAT_LOW: 1, THREAT_MEDIUM: 2, THREAT_HIGH: 3, THREAT_IMMINENT: 4}


@lru_cache(maxsize=1)
def _config() -> dict:
    with _CONFIG_FILE.open(encoding="utf-8") as fh:
        return json.load(fh)


@dataclass(frozen=True)
class EscalationClassification:
    customer_sentiment: str
    anger_level: str
    abuse_detected: bool
    abuse_category: str
    abuse_target: str
    threat_detected: bool
    threat_severity: str
    human_intervention_required: bool
    confidence: float
    reason_codes: list[str] = field(default_factory=list)
    customer_safe_response_type: str = RESP_NORMAL
    recommended_priority: str = PRIO_NORMAL

    def as_dict(self) -> dict:
        return {
            "customer_sentiment": self.customer_sentiment,
            "anger_level": self.anger_level,
            "abuse_detected": self.abuse_detected,
            "abuse_category": self.abuse_category,
            "abuse_target": self.abuse_target,
            "threat_detected": self.threat_detected,
            "threat_severity": self.threat_severity,
            "human_intervention_required": self.human_intervention_required,
            "confidence": self.confidence,
            "reason_codes": list(self.reason_codes),
            "customer_safe_response_type": self.customer_safe_response_type,
            "recommended_priority": self.recommended_priority,
        }


# --- Text helpers -----------------------------------------------------------
def _normalize(text: str) -> str:
    t = (text or "").lower()
    # Light leet / obfuscation normalisation so "f*ck" / "a55" still match.
    t = t.replace("@", "a").replace("$", "s").replace("*", "").replace("!", "i")
    t = re.sub(r"\s+", " ", t)
    return t


def _contains_any(text: str, terms) -> list[str]:
    """Return the terms present as whole words / phrases (order preserved)."""
    hits = []
    for term in terms:
        if " " in term:
            if term in text:
                hits.append(term)
        elif re.search(rf"\b{re.escape(term)}\b", text):
            hits.append(term)
    return hits


def _resolve_target(text: str, cfg: dict) -> str:
    tt = cfg["staff_target_terms"]
    # Most specific first: driver / facility / human staff / AI.
    if _contains_any(text, tt["DRIVER"]):
        return TGT_DRIVER
    if _contains_any(text, tt["FACILITY"]):
        return TGT_FACILITY
    if _contains_any(text, tt["HUMAN_STAFF"]):
        return TGT_HUMAN_STAFF
    if _contains_any(text, tt["AI_AGENT"]):
        return TGT_AI_AGENT
    return TGT_UNSPECIFIED


def _has_second_person(text: str, cfg: dict) -> bool:
    return bool(_contains_any(text, cfg["second_person_markers"]))


# --- Classification ---------------------------------------------------------
def classify(text: str, *, prior_abuse_event_count: int = 0,
             config: dict | None = None) -> EscalationClassification:
    """Classify a customer's aggregated turn.

    ``prior_abuse_event_count`` is how many abusive turns this conversation has
    already produced (for REPEATED_ABUSE / SEVERE_HOSTILITY escalation). The full
    logical turn should be passed (fragments already combined), not one fragment.
    """
    cfg = config or _config()
    thr = cfg["thresholds"]
    raw = text or ""
    t = _normalize(raw)

    reasons: list[str] = []
    profanity_hits = _contains_any(t, cfg["profanity"])
    insult_hits = _contains_any(t, cfg["insult_nouns"])
    slur_hits = _contains_any(t, cfg["slurs"])
    sexual_hits = _contains_any(t, cfg["sexual_harassment"])
    threat_verb_hits = _contains_any(t, cfg["threat_verbs"])
    presence_hits = _contains_any(t, cfg["threat_presence_phrases"])
    imminent_hits = _contains_any(t, cfg["imminent_threat_phrases"])
    dissatisfaction_hits = _contains_any(t, cfg["dissatisfaction_terms"])
    directed = _has_second_person(t, cfg)
    target = _resolve_target(t, cfg)

    # --- Threats (highest priority) -----------------------------------------
    threat_detected = False
    threat_severity = THREAT_NONE
    if imminent_hits or (threat_verb_hits and presence_hits):
        threat_detected, threat_severity = True, THREAT_IMMINENT
        reasons.append("IMMINENT_THREAT")
    elif threat_verb_hits and (target in (TGT_DRIVER, TGT_HUMAN_STAFF, TGT_FACILITY) or directed):
        threat_detected, threat_severity = True, THREAT_HIGH
        reasons.append("THREAT_TO_PERSON")
    elif threat_verb_hits or presence_hits:
        threat_detected, threat_severity = True, THREAT_MEDIUM
        reasons.append("THREAT_LANGUAGE")

    # --- Abuse category ------------------------------------------------------
    category = CAT_NONE
    if slur_hits:
        category = CAT_HATE_OR_SLUR
        reasons.append("SLUR_OR_HATE")
    elif sexual_hits:
        category = CAT_SEXUAL_HARASSMENT
        reasons.append("SEXUAL_HARASSMENT")
    elif threat_detected:
        category = CAT_THREAT
    elif (profanity_hits or insult_hits) and directed:
        # Directed at a person → a personal attack, not just venting.
        category = CAT_DIRECT_INSULT if profanity_hits else CAT_DEROGATORY
        reasons.append("PERSONAL_ATTACK")
    elif profanity_hits:
        # Profanity present but describing the service/situation, no personal target.
        category = CAT_GENERAL_PROFANITY
        reasons.append("GENERAL_PROFANITY")
    elif insult_hits and not directed:
        # An insult noun with no personal target (rare) — treat as general profanity.
        category = CAT_GENERAL_PROFANITY
        reasons.append("GENERAL_PROFANITY")

    # --- Repetition escalation ----------------------------------------------
    this_is_abuse = category not in (CAT_NONE, CAT_GENERAL_PROFANITY) or threat_detected
    total_events = prior_abuse_event_count + (1 if (this_is_abuse or category == CAT_GENERAL_PROFANITY) else 0)
    if this_is_abuse and total_events >= thr["severe_hostility_min_events"]:
        category = CAT_SEVERE_HOSTILITY
        reasons.append("SEVERE_HOSTILITY")
    elif this_is_abuse and total_events >= thr["repeated_abuse_min_events"]:
        category = CAT_REPEATED_ABUSE
        reasons.append("REPEATED_ABUSE")

    # --- Target normalisation -----------------------------------------------
    if category == CAT_GENERAL_PROFANITY and not directed:
        abuse_target = TGT_BUSINESS
    elif category in (CAT_NONE,):
        abuse_target = TGT_NONE if not dissatisfaction_hits else TGT_BUSINESS
    elif target == TGT_UNSPECIFIED and directed:
        abuse_target = TGT_AI_AGENT   # "you" with no staff word → the assistant
    else:
        abuse_target = target if target != TGT_UNSPECIFIED else TGT_UNSPECIFIED

    # --- Human-intervention decision (deterministic) ------------------------
    abuse_detected = category not in (CAT_NONE, CAT_GENERAL_PROFANITY)
    intervention = bool(
        (threat_detected and _SEVERITY_ORDER[threat_severity] >= _SEVERITY_ORDER[THREAT_MEDIUM])
        or category in (CAT_DIRECT_INSULT, CAT_DEROGATORY, CAT_HATE_OR_SLUR,
                        CAT_SEXUAL_HARASSMENT, CAT_THREAT, CAT_REPEATED_ABUSE,
                        CAT_SEVERE_HOSTILITY)
    )
    # General profanity alone doesn't pause the AI unless it keeps repeating.
    if (not intervention and category == CAT_GENERAL_PROFANITY
            and total_events >= thr["general_profanity_intervention_after_events"]):
        category = CAT_REPEATED_ABUSE
        abuse_detected = True
        intervention = True
        reasons.append("REPEATED_PROFANITY")

    # --- Sentiment / anger ---------------------------------------------------
    if threat_detected or category in (CAT_HATE_OR_SLUR, CAT_SEVERE_HOSTILITY):
        sentiment, anger = SENTIMENT_ANGRY, ANGER_EXTREME
    elif abuse_detected:
        sentiment, anger = SENTIMENT_ANGRY, ANGER_HIGH
    elif category == CAT_GENERAL_PROFANITY:
        sentiment, anger = SENTIMENT_ANGRY, ANGER_HIGH
    elif dissatisfaction_hits:
        sentiment, anger = SENTIMENT_NEGATIVE, ANGER_MEDIUM
        reasons.append("DISSATISFACTION")
    else:
        sentiment, anger = SENTIMENT_NEUTRAL, ANGER_NONE

    # --- Priority ------------------------------------------------------------
    if threat_detected and _SEVERITY_ORDER[threat_severity] >= _SEVERITY_ORDER[THREAT_HIGH]:
        priority = PRIO_CRITICAL
    elif category in (CAT_HATE_OR_SLUR, CAT_SEXUAL_HARASSMENT) or threat_detected:
        priority = PRIO_CRITICAL if category == CAT_HATE_OR_SLUR else PRIO_HIGH
    elif category in (CAT_REPEATED_ABUSE, CAT_SEVERE_HOSTILITY):
        priority = PRIO_HIGH
    elif intervention:
        priority = PRIO_MEDIUM
    else:
        priority = PRIO_NORMAL

    # --- Response type -------------------------------------------------------
    if intervention:
        response_type = RESP_TRANSFER_HOLDING
    elif category == CAT_GENERAL_PROFANITY or dissatisfaction_hits:
        response_type = RESP_COMPLAINT_EMPATHY
    else:
        response_type = RESP_NORMAL

    # --- Confidence ----------------------------------------------------------
    if slur_hits or imminent_hits or (threat_verb_hits and (presence_hits or directed)):
        confidence = 0.95
    elif intervention:
        confidence = 0.85
    elif category == CAT_GENERAL_PROFANITY:
        confidence = 0.7
    elif dissatisfaction_hits:
        confidence = 0.6
    else:
        confidence = 0.5

    if not reasons:
        reasons.append("NO_ISSUE")

    return EscalationClassification(
        customer_sentiment=sentiment, anger_level=anger,
        abuse_detected=abuse_detected, abuse_category=category, abuse_target=abuse_target,
        threat_detected=threat_detected, threat_severity=threat_severity,
        human_intervention_required=intervention, confidence=confidence,
        reason_codes=reasons, customer_safe_response_type=response_type,
        recommended_priority=priority,
    )


# --- Intervention-reason mapping (for the persistent takeover state) ---------
INTERVENTION_REASON_ABUSE = "ABUSIVE_LANGUAGE"
INTERVENTION_REASON_THREAT = "THREAT"


def intervention_reason(result: EscalationClassification) -> str | None:
    """Map a classification to the persistent takeover reason, or None if no
    intervention is required."""
    if not result.human_intervention_required:
        return None
    if result.threat_detected or result.abuse_category == CAT_THREAT:
        return INTERVENTION_REASON_THREAT
    return INTERVENTION_REASON_ABUSE
