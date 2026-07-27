"""TurnBuffer orchestration (task spec §§15-27, tests 31-33/38-41/45-50).

Uses an in-memory fake turn repo + a recording processor + a controllable clock,
so buffering / one-flush-per-turn / conversation isolation / restart recovery /
takeover cancellation are tested with NO DB and NO real timers.
"""
from datetime import datetime, timedelta

import pytest

from services.turn_service import TurnBuffer

T0 = datetime(2026, 7, 27, 18, 0, 0)


class FakeRepo:
    """Minimal in-memory stand-in for db.repositories.turns_repo."""
    def __init__(self):
        self.turns: dict[str, dict] = {}      # pk -> turn
        self.frags: dict[str, list] = {}      # turn_id -> [message rows]
        self._seq = 0

    def _open_for(self, convo):
        for t in self.turns.values():
            if t["conversation_id"] == convo and t["status"] in ("pending", "aggregating"):
                return t
        return None

    # test helper (not part of the real repo interface)
    def add_message_row(self, turn_id, text, *, selection_id=None, latitude=None, longitude=None):
        self.frags.setdefault(turn_id, []).append(
            {"message_text": text, "metadata": {"selection_id": selection_id,
             "latitude": latitude, "longitude": longitude}})

    async def append_or_open(self, convo, cust, *, message_id, message_at,
                             deadline_at, first_deadline_at):
        t = self._open_for(convo)
        if t is not None:
            t["message_count"] += 1
            t["last_message_at"] = message_at
            t["aggregation_deadline_at"] = deadline_at
            t["status"] = "aggregating"
            return t, False
        self._seq += 1
        t = {"id": f"pk{self._seq}", "turn_id": f"turn{self._seq}",
             "conversation_id": convo, "customer_id": cust, "status": "pending",
             "first_message_at": message_at, "last_message_at": message_at,
             "aggregation_deadline_at": min(deadline_at, first_deadline_at),
             "message_count": 1}
        self.turns[t["id"]] = t
        self.frags.setdefault(t["turn_id"], [])
        return t, True

    async def link_message(self, message_id, turn_id):
        return None

    async def get_open_turn(self, convo):
        return self._open_for(convo)

    async def claim_for_processing(self, pk):
        t = self.turns.get(pk)
        if t and t["status"] in ("pending", "aggregating"):
            t["status"] = "processing"
            return t
        return None

    async def fragments(self, turn_id):
        return list(self.frags.get(turn_id, []))

    async def mark_completed(self, pk, *, combined_text, response_message_id=None,
                             llm_request_id=None):
        self.turns[pk]["status"] = "completed"
        self.turns[pk]["combined_text"] = combined_text

    async def mark_failed(self, pk):
        self.turns[pk]["status"] = "failed"
        self.turns[pk]["attempts"] = self.turns[pk].get("attempts", 0) + 1

    async def release_to_pending(self, pk):
        if self.turns[pk]["status"] == "processing":
            self.turns[pk]["status"] = "pending"

    async def cancel_open_turns(self, convo):
        for t in self.turns.values():
            if t["conversation_id"] == convo and t["status"] in ("pending", "aggregating"):
                t["status"] = "cancelled"

    async def recoverable_turns(self):
        return [t for t in self.turns.values()
                if t["status"] in ("pending", "aggregating", "processing")]


class Recorder:
    def __init__(self):
        self.calls = []

    async def __call__(self, conversation_id, combined, turn):
        self.calls.append((conversation_id, combined.text, combined.message_count))
        return "resp-msg-id"


def _buffer(repo):
    # A fixed clock so no real time passes; timers are exercised via flush directly.
    return TurnBuffer(repo, debounce_seconds=5, max_seconds=15, now_fn=lambda: T0)


# --- One combined turn -> one processor call (spec §§31-33) ------------------
@pytest.mark.asyncio
async def test_rapid_fragments_form_one_turn_and_one_call():
    repo, proc = FakeRepo(), Recorder()
    buf = _buffer(repo)
    t = await buf.add_fragment("c1", "cust1", message_id="m1", message_at=T0)
    repo.add_message_row(t["turn_id"], "Hi")
    t = await buf.add_fragment("c1", "cust1", message_id="m2", message_at=T0 + timedelta(seconds=1))
    repo.add_message_row(t["turn_id"], "I need wash and fold")
    t = await buf.add_fragment("c1", "cust1", message_id="m3", message_at=T0 + timedelta(seconds=2))
    repo.add_message_row(t["turn_id"], "tomorrow")
    assert t["message_count"] == 3                 # one turn, three fragments

    await buf.flush("c1", proc)
    assert len(proc.calls) == 1                     # ONE processor call (one reply)
    assert proc.calls[0][1] == "Hi\nI need wash and fold\ntomorrow"
    assert proc.calls[0][2] == 3


@pytest.mark.asyncio
async def test_flush_twice_processes_once():
    repo, proc = FakeRepo(), Recorder()
    buf = _buffer(repo)
    t = await buf.add_fragment("c1", "cust1", message_id="m1", message_at=T0)
    repo.add_message_row(t["turn_id"], "hello")
    await buf.flush("c1", proc)
    await buf.flush("c1", proc)                      # duplicate flush / duplicate webhook
    assert len(proc.calls) == 1
    assert repo.turns["pk1"]["status"] == "completed"


# --- Conversation isolation (spec §§39-40) ----------------------------------
@pytest.mark.asyncio
async def test_two_conversations_isolated():
    repo, proc = FakeRepo(), Recorder()
    buf = _buffer(repo)
    ta = await buf.add_fragment("cA", "custA", message_id="a1", message_at=T0)
    repo.add_message_row(ta["turn_id"], "wash and fold")
    tb = await buf.add_fragment("cB", "custB", message_id="b1", message_at=T0)
    repo.add_message_row(tb["turn_id"], "shoe cleaning")
    assert ta["turn_id"] != tb["turn_id"]
    await buf.flush("cA", proc)
    await buf.flush("cB", proc)
    texts = sorted(c[1] for c in proc.calls)
    assert texts == ["shoe cleaning", "wash and fold"]  # no crossed data


# --- New fragment during/after processing -> next turn (spec §21) ------------
@pytest.mark.asyncio
async def test_message_after_completion_starts_new_turn():
    repo, proc = FakeRepo(), Recorder()
    buf = _buffer(repo)
    t = await buf.add_fragment("c1", "cust1", message_id="m1", message_at=T0)
    repo.add_message_row(t["turn_id"], "first")
    await buf.flush("c1", proc)
    # a new message arrives after the turn completed -> a brand new turn
    t2 = await buf.add_fragment("c1", "cust1", message_id="m2", message_at=T0 + timedelta(seconds=30))
    assert t2["turn_id"] != t["turn_id"]
    repo.add_message_row(t2["turn_id"], "second")
    await buf.flush("c1", proc)
    assert [c[1] for c in proc.calls] == ["first", "second"]


# --- Failure preserves the turn (spec §§27/47/48) ---------------------------
@pytest.mark.asyncio
async def test_processing_failure_marks_failed_and_raises_once():
    repo = FakeRepo()
    buf = _buffer(repo)

    async def boom(*_a):
        raise RuntimeError("llm down")

    t = await buf.add_fragment("c1", "cust1", message_id="m1", message_at=T0)
    repo.add_message_row(t["turn_id"], "hello")
    with pytest.raises(RuntimeError):
        await buf.flush("c1", boom)
    assert repo.turns["pk1"]["status"] == "failed"


# --- Human takeover cancels the pending turn (spec §24) ---------------------
@pytest.mark.asyncio
async def test_cancel_on_takeover_stops_flush():
    repo, proc = FakeRepo(), Recorder()
    buf = _buffer(repo)
    t = await buf.add_fragment("c1", "cust1", message_id="m1", message_at=T0)
    repo.add_message_row(t["turn_id"], "hello")
    await buf.cancel("c1")                           # takeover began
    assert repo.turns["pk1"]["status"] == "cancelled"
    await buf.flush("c1", proc)
    assert proc.calls == []                          # no delayed AI reply


# --- Restart recovery (spec §§21/27/49) -------------------------------------
@pytest.mark.asyncio
async def test_recover_processes_pending_turns():
    repo, proc = FakeRepo(), Recorder()
    buf = _buffer(repo)
    t = await buf.add_fragment("c1", "cust1", message_id="m1", message_at=T0)
    repo.add_message_row(t["turn_id"], "left mid-flight")
    # simulate a crash mid-processing
    repo.turns["pk1"]["status"] = "processing"
    n = await buf.recover(proc)
    assert n == 1
    assert len(proc.calls) == 1 and proc.calls[0][1] == "left mid-flight"
    assert repo.turns["pk1"]["status"] == "completed"


# --- Debounce timer actually fires a single flush (real asyncio) ------------
@pytest.mark.asyncio
async def test_schedule_fires_flush_after_debounce():
    import asyncio
    repo, proc = FakeRepo(), Recorder()
    # tiny real debounce; now_fn=real so the computed delay is ~0
    from datetime import timezone
    buf = TurnBuffer(repo, debounce_seconds=0.01, max_seconds=0.05,
                     now_fn=lambda: datetime.now(timezone.utc))
    now = datetime.now(timezone.utc)
    t = await buf.add_fragment("c1", "cust1", message_id="m1", message_at=now)
    repo.add_message_row(t["turn_id"], "buffered")
    buf.schedule("c1", t, proc)
    await asyncio.sleep(0.08)
    assert len(proc.calls) == 1 and proc.calls[0][1] == "buffered"
