"""Deterministic abuse/threat classification — the enforcement layer that decides
human intervention. Mirrors the feature spec's classification test matrix:
ordinary dissatisfaction must NOT trigger takeover; directed insults, slurs,
sexual harassment and threats MUST; general profanity is angry-but-not-takeover
until it repeats.
"""
from services import abuse_classification as ac


def c(text, prior=0):
    return ac.classify(text, prior_abuse_event_count=prior)


# ===================== dissatisfaction is NOT abuse =========================
def test_expensive_is_not_abuse():
    r = c("This is too expensive.")
    assert r.abuse_detected is False
    assert r.human_intervention_required is False
    assert r.abuse_category == ac.CAT_NONE
    assert r.customer_safe_response_type == ac.RESP_COMPLAINT_EMPATHY


def test_terrible_service_is_dissatisfaction_not_abuse():
    r = c("This service is terrible and nobody has helped me.")
    assert r.human_intervention_required is False
    assert r.customer_sentiment == ac.SENTIMENT_NEGATIVE
    assert "DISSATISFACTION" in r.reason_codes


def test_various_unhappy_messages_do_not_trigger_takeover():
    for msg in ["This is taking too long.", "I am disappointed.",
                "I need this fixed now.", "Why has nobody replied?",
                "This service is terrible."]:
        r = c(msg)
        assert r.human_intervention_required is False, msg
        assert r.abuse_detected is False, msg


# ===================== general profanity (about the service) ================
def test_general_profanity_about_service_is_not_takeover():
    r = c("This fucking service is slow.")
    assert r.abuse_category == ac.CAT_GENERAL_PROFANITY
    assert r.human_intervention_required is False        # profane but not directed
    assert r.anger_level in (ac.ANGER_HIGH, ac.ANGER_EXTREME)
    assert r.customer_safe_response_type == ac.RESP_COMPLAINT_EMPATHY


def test_repeated_general_profanity_eventually_escalates():
    # 3rd profane-only turn crosses the configured threshold.
    r = c("this fucking service again", prior=2)
    assert r.human_intervention_required is True
    assert r.abuse_category == ac.CAT_REPEATED_ABUSE


# ===================== directed insults ====================================
def test_direct_insult_triggers_intervention():
    r = c("You are a fucking idiot.")
    assert r.abuse_detected is True
    assert r.abuse_category == ac.CAT_DIRECT_INSULT
    assert r.human_intervention_required is True
    assert r.abuse_target == ac.TGT_AI_AGENT
    assert r.customer_safe_response_type == ac.RESP_TRANSFER_HOLDING
    assert ac.intervention_reason(r) == "ABUSIVE_LANGUAGE"


def test_you_are_useless_is_directed_insult():
    r = c("You are useless")
    assert r.abuse_category in (ac.CAT_DIRECT_INSULT, ac.CAT_DEROGATORY)
    assert r.human_intervention_required is True


def test_insult_at_staff_targets_human_staff():
    r = c("your staff are complete morons")
    assert r.abuse_target == ac.TGT_HUMAN_STAFF
    assert r.human_intervention_required is True


# ===================== slurs / hate ========================================
def test_slur_is_high_severity_intervention():
    r = c("you people are retards")
    assert r.abuse_category == ac.CAT_HATE_OR_SLUR
    assert r.human_intervention_required is True
    assert r.recommended_priority == ac.PRIO_CRITICAL
    assert r.confidence >= 0.9


# ===================== sexual harassment ===================================
def test_sexual_harassment_triggers_intervention():
    r = c("send nudes")
    assert r.abuse_category == ac.CAT_SEXUAL_HARASSMENT
    assert r.human_intervention_required is True
    assert r.recommended_priority in (ac.PRIO_HIGH, ac.PRIO_CRITICAL)


# ===================== threats =============================================
def test_threat_to_driver_is_imminent_or_high_and_critical():
    r = c("I will hurt the driver.")
    assert r.threat_detected is True
    assert r.threat_severity in (ac.THREAT_HIGH, ac.THREAT_IMMINENT)
    assert r.abuse_category in (ac.CAT_THREAT,)
    assert r.human_intervention_required is True
    assert r.recommended_priority == ac.PRIO_CRITICAL
    assert ac.intervention_reason(r) == "THREAT"


def test_coming_to_office_threat_is_imminent():
    r = c("I'll come there and show you")
    assert r.threat_detected is True
    assert r.threat_severity == ac.THREAT_IMMINENT
    assert r.recommended_priority == ac.PRIO_CRITICAL


def test_property_threat_detected():
    r = c("I will burn your facility down")
    assert r.threat_detected is True
    assert r.human_intervention_required is True


# ===================== aggregated / repeated turn ==========================
def test_aggregated_abusive_turn_classified_once():
    combined = "You people are useless fucking idiots I'll come there and show you"
    r = c(combined)
    # A single classification over the combined turn: threat dominates.
    assert r.threat_detected is True
    assert r.human_intervention_required is True
    assert r.recommended_priority == ac.PRIO_CRITICAL


def test_repeated_abuse_escalates_category():
    r = c("you are an idiot", prior=1)      # 2nd abusive event
    assert r.abuse_category == ac.CAT_REPEATED_ABUSE
    r2 = c("you idiot", prior=2)            # 3rd → severe hostility
    assert r2.abuse_category == ac.CAT_SEVERE_HOSTILITY
    assert r2.anger_level == ac.ANGER_EXTREME


# ===================== structured-output contract ==========================
def test_result_is_fully_structured():
    d = c("You are a fucking idiot.").as_dict()
    for key in ["customer_sentiment", "anger_level", "abuse_detected", "abuse_category",
                "abuse_target", "threat_detected", "threat_severity",
                "human_intervention_required", "confidence", "reason_codes",
                "customer_safe_response_type", "recommended_priority"]:
        assert key in d
    assert isinstance(d["reason_codes"], list) and d["reason_codes"]


def test_clean_message_is_neutral_no_intervention():
    r = c("Hi, I'd like to book a wash and fold pickup tomorrow.")
    assert r.customer_sentiment == ac.SENTIMENT_NEUTRAL
    assert r.abuse_detected is False
    assert r.human_intervention_required is False
    assert r.customer_safe_response_type == ac.RESP_NORMAL


def test_intervention_reason_none_when_not_required():
    assert ac.intervention_reason(c("this is expensive")) is None
