"""Retrieval KB service — cosine search wiring + fail-soft behavior (Phase 2).

Hermetic: the fastembed model and pgvector are mocked, so no model download / DB.
"""
import pytest

from db import database
from services import chat_kb


def _async(value):
    async def _f(*a, **k):
        return value
    return _f


@pytest.mark.asyncio
async def test_search_returns_scored_snippets(monkeypatch):
    monkeypatch.setattr(database, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(chat_kb, "embed_query", lambda t: [0.1] * chat_kb.EMBED_DIM)
    captured = {}

    async def fake_fetch(sql, *args):
        captured["sql"] = sql
        captured["args"] = args
        return [
            {"source_ref": "cust-a", "content": "we collect and confirm the weight after pickup", "chunk_index": 0, "score": 0.82},
            {"source_ref": "cust-b", "content": "curtains take 3-4 days", "chunk_index": 1, "score": 0.20},
        ]
    monkeypatch.setattr(database, "fetch", fake_fetch)

    out = await chat_kb.search("how are curtains priced?", market="AE", k=4, min_score=0.3)

    # Only the >=0.3 snippet survives; PII-free content passes through.
    assert [r["source_ref"] for r in out] == ["cust-a"]
    assert out[0]["score"] == 0.82
    # Query is scoped by market and ordered by cosine distance.
    assert "embedding <=> $1::vector" in captured["sql"]
    assert captured["args"][1] == "AE"


@pytest.mark.asyncio
async def test_search_empty_query_returns_empty(monkeypatch):
    monkeypatch.setattr(database, "is_supabase_mode", lambda: True)
    assert await chat_kb.search("   ") == []


@pytest.mark.asyncio
async def test_search_non_supabase_returns_empty(monkeypatch):
    monkeypatch.setattr(database, "is_supabase_mode", lambda: False)
    # Should not even attempt to embed / query.
    monkeypatch.setattr(chat_kb, "embed_query", lambda t: (_ for _ in ()).throw(AssertionError("must not embed")))
    assert await chat_kb.search("anything") == []


@pytest.mark.asyncio
async def test_search_fails_soft_on_db_error(monkeypatch):
    monkeypatch.setattr(database, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(chat_kb, "embed_query", lambda t: [0.0] * chat_kb.EMBED_DIM)

    async def boom(*a, **k):
        raise RuntimeError("relation does not exist")
    monkeypatch.setattr(database, "fetch", boom)

    assert await chat_kb.search("query") == []


def test_indexer_parse_redacts_pii_and_names():
    from scripts.index_chat_kb import parse_chat
    raw = (
        '<div class="msg __message-in">'
        '<span dir="ltr" class="__selectable-text">Hi I\'m Ahmed, call +971501234567</span></div>'
        '<div class="msg __message-out">'
        '<span dir="ltr" class="__selectable-text">Sure, we will collect today</span></div>'
    )
    msgs = parse_chat(raw, "Ahmed Khan")
    joined = "\n".join(t for _, t in msgs)
    # Structural PII + intro name + saved contact name are all gone.
    assert "Ahmed" not in joined and "Khan" not in joined
    assert "+971501234567" not in joined and "971" not in joined
    assert "[NAME]" in joined and "[PHONE]" in joined
    # Non-PII content survives for retrieval usefulness.
    assert "collect today" in joined


def test_vector_literal_shape():
    lit = chat_kb.vector_literal([0.1, 0.2, -0.3])
    assert lit.startswith("[") and lit.endswith("]")
    assert lit.count(",") == 2


def test_tool_is_registered():
    from agents.whatsapp_agent.booking_tools import BOOKING_TOOL_SCHEMAS
    names = [t["name"] for t in BOOKING_TOOL_SCHEMAS]
    assert "search_past_conversations" in names


@pytest.mark.asyncio
async def test_tool_dispatches_to_chat_kb(monkeypatch):
    import datetime as _dt
    import json
    from agents.whatsapp_agent.booking_tools import BookingContext, make_booking_executor

    async def fake_search(query, *, market="AE", **k):
        assert market == "AE"
        return [{"source_ref": "cust-x", "content": "we separate darks from lights", "chunk_index": 0, "score": 0.7}]
    monkeypatch.setattr(chat_kb, "search", fake_search)

    class _Repo:
        async def get_active_draft(self, cid): return None
        async def get_latest_for_conversation(self, cid): return None

    async def _slots(*a, **k):
        return []
    ctx = BookingContext(conversation_id="c1", order_uuid="o1", repo=_Repo(),
                         today=_dt.date(2026, 8, 8), available_slots=_slots, market="AE")
    text, is_error = await make_booking_executor(ctx)("search_past_conversations", {"query": "colour separation?"})
    data = json.loads(text)
    assert is_error is False
    assert data["snippets"][0]["source_ref"] == "cust-x"
    assert "Guidance only" in data["note"]
