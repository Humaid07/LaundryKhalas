"""Auto-reply decision layer (gates live Evolution sends).

Runs BEFORE the agent auto-sends anything through Evolution when
EVOLUTION_AUTO_REPLY=true. Its whole job is to stop the WhatsApp number from
behaving like a dumb bot that welcomes every inbound line. It answers one
question: *should we auto-reply to this message at all, and may we welcome?*

It is deterministic (no LLM call) and reuses the existing domain guard
(``services.domain_guard.classify``) and escalation detector
(``services.escalation.detect_escalation``) so the keyword lists live in one
place. Decision precedence:

  1. escalation (refund/complaint/damage/…) -> route to human, never auto-resolve
  2. explicitly out-of-domain (code/politics/injection/…) -> stay silent
  3. laundry-related -> auto-reply (welcome only if not welcomed before)
  4. bare greeting ("hi"/"hello") -> welcome ONCE per conversation, then silent
  5. ack / smalltalk / emoji-only / anything else uncertain -> stay silent

Only case 3 and the first hit of case 4 return ``send_reply=True``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from services.domain_guard import Domain, classify
from services.escalation import detect_escalation
from services.privacy import mask_phone, normalize_e164

# Decision domains (distinct from domain_guard.Domain — this is the coarser
# bucket the caller/logs reason about).
LAUNDRY_RELATED = "laundry_related"
OUT_OF_DOMAIN = "out_of_domain"
GREETING_ONLY = "greeting_only"
ESCALATION = "escalation"

# A message is a "bare greeting" only if EVERY token is a greeting word — so
# "hello" and "hi hi" qualify, but "hello bro" does not (it falls through to
# silence, per the requirement).
_GREETING_WORDS = {
    "hi", "hii", "hiii", "hello", "helo", "hey", "heyy", "heya", "hiya", "yo",
    "hai", "salam", "salaam", "assalamualaikum", "howdy", "greetings",
}
_GREETING_PHRASES = {
    "good morning", "good afternoon", "good evening", "good day",
    "hi there", "hello there", "hey there",
}
# Bare acknowledgements / filler that never deserve an auto-reply.
_ACK_WORDS = {
    "ok", "okay", "k", "kk", "thanks", "thank", "thankyou", "thanku", "thx",
    "ty", "cool", "great", "nice", "fine", "done", "sure", "alright", "noted",
    "hmm", "hm", "yeah", "yep", "yup", "nope", "na", "test", "testing", "hello?",
}

_STRIP = re.compile(r"[^a-z0-9\s]")


@dataclass
class AutoReplyDecision:
    send_reply: bool
    reason: str
    intent: str
    domain: str  # laundry_related | out_of_domain | greeting_only | escalation
    allow_welcome: bool


def _normalize(text: str | None) -> str:
    """Lowercase, drop punctuation/emoji, collapse whitespace."""
    return " ".join(_STRIP.sub(" ", (text or "").lower()).split())


def _is_bare_greeting(norm: str) -> bool:
    if not norm:
        return False
    if norm in _GREETING_PHRASES:
        return True
    tokens = norm.split()
    return bool(tokens) and all(t in _GREETING_WORDS for t in tokens)


def _is_ack(norm: str) -> bool:
    if not norm:
        return False
    tokens = norm.split()
    return bool(tokens) and all(t in _ACK_WORDS for t in tokens)


def should_auto_reply(
    message_text: str, conversation_context: dict | None = None
) -> AutoReplyDecision:
    """Decide whether the agent may auto-reply to ``message_text``.

    conversation_context keys used:
      - ``welcome_sent`` (bool): has a welcome/agent message already gone out in
        this conversation? Prevents repeat welcomes.
    """
    ctx = conversation_context or {}
    welcome_sent = bool(ctx.get("welcome_sent"))
    text = (message_text or "").strip()

    # 1) Escalation first — risky topics are never auto-resolved. The webhook
    #    still stores the message and raises a human_needed flag; we just refuse
    #    to send an autonomous reply here.
    category = detect_escalation(text)
    if category:
        return AutoReplyDecision(
            send_reply=False,
            reason=f"escalation:{category} — route to human, no autonomous reply",
            intent=f"escalation_{category}",
            domain=ESCALATION,
            allow_welcome=False,
        )

    # 2) Hard out-of-domain (coding/politics/prompt-injection/…): stay silent.
    domain = classify(text)
    if domain is Domain.OUT_OF_DOMAIN:
        return AutoReplyDecision(
            send_reply=False,
            reason="out_of_domain — unrelated to laundry/LaundryKhalas",
            intent="out_of_domain",
            domain=OUT_OF_DOMAIN,
            allow_welcome=False,
        )

    # 3) Clearly laundry-related: auto-reply and continue the flow. A welcome is
    #    only appropriate if we have not welcomed this conversation yet.
    if domain is Domain.IN_DOMAIN:
        return AutoReplyDecision(
            send_reply=True,
            reason="laundry_related — auto-reply",
            intent="laundry_related",
            domain=LAUNDRY_RELATED,
            allow_welcome=not welcome_sent,
        )

    # 4) UNCERTAIN — short/greeting/ack/emoji. Only a first bare greeting earns a
    #    single welcome; everything else stays silent so we don't spam.
    norm = _normalize(text)

    if not norm:
        return AutoReplyDecision(
            send_reply=False,
            reason="empty/emoji-only — nothing to answer",
            intent="empty",
            domain=OUT_OF_DOMAIN,
            allow_welcome=False,
        )

    if _is_bare_greeting(norm):
        if welcome_sent:
            return AutoReplyDecision(
                send_reply=False,
                reason="bare greeting but welcome already sent — no repeat welcome",
                intent="greeting",
                domain=GREETING_ONLY,
                allow_welcome=False,
            )
        return AutoReplyDecision(
            send_reply=True,
            reason="first bare greeting — send welcome once",
            intent="greeting",
            domain=GREETING_ONLY,
            allow_welcome=True,
        )

    if _is_ack(norm):
        return AutoReplyDecision(
            send_reply=False,
            reason="ack/smalltalk — no auto-reply",
            intent="smalltalk_ack",
            domain=OUT_OF_DOMAIN,
            allow_welcome=False,
        )

    # Anything else uncertain ("what are you doing", "hello bro", random chat):
    # do not auto-reply — avoids welcome-spam on non-laundry messages.
    return AutoReplyDecision(
        send_reply=False,
        reason="uncertain and not laundry-related — no auto-reply",
        intent="uncertain",
        domain=OUT_OF_DOMAIN,
        allow_welcome=False,
    )


# ---------------------------------------------------------------------------
# Sender gate + message decision (the single entry the webhook calls)
# ---------------------------------------------------------------------------
# Reason a message was NOT auto-replied to because of WHO sent it (checked
# before the message is even looked at).
SENDER_NOT_ALLOWED = "sender_not_allowed"


@dataclass
class InboundDecision:
    """Combined 'should we auto-reply to this inbound?' verdict.

    Order of checks (per the safety spec): normalize sender -> is the sender an
    approved test number? -> only then run the message/domain decision. A
    non-allowed sender short-circuits: the message decision is never run, so a
    refund/complaint from a stranger cannot create a customer-facing reply.
    """
    allowed_sender: bool
    masked_sender: str          # never the full number — safe to log/return
    auto_reply_decision: str    # "send" | "hold"
    no_auto_reply_reason: str | None
    message: AutoReplyDecision | None  # None when the sender was not allowed

    @property
    def send_reply(self) -> bool:
        return self.auto_reply_decision == "send"


def evaluate_inbound(
    sender_raw: str | None,
    message_text: str,
    allowed_numbers,
    conversation_context: dict | None = None,
) -> InboundDecision:
    """Decide whether to auto-reply to an inbound WhatsApp message.

    ``allowed_numbers`` is any container of normalized E.164 strings (e.g.
    ``settings.allowed_auto_reply_numbers``). The sender is normalized with the
    SAME function used to build that set, so the comparison is format-independent.
    """
    sender = normalize_e164(sender_raw)
    masked = mask_phone(sender)

    # Gate on WHO sent it first — a stranger never reaches the message decision.
    if not sender or sender not in allowed_numbers:
        return InboundDecision(
            allowed_sender=False,
            masked_sender=masked,
            auto_reply_decision="hold",
            no_auto_reply_reason=SENDER_NOT_ALLOWED,
            message=None,
        )

    decision = should_auto_reply(message_text, conversation_context)
    return InboundDecision(
        allowed_sender=True,
        masked_sender=masked,
        auto_reply_decision="send" if decision.send_reply else "hold",
        no_auto_reply_reason=None if decision.send_reply else decision.reason,
        message=decision,
    )
