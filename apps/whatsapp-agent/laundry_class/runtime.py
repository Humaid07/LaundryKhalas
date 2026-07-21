"""High-level entry point for the Laundry Class agent.

`process_message(phone, text)` is the one call the WhatsApp channel (or a test)
makes per inbound message. It:

* derives a stable thread_id ("whatsapp:<phone>") so each number keeps isolated
  memory,
* loads/persists conversation state via a LangGraph AsyncSqliteSaver checkpointer
  (memory survives an application restart — task Part 8),
* runs the graph and returns the agent's reply plus a small metadata dict.

Use `InMemoryRuntime` for the first functional test (Part 4, Step 3) and
`PersistentRuntime` (default) for the restart/persistence test.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, HumanMessage

from laundry_class.config import get_config
from laundry_class.graph import build_graph


def thread_id_for(phone: str) -> str:
    """Stable per-WhatsApp-number thread id. Same number -> same thread; different
    numbers -> different threads (memory isolation)."""
    return f"whatsapp:{phone.strip()}"


@dataclass
class AgentReply:
    text: str
    thread_id: str
    intent: str | None
    handoff_required: bool
    handoff_reason: str | None
    current_order_id: str | None
    collected_order_details: dict


class _BaseRuntime:
    def __init__(self, graph):
        self._graph = graph

    async def process_message(self, phone: str, text: str) -> AgentReply:
        tid = thread_id_for(phone)
        config = {"configurable": {"thread_id": tid}}
        inp = {
            "messages": [HumanMessage(content=text)],
            "phone_number": phone,
            "thread_id": tid,
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
        }
        state = await self._graph.ainvoke(inp, config=config)
        reply_text = ""
        for msg in reversed(state.get("messages", [])):
            if isinstance(msg, AIMessage):
                reply_text = msg.content if isinstance(msg.content, str) else str(msg.content)
                break
        return AgentReply(
            text=reply_text,
            thread_id=tid,
            intent=state.get("detected_intent"),
            handoff_required=bool(state.get("handoff_required")),
            handoff_reason=state.get("handoff_reason"),
            current_order_id=state.get("current_order_id"),
            collected_order_details=state.get("collected_order_details") or {},
        )

    async def get_state(self, phone: str) -> dict:
        config = {"configurable": {"thread_id": thread_id_for(phone)}}
        snapshot = await self._graph.aget_state(config)
        return snapshot.values if snapshot else {}


class InMemoryRuntime(_BaseRuntime):
    """First-functional-test runtime — memory lives only for the process lifetime."""

    def __init__(self):
        from langgraph.checkpoint.memory import MemorySaver

        super().__init__(build_graph(MemorySaver()))


class PersistentRuntime(_BaseRuntime):
    """Production/testing runtime — memory persists to a SQLite file so it survives
    an application restart. Must be used as an async context manager so the
    checkpointer connection is opened and closed cleanly."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or get_config().checkpoint_db
        self._cm = None

    async def __aenter__(self) -> "PersistentRuntime":
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        self._cm = AsyncSqliteSaver.from_conn_string(self._db_path)
        saver = await self._cm.__aenter__()
        self._graph = build_graph(saver)
        return self

    async def __aexit__(self, *exc) -> None:
        if self._cm is not None:
            await self._cm.__aexit__(*exc)
