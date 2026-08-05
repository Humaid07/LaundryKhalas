"""Deterministic keyword rule engine.

Two roles:
  1. **Fallback** when the live model times out/errors in a way where a bare
     UNKNOWN would be worse than a confident keyword read (the caller decides).
  2. **Offline oracle** so the pytest suite exercises the full taxonomy without a
     live Anthropic key or token spend (conftest forces LLM_PROVIDER=mock).

In PRODUCTION the live Sonnet-5 classifier is authoritative; this engine is the
safety net, not the primary path. It is pure/deterministic (mirroring
services/abuse_classification.py) and never touches the DB or the model.

Priority matters: safety-sensitive intents (refund, reprocessing, damage,
missing item, disputes, human request) are detected BEFORE ordinary service or
pricing intents so a complaint is never masked by an incidental service word.
"""
from __future__ import annotations

import re

from classifier.context import ClassifierInput
from classifier.schema import Classification, ClassifierStatus, DetectedEntities

# --- service keyword → domain (ordered: longer / more-specific first) --------
# NB: dry cleaning → CLEAN_AND_PRESS unless a specialist context word is present
# (leather/shoe/bag/restoration), per the spec's service classification rules.
_SERVICE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("wash and fold", "WASH_AND_FOLD"),
    ("wash & fold", "WASH_AND_FOLD"),
    ("wash and iron", "CLEAN_AND_PRESS"),
    ("wash & iron", "CLEAN_AND_PRESS"),
    ("dry clean", "CLEAN_AND_PRESS"),
    ("dryclean", "CLEAN_AND_PRESS"),
    ("steam press", "PRESS_ONLY"),
    ("ironing", "PRESS_ONLY"),
    ("iron only", "PRESS_ONLY"),
    ("press only", "PRESS_ONLY"),
    ("wedding dress", "WEDDING_AND_EVENING_DRESSES"),
    ("evening dress", "WEDDING_AND_EVENING_DRESSES"),
    ("bridal", "WEDDING_AND_EVENING_DRESSES"),
    ("gown", "WEDDING_AND_EVENING_DRESSES"),
    ("carpet", "CARPETS_AND_RUGS"),
    ("rug", "CARPETS_AND_RUGS"),
    ("curtain", "CURTAINS"),
    ("drape", "CURTAINS"),
    ("sofa", "SOFA_AND_UPHOLSTERY"),
    ("couch", "SOFA_AND_UPHOLSTERY"),
    ("upholstery", "SOFA_AND_UPHOLSTERY"),
    ("bedding", "BEDDING_AND_HOME_TEXTILES"),
    ("duvet", "BEDDING_AND_HOME_TEXTILES"),
    ("blanket", "BEDDING_AND_HOME_TEXTILES"),
    ("sneaker", "SHOES"),
    ("trainer", "SHOES"),
    ("shoe", "SHOES"),
    ("handbag", "BAGS_AND_ACCESSORIES"),
    ("purse", "BAGS_AND_ACCESSORIES"),
    ("bag", "BAGS_AND_ACCESSORIES"),
    ("suit", "SUITS_AND_BLAZERS"),
    ("blazer", "SUITS_AND_BLAZERS"),
    ("tuxedo", "SUITS_AND_BLAZERS"),
    ("leather", "LEATHER"),
    ("teddy", "TOYS_AND_MASCOTS"),
    ("mascot", "TOYS_AND_MASCOTS"),
    ("plush", "TOYS_AND_MASCOTS"),
    ("kandura", "TRADITIONAL_WEAR"),
    ("abaya", "TRADITIONAL_WEAR"),
    ("thobe", "TRADITIONAL_WEAR"),
    ("jalabiya", "TRADITIONAL_WEAR"),
    ("trouser", "ALTERATIONS_AND_GARMENT_REPAIR"),
)

_B2B_KEYWORDS = (
    "hotel", "restaurant", "gym", "spa", "airbnb", "factory", "office building",
    "company", "salon", "uniform", "commercial linen", "linen collection",
    "daily pickup", "daily collection", "weekly pickup", "recurring order",
    "bulk", "branches", "institution", "kitchen linen", "guest laundry", "workwear",
)

_GREETINGS = (
    "hi", "hello", "hey", "hiya", "yo", "salam", "assalam", "assalamualaikum",
    "good morning", "good afternoon", "good evening", "gm", "hey there",
)

_AFFIRMATIVES = frozenset({
    "yes", "yeah", "yep", "yup", "ok", "okay", "sure", "correct", "confirm",
    "confirm it", "okay confirm", "ok confirm", "please confirm", "go ahead", "confirmed",
})

_WEIGHT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*kg", re.I)
_OPTION_RE = re.compile(r"\b(?:option\s*)?(\d{1,2})\b", re.I)
_PERCENT_RE = re.compile(r"(\d{1,3})\s*%|\b(\d{1,3})\s*percent", re.I)
_QTY_WORDS = {"a": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
              "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_TIME_RE = re.compile(r"\b(\d{1,2})\s*(?::\d{2})?\s*(am|pm)\b|\b(\d{1,2})\s*o'?clock\b", re.I)

_ADDRESS_WORDS = ("apartment", "apt", "flat", "villa", "tower", "building",
                  "street", "floor", "block", "jbr", "jlt", "marina", "downtown",
                  "residence", "room no", "house no")


def _has(text: str, *needles: str) -> bool:
    return any(n in text for n in needles)


def _hasw(text: str, *words: str) -> bool:
    """Word-START boundary match — matches 'rip'/'ripped' but NOT 'stripe',
    'sole' but NOT 'console'. Used for short repair tokens that would otherwise
    false-match as substrings of unrelated words."""
    return bool(re.search(r"\b(?:" + "|".join(re.escape(w) for w in words) + r")", text))


def _detect_services(text: str) -> list[str]:
    found: list[str] = []
    for kw, domain in _SERVICE_PATTERNS:
        if kw in text and domain not in found:
            found.append(domain)
    return found


def _detect_entities(text: str) -> DetectedEntities:
    ent = DetectedEntities()
    wm = _WEIGHT_RE.search(text)
    if wm:
        try:
            ent.mentioned_weight_kg = float(wm.group(1))
        except ValueError:
            pass
    # quantity: "two suits", "2 shirts"
    qm = re.search(r"\b(\d{1,3}|" + "|".join(_QTY_WORDS) + r")\s+([a-z]{3,})", text)
    if qm:
        raw_qty = qm.group(1)
        qty = int(raw_qty) if raw_qty.isdigit() else _QTY_WORDS.get(raw_qty)
        if qty:
            ent.mentioned_quantity = qty
            ent.mentioned_items = [f"{qty} {qm.group(2)}"]
    tm = _TIME_RE.search(text)
    if tm:
        ent.mentioned_time_text = tm.group(0).strip()
    for d in ("today", "tomorrow", "tonight", "monday", "tuesday", "wednesday",
              "thursday", "friday", "saturday", "sunday"):
        if d in text:
            ent.mentioned_date_text = d
            break
    return ent


def classify(ci: ClassifierInput) -> Classification:
    """Deterministic classification of one logical turn. Never raises."""
    text = (ci.message.text or "").strip().lower()
    convo = ci.conversation
    recent = ci.recent_context
    last_assistant = ""
    for item in reversed(recent):
        if item.role == "assistant":
            last_assistant = (item.text or "").lower()
            break

    services = _detect_services(text)
    entities = _detect_entities(text)
    secondary: list[str] = []
    reasons: list[str] = []

    def result(primary: str, **kw) -> Classification:
        # Pop unconditionally so an explicit reason_codes kwarg never collides
        # with the accumulated ``reasons`` list in the **kw expansion below.
        explicit_reasons = kw.pop("reason_codes", None)
        c = Classification(
            primary_intent=primary,
            secondary_intents=[s for s in secondary if s != primary],
            service_domain=kw.pop("service_domain", services[0] if services else "UNKNOWN"),
            detected_entities=entities,
            reason_codes=list(reasons) or explicit_reasons or [],
            status=ClassifierStatus.FALLBACK,
            **kw,
        )
        if services:
            c.detected_entities.mentioned_services = services
            if c.service_confidence == 0.0 and c.service_domain != "UNKNOWN":
                c.service_confidence = 0.9
        return c

    # ---- 1. safety-sensitive intents (mandatory human) ----------------------
    if _has(text, "refund", "money back", "my money back", "return my money"):
        reasons.append("REFUND_PHRASE")
        return result("REFUND_REQUEST", intent_confidence=0.95, customer_goal="REQUEST_REFUND",
                      conversation_route="HUMAN_INTERVENTION", requires_human=True,
                      human_reason="REFUND_REQUEST", complaint_type="REFUND_REQUEST",
                      sentiment="NEGATIVE", frustration_level=1, urgency="HIGH")

    if _has(text, "again for free", "clean it again", "redo", "re-clean", "reclean",
            "wash again", "reprocess", "do it again for free", "clean again"):
        reasons.append("REPROCESSING_PHRASE")
        return result("REPROCESSING_REQUEST", intent_confidence=0.9,
                      customer_goal="REQUEST_REPROCESSING", conversation_route="HUMAN_INTERVENTION",
                      requires_human=True, human_reason="REPROCESSING_REQUEST",
                      sentiment="NEGATIVE", frustration_level=1, urgency="HIGH")

    if _has(text, "charged twice", "double charge", "double charged", "paid twice",
            "duplicate charge", "charged me twice", "two times charged"):
        reasons.append("PAYMENT_DISPUTE_PHRASE")
        return result("COMPLAINT", intent_confidence=0.92, customer_goal="REPORT_PROBLEM",
                      conversation_route="HUMAN_INTERVENTION", requires_human=True,
                      human_reason="DUPLICATE_CHARGE", complaint_type="DUPLICATE_CHARGE",
                      payment_intent="DUPLICATE_CHARGE", sentiment="NEGATIVE",
                      frustration_level=2, urgency="HIGH")

    if _has(text, "damaged", "you damaged", "ruined", "destroyed", "you ruined", "burnt my", "burned my"):
        reasons.append("DAMAGE_PHRASE")
        return result("COMPLAINT", intent_confidence=0.9, customer_goal="REPORT_PROBLEM",
                      conversation_route="HUMAN_INTERVENTION", requires_human=True,
                      human_reason="DAMAGE_CLAIM", complaint_type="DAMAGE_CLAIM",
                      sentiment="ANGRY", frustration_level=3, urgency="HIGH")

    if _has(text, "missing", "one item is gone", "lost my", "item is gone", "not returned"):
        reasons.append("MISSING_ITEM_PHRASE")
        return result("COMPLAINT", intent_confidence=0.88, customer_goal="REPORT_PROBLEM",
                      conversation_route="HUMAN_INTERVENTION", requires_human=True,
                      human_reason="MISSING_ITEM", complaint_type="MISSING_ITEM",
                      sentiment="NEGATIVE", frustration_level=2, urgency="HIGH")

    if _has(text, "wrong item", "not my clothes", "someone else", "not mine", "wrong order", "wrong delivery"):
        reasons.append("COMPLAINT_PHRASE")
        ctype = "WRONG_DELIVERY" if "delivery" in text else "WRONG_ITEM"
        hr = "WRONG_DELIVERY" if ctype == "WRONG_DELIVERY" else "WRONG_ITEM"
        return result("COMPLAINT", intent_confidence=0.85, customer_goal="REPORT_PROBLEM",
                      conversation_route="HUMAN_INTERVENTION", requires_human=True,
                      human_reason=hr, complaint_type=ctype, sentiment="NEGATIVE",
                      frustration_level=2, urgency="HIGH")

    # repeated failed pickup/delivery ("again" + failure)
    if _has(text, "driver did not come", "driver didn't come", "no one came", "nobody came",
            "did not show", "didn't show", "no pickup") and _has(text, "again", "second time", "twice"):
        reasons.append("REPEATED_FAILURE_PHRASE")
        return result("COMPLAINT", intent_confidence=0.85, customer_goal="REPORT_PROBLEM",
                      conversation_route="HUMAN_INTERVENTION", requires_human=True,
                      human_reason="REPEATED_FAILED_PICKUP", complaint_type="REPEATED_FAILED_PICKUP",
                      sentiment="ANGRY", frustration_level=3, urgency="HIGH")

    # explicit human/manager request (also caught deterministically upstream)
    if _has(text, "speak to a manager", "talk to a manager", "speak to a human",
            "talk to a human", "human agent", "real person", "customer service",
            "speak to someone", "let me speak"):
        reasons.append("HUMAN_REQUEST_PHRASE")
        hr = "CUSTOMER_REQUESTED_MANAGER" if "manager" in text else "CUSTOMER_REQUESTED_HUMAN"
        if "supervisor" in text:
            hr = "CUSTOMER_REQUESTED_SUPERVISOR"
        elif "operations" in text:
            hr = "CUSTOMER_REQUESTED_OPERATIONS"
        return result("HUMAN_AGENT_REQUEST", intent_confidence=0.95, customer_goal="REQUEST_HUMAN",
                      conversation_route="HUMAN_INTERVENTION", requires_human=True,
                      human_reason=hr, fixed_template_id="HUMAN_HANDOVER")

    # ---- 2. B2B ------------------------------------------------------------
    if _has(text, *_B2B_KEYWORDS):
        reasons.append("B2B_SIGNAL")
        return result("B2B_ENQUIRY", intent_confidence=0.85, customer_goal="COMMERCIAL_ENQUIRY",
                      conversation_route="MAIN_AGENT", service_domain="B2B_COMMERCIAL",
                      needs_clarification=True, clarification_topic="B2B_REQUIREMENT_REQUIRED")

    # ---- 3. repair / alteration / restoration ------------------------------
    repair_signal = _hasw(text, "repair", "fix", "mend", "broken", "torn", "tear",
                          "rip", "stitch", "sew", "sole", "hem", "shorten",
                          "resize", "alter", "zip", "restore", "restoration") \
        or _has(text, "take in", "let out")
    non_laundry = _has(text, "phone", "laptop", "computer", "car ", "watch",
                       "furniture", "tv", "screen", "electronics", "mobile")
    if repair_signal and non_laundry and not services:
        reasons.append("NON_LAUNDRY_REPAIR")
        return result("UNSUPPORTED_REQUEST", intent_confidence=0.9, customer_goal="GET_INFORMATION",
                      conversation_route="MAIN_AGENT", service_domain="UNKNOWN",
                      repair_intent="UNSUPPORTED_NON_LAUNDRY_REPAIR",
                      needs_clarification=False, reason_codes=["NON_LAUNDRY_REPAIR"])
    if repair_signal:
        # restoration (specialist)
        if _has(text, "restore", "restoration", "colour restoration", "color restoration", "recolour", "recolor"):
            reasons.append("RESTORATION_KEYWORD")
            sec = ["RESTORATION"] if services and services[0] != "RESTORATION" else []
            domain = services[0] if services else "RESTORATION"
            secondary.extend(sec)
            return result("SPECIALIST_RESTORATION_REQUEST", intent_confidence=0.85,
                          customer_goal="GET_INFORMATION", conversation_route="MAIN_AGENT",
                          service_domain=domain, repair_intent="SPECIALIST_RESTORATION",
                          needs_clarification=False)
        # alteration keywords
        if _has(text, "shorten", "hem", "take in", "let out", "resize", "alter", "adjust", "tailor"):
            reasons.append("ALTERATION_KEYWORD")
            return result("ALTERATION_REQUEST", intent_confidence=0.88, customer_goal="PLACE_ORDER",
                          conversation_route="MAIN_AGENT",
                          service_domain="ALTERATIONS_AND_GARMENT_REPAIR",
                          repair_intent="STANDARD_ALTERATION")
        # shoe repair
        if _has(text, "sole", "heel") or (services and services[0] == "SHOES"):
            reasons.append("REPAIR_KEYWORD")
            return result("REPAIR_REQUEST", intent_confidence=0.85, customer_goal="PLACE_ORDER",
                          conversation_route="MAIN_AGENT", service_domain="SHOES",
                          repair_intent="SHOE_REPAIR")
        # bag / leather repair
        if services and services[0] == "BAGS_AND_ACCESSORIES":
            reasons.append("REPAIR_KEYWORD")
            return result("REPAIR_REQUEST", intent_confidence=0.8, customer_goal="PLACE_ORDER",
                          conversation_route="MAIN_AGENT", repair_intent="BAG_REPAIR")
        if services and services[0] == "LEATHER":
            reasons.append("REPAIR_KEYWORD")
            return result("REPAIR_REQUEST", intent_confidence=0.8, customer_goal="PLACE_ORDER",
                          conversation_route="MAIN_AGENT", repair_intent="LEATHER_REPAIR")
        # garment repair (torn/stitch/sew/zip/button)
        if _hasw(text, "torn", "tear", "rip", "stitch", "sew", "zip", "mend") or _has(text, "button"):
            reasons.append("REPAIR_KEYWORD")
            return result("REPAIR_REQUEST", intent_confidence=0.85, customer_goal="PLACE_ORDER",
                          conversation_route="MAIN_AGENT",
                          service_domain="ALTERATIONS_AND_GARMENT_REPAIR",
                          repair_intent="STANDARD_GARMENT_REPAIR")
        # ambiguous repair → clarify (NEVER auto-reject)
        reasons.append("REPAIR_KEYWORD")
        return result("REPAIR_REQUEST", intent_confidence=0.7, customer_goal="GET_INFORMATION",
                      conversation_route="NEEDS_CLARIFICATION", service_domain="UNKNOWN",
                      repair_intent="AMBIGUOUS_REPAIR", needs_clarification=True,
                      clarification_topic="REPAIR_ITEM_AND_SCOPE")

    # ---- 4. detect secondary signals (pickup / payment) for multi-intent ----
    price_signal = _has(text, "how much", "price", "cost", "rate", "quote", "charges", "how many aed", "how much is")
    pickup_enquiry = _has(text, "pickup time", "pick up time", "collection time",
                          "what time can you collect", "when can you collect",
                          "available pickup", "pickup slot", "collect")
    exact_time = bool(_TIME_RE.search(text)) and _has(text, "collect", "pick up", "pickup", "at")
    payment_enquiry = _has(text, "how do i pay", "how to pay", "payment method",
                           "ways to pay", "accept cash", "take cash", "do you take", "pay by")
    if pickup_enquiry and not exact_time:
        secondary.append("PICKUP_SLOT_ENQUIRY")
    if payment_enquiry:
        secondary.append("PAYMENT_METHOD_ENQUIRY")
    if services and (price_signal or pickup_enquiry or payment_enquiry):
        secondary.append("SERVICE_SELECTION")

    # ---- 5. pricing --------------------------------------------------------
    if _has(text, "too expensive", "too much", "expensive", "cheaper", "best price",
            "reduce", "high price", "lower the price", "so expensive", "bit much"):
        reasons.append("PRICE_RESISTANCE_PHRASE")
        return result("PRICE_PUSHBACK", intent_confidence=0.9, customer_goal="NEGOTIATE_PRICE",
                      conversation_route="MAIN_AGENT", pricing_intent="PRICE_PUSHBACK",
                      sentiment="NEUTRAL", frustration_level=0)
    if _PERCENT_RE.search(text) or _has(text, "discount", "off", "deal", "offer", "voucher", "promo"):
        reasons.append("DISCOUNT_PHRASE")
        return result("DISCOUNT_REQUEST", intent_confidence=0.88, customer_goal="NEGOTIATE_PRICE",
                      conversation_route="MAIN_AGENT", pricing_intent="ASKING_DISCOUNT")
    if price_signal:
        reasons.append("PRICE_KEYWORD")
        pi = "ASKING_MINIMUM_ORDER" if "minimum" in text else (
            "ASKING_DELIVERY_CHARGE" if ("delivery" in text and ("charge" in text or "fee" in text)) else "ASKING_PRICE")
        return result("PRICE_ENQUIRY", intent_confidence=0.9, customer_goal="GET_PRICE",
                      conversation_route="MAIN_AGENT", pricing_intent=pi)

    # ---- 6. payment --------------------------------------------------------
    if _has(text, "no stripe", "don't have stripe", "do not have stripe", "without stripe", "not on stripe"):
        reasons.append("STRIPE_KEYWORD")
        return result("STRIPE_PAYMENT_QUERY", intent_confidence=0.9, customer_goal="CHANGE_PAYMENT_METHOD",
                      conversation_route="DETERMINISTIC_HANDLER", payment_intent="STRIPE_ACCOUNT_CONCERN",
                      fixed_template_id="STRIPE_ACCOUNT_NOT_REQUIRED")
    if _has(text, "prefer cash", "still cash", "want cash", "cash please", "cash on delivery", "pay cash", "rather cash"):
        reasons.append("CASH_KEYWORD")
        return result("CASH_PAYMENT_REQUEST", intent_confidence=0.9, customer_goal="CHANGE_PAYMENT_METHOD",
                      conversation_route="DETERMINISTIC_HANDLER", payment_intent="CASH_PREFERENCE",
                      fixed_template_id="CASH_ON_DELIVERY_ACCEPTED")
    if _has(text, "take cash", "accept cash", "do you take cash", "is cash ok", "cash accepted"):
        reasons.append("CASH_KEYWORD")
        return result("PAYMENT_METHOD_ENQUIRY", intent_confidence=0.9, customer_goal="GET_INFORMATION",
                      conversation_route="DETERMINISTIC_HANDLER", payment_intent="CASH_ENQUIRY",
                      fixed_template_id="STRIPE_REGULAR_PAYMENT")
    if payment_enquiry or _has(text, "how do i pay", "payment options"):
        reasons.append("PAYMENT_METHOD_QUESTION")
        return result("PAYMENT_METHOD_ENQUIRY", intent_confidence=0.88, customer_goal="GET_INFORMATION",
                      conversation_route="DETERMINISTIC_HANDLER", payment_intent="ASKING_PAYMENT_METHODS",
                      fixed_template_id="STRIPE_REGULAR_PAYMENT")

    # ---- 7. pickup / delivery / status -------------------------------------
    if exact_time:
        reasons.append("EXACT_TIME_PHRASE")
        return result("EXACT_PICKUP_TIME_REQUEST", intent_confidence=0.88, customer_goal="CONTINUE_ORDER",
                      conversation_route="MAIN_AGENT")
    if convo.has_active_slot_options and _OPTION_RE.search(text) and len(text) <= 20:
        reasons.append("SLOT_SELECTION_IN_CONTEXT")
        return result("PICKUP_SLOT_SELECTION", intent_confidence=0.9, customer_goal="CONTINUE_ORDER",
                      conversation_route="DETERMINISTIC_HANDLER")
    if pickup_enquiry:
        reasons.append("SLOT_ENQUIRY_PHRASE")
        return result("PICKUP_SLOT_ENQUIRY", intent_confidence=0.88, customer_goal="CONTINUE_ORDER",
                      conversation_route="MAIN_AGENT")
    if _has(text, "where is my order", "order status", "status of my order", "track my order"):
        reasons.append("STATUS_QUESTION")
        return result("ORDER_STATUS_ENQUIRY", intent_confidence=0.9, customer_goal="CHECK_STATUS",
                      conversation_route="MAIN_AGENT")
    if _has(text, "where is my delivery", "delivery status", "when will it arrive", "when is my delivery"):
        reasons.append("STATUS_QUESTION")
        return result("DELIVERY_STATUS_ENQUIRY", intent_confidence=0.88, customer_goal="CHECK_STATUS",
                      conversation_route="MAIN_AGENT")
    if _has(text, "where is my pickup", "pickup status", "has the driver"):
        reasons.append("STATUS_QUESTION")
        return result("PICKUP_STATUS_ENQUIRY", intent_confidence=0.85, customer_goal="CHECK_STATUS",
                      conversation_route="MAIN_AGENT")

    # ---- 8. complaints without a mandatory reason --------------------------
    if _has(text, "no one has updated", "nobody has updated", "no update", "haven't heard",
            "not heard anything", "no response for") or (
            _has(text, "two days", "three days", "days") and _has(text, "no", "not", "haven't")):
        reasons.append("COMPLAINT_PHRASE")
        return result("COMPLAINT", intent_confidence=0.82, customer_goal="REPORT_PROBLEM",
                      conversation_route="MAIN_AGENT", complaint_type="NO_UPDATE",
                      sentiment="NEGATIVE", frustration_level=2, urgency="NORMAL")
    if _has(text, "unhappy with the cleaning", "not clean", "poor quality", "bad job",
            "still dirty", "not cleaned properly", "quality is bad"):
        reasons.append("COMPLAINT_PHRASE")
        return result("COMPLAINT", intent_confidence=0.82, customer_goal="REPORT_PROBLEM",
                      conversation_route="MAIN_AGENT", complaint_type="CLEANING_QUALITY",
                      sentiment="NEGATIVE", frustration_level=2)

    # ---- 9. order lifecycle actions ----------------------------------------
    if _has(text, "cancel my order", "cancel the order", "cancel booking"):
        return result("ORDER_CANCELLATION", intent_confidence=0.85, customer_goal="CANCEL_ORDER",
                      conversation_route="MAIN_AGENT")
    if _has(text, "change", "edit", "update my order", "modify") and convo.active_order:
        return result("ORDER_CHANGE", intent_confidence=0.75, customer_goal="CHANGE_ORDER",
                      conversation_route="MAIN_AGENT")
    if "confirm" in text or (text in _AFFIRMATIVES and _has(last_assistant, "confirm", "summary", "total", "proceed")):
        reasons.append("CONFIRMATION_IN_CONTEXT")
        return result("ORDER_CONFIRMATION", intent_confidence=0.85, customer_goal="CONFIRM_ORDER",
                      conversation_route="MAIN_AGENT")
    if _has(text, "order summary", "show my order", "what did i order"):
        return result("ORDER_SUMMARY_REQUEST", intent_confidence=0.8, customer_goal="GET_INFORMATION",
                      conversation_route="DETERMINISTIC_HANDLER", fixed_template_id="ORDER_SUMMARY")

    # ---- 10. address -------------------------------------------------------
    if _has(text, *_ADDRESS_WORDS) and any(ch.isdigit() for ch in text):
        reasons.append("ADDRESS_TEXT")
        return result("ADDRESS_PROVIDED", intent_confidence=0.85, customer_goal="PROVIDE_INFORMATION",
                      conversation_route="MAIN_AGENT", service_domain=convo.selected_service or "UNKNOWN")

    # ---- 11. process / service enquiry -------------------------------------
    if _has(text, "how does it work", "how does the process", "process work", "how it works",
            "explain the process", "how do you work"):
        reasons.append("PROCESS_QUESTION")
        return result("PROCESS_ENQUIRY", intent_confidence=0.88, customer_goal="GET_INFORMATION",
                      conversation_route="DETERMINISTIC_HANDLER", fixed_template_id="PROCESS_EXPLANATION")
    if _has(text, "what services", "what do you offer", "what do you provide", "services do you",
            "what can you clean", "what do you clean"):
        reasons.append("PROCESS_QUESTION")
        return result("SERVICE_ENQUIRY", intent_confidence=0.88, customer_goal="GET_INFORMATION",
                      conversation_route="MAIN_AGENT", service_domain="UNKNOWN")

    # ---- 12. express -------------------------------------------------------
    if _has(text, "express", "urgent", "same day", "asap", "as soon as possible", "rush"):
        return result("EXPRESS_SERVICE_REQUEST", intent_confidence=0.8, customer_goal="PLACE_ORDER",
                      conversation_route="MAIN_AGENT", urgency="HIGH")

    # ---- 13. service selection (a service is named, intent to use it) -------
    if services:
        reasons.append("EXPLICIT_SERVICE_MENTION")
        goal = "GET_PRICE" if price_signal else "PLACE_ORDER"
        return result("SERVICE_SELECTION", intent_confidence=0.85, customer_goal=goal,
                      conversation_route="MAIN_AGENT")

    # ---- 14. contextual short replies --------------------------------------
    if text in _AFFIRMATIVES:
        if _has(last_assistant, "cash"):
            reasons.append("CONFIRMATION_IN_CONTEXT")
            return result("BOOKING_CONTINUE", intent_confidence=0.8, customer_goal="MAKE_PAYMENT",
                          conversation_route="MAIN_AGENT", payment_intent="CASH_CONFIRMED")
        if _has(last_assistant, "address", "same address", "reuse"):
            reasons.append("CONFIRMATION_IN_CONTEXT")
            return result("BOOKING_CONTINUE", intent_confidence=0.8, customer_goal="CONTINUE_ORDER",
                          conversation_route="MAIN_AGENT", reason_codes=["CONFIRMATION_IN_CONTEXT"])
        if convo.last_assistant_was_question or convo.active_order or convo.workflow_state:
            reasons.append("CONFIRMATION_IN_CONTEXT")
            return result("BOOKING_CONTINUE", intent_confidence=0.7, customer_goal="CONTINUE_ORDER",
                          conversation_route="MAIN_AGENT")
        reasons.append("NO_CONTEXT_FOR_SHORT_REPLY")
        return result("UNKNOWN", intent_confidence=0.3, customer_goal="UNKNOWN",
                      conversation_route="NEEDS_CLARIFICATION", needs_clarification=True,
                      clarification_topic="UNKNOWN_INTENT")

    # ---- 15. greeting / small talk / feedback ------------------------------
    if text in _GREETINGS or (len(text) <= 12 and any(text.startswith(g) for g in _GREETINGS)):
        reasons.append("GREETING_ONLY")
        return result("GREETING", intent_confidence=0.9, customer_goal="GET_INFORMATION",
                      conversation_route="DETERMINISTIC_HANDLER", service_domain="UNKNOWN",
                      fixed_template_id="GREETING_NEW_CUSTOMER")
    if _has(text, "thank you", "thanks", "great service", "well done", "good job", "appreciate"):
        reasons.append("FEEDBACK_PHRASE")
        return result("FEEDBACK_OR_REVIEW", intent_confidence=0.7, customer_goal="END_CONVERSATION",
                      conversation_route="MAIN_AGENT", sentiment="POSITIVE", service_domain="UNKNOWN")
    if _has(text, "how are you", "what's up", "good morning") and len(text) <= 25:
        return result("SMALL_TALK", intent_confidence=0.6, customer_goal="GET_INFORMATION",
                      conversation_route="MAIN_AGENT", service_domain="UNKNOWN")

    # ---- 16. laundry-generic / fallthrough ---------------------------------
    if _has(text, "laundry", "clean", "washing", "book", "booking", "order"):
        return result("GENERAL_ENQUIRY", intent_confidence=0.55, customer_goal="GET_INFORMATION",
                      conversation_route="MAIN_AGENT", service_domain="UNKNOWN",
                      needs_clarification=True, clarification_topic="SERVICE_REQUIRED")

    reasons.append("LOW_CONFIDENCE")
    return result("UNKNOWN", intent_confidence=0.3, customer_goal="UNKNOWN",
                  conversation_route="NEEDS_CLARIFICATION", service_domain="UNKNOWN",
                  needs_clarification=True, clarification_topic="UNKNOWN_INTENT")
