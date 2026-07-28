"""Human-intervention orchestration (services/human_intervention) — pure tests
with a fake repo (no DB). The SQL-level idempotency / concurrency-safe claim /
pause guarantees are verified separately against dev Supabase; here we prove the
service logic: only abuse/threat triggers, one holding message per event,
duplicates prevented, clean/dissatisfied turns are no-ops.
"""
import pytest

from services import abuse_classification as ac
from services import human_intervention as hint


class FakeRepo:
    """In-memory stand-in for human_interventions_repo — one active event/convo."""
    def __init__(self):
        self.active: dict | None = None
        self.paused = False
        self.create_calls = 0

    async def create_and_pause(self, conversation_id, **kw):
        self.create_calls += 1
        if self.active is not None:
            return dict(self.active), False           # idempotent
        self.active = {"id": "hi-1", "conversation_id": conversation_id,
                       "takeover_status": "WAITING_FOR_HUMAN",
                       "customer_notice_sent": False, **kw}
        self.paused = True
        return dict(self.active), True

    async def mark_notice_sent(self, intervention_id):
        if self.active and not self.active["customer_notice_sent"]:
            self.active["customer_notice_sent"] = True
            return dict(self.active)
        return None                                    # already sent → no resend


@pytest.fixture
def repo(monkeypatch):
    r = FakeRepo()
    monkeypatch.setattr(hint, "hi_repo", r)
    return r


async def _trigger(text, prior=0):
    result = ac.classify(text, prior_abuse_event_count=prior)
    return await hint.trigger_from_classification(
        "conv-1", result, flagged_turn_id="t1", combined_text=text)


# ===================== triggers only on abuse/threat =======================
async def test_direct_insult_triggers_and_sends_one_holding(repo):
    out = await _trigger("You are a fucking idiot")
    assert out.triggered and out.created
    assert out.should_send_notice is True
    assert out.holding_message == hint.HOLDING_MESSAGE
    assert repo.paused is True


async def test_threat_triggers(repo):
    out = await _trigger("I will hurt the driver")
    assert out.triggered
    assert out.intervention["reason"] == "THREAT"      # kwarg persisted by the repo as takeover_reason


async def test_dissatisfaction_does_not_trigger(repo):
    out = await _trigger("this is too expensive and slow")
    assert out.triggered is False
    assert repo.paused is False
    assert repo.create_calls == 0


async def test_general_profanity_does_not_trigger(repo):
    out = await _trigger("this fucking service is slow")
    assert out.triggered is False


async def test_clean_message_does_not_trigger(repo):
    out = await _trigger("hi please book a pickup tomorrow")
    assert out.triggered is False


# ===================== idempotency (one notice per event) ==================
async def test_second_abusive_turn_does_not_resend_notice(repo):
    first = await _trigger("you are an idiot")
    assert first.should_send_notice is True
    # Same active event still open → re-trigger must NOT create or resend.
    second = await _trigger("you idiot", prior=1)
    assert second.triggered is True
    assert second.created is False
    assert second.should_send_notice is False
    assert second.holding_message is None
    assert repo.create_calls == 2                      # both attempted, one created


# ===================== reason mapping ======================================
def test_intervention_reason_mapping():
    assert ac.intervention_reason(ac.classify("you are a fucking idiot")) == "ABUSIVE_LANGUAGE"
    assert ac.intervention_reason(ac.classify("I will hurt the driver")) == "THREAT"
    assert ac.intervention_reason(ac.classify("this is expensive")) is None
