"use client";

import { useMemo, useState } from "react";
import {
  seedConversations,
  matchesFilter,
  matchesSearch,
  inboxFilters,
  type InboxConversation,
  type InboxFilter,
  type InboxMessage,
} from "@/lib/dashboard/whatsapp-inbox";
import { WhatsAppChatList } from "./WhatsAppChatList";
import { WhatsAppConversationPane, ConversationContextPanel } from "./WhatsAppConversationPane";

/**
 * Operational WhatsApp inbox — the operator's view of the WhatsApp Operations
 * Agent. Left: chat list. Right: the selected thread. Optional: an order/flag
 * context panel. Human takeover is only offered when the agent raises a flag or
 * the operator opts in; the composer is gated to takeover mode.
 *
 * State is local + seeded for now. Every mutation (take over, return to bot,
 * resolve, human reply) maps 1:1 to a documented backend endpoint so this can
 * be wired to real conversations without changing the UI.
 */
export function WhatsAppInbox() {
  const [conversations, setConversations] = useState<InboxConversation[]>(() =>
    seedConversations.map((c) => ({ ...c, messages: [...c.messages], notes: [...c.notes] })),
  );
  const [selectedId, setSelectedId] = useState<string | null>(seedConversations[0]?.id ?? null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<InboxFilter>("all");
  const [contextOpen, setContextOpen] = useState(true);
  const [mobileChatOpen, setMobileChatOpen] = useState(false);

  const visible = useMemo(
    () => conversations.filter((c) => matchesFilter(c, filter) && matchesSearch(c, query)),
    [conversations, filter, query],
  );

  const counts = useMemo(() => {
    const out = {} as Record<InboxFilter, number>;
    for (const f of inboxFilters) out[f.id] = conversations.filter((c) => matchesFilter(c, f.id)).length;
    return out;
  }, [conversations]);

  const selected = conversations.find((c) => c.id === selectedId) ?? null;

  /* ------------------------------- mutations ------------------------------- */

  function patch(id: string, fn: (c: InboxConversation) => InboxConversation) {
    setConversations((prev) => prev.map((c) => (c.id === id ? fn(c) : c)));
  }

  function appendMessage(c: InboxConversation, msg: InboxMessage): InboxConversation {
    return {
      ...c,
      messages: [...c.messages, msg],
      lastMessage: msg.isInternal || msg.sender === "system" ? c.lastMessage : msg.text,
      lastMessageAt: msg.isInternal || msg.sender === "system" ? c.lastMessageAt : msg.createdAt,
    };
  }

  function handleSelect(id: string) {
    setSelectedId(id);
    setMobileChatOpen(true);
    patch(id, (c) => ({ ...c, unread: 0 }));
  }

  function handleTakeOver() {
    if (!selected) return;
    patch(selected.id, (c) =>
      appendMessage({ ...c, status: "human_takeover" }, note("Human takeover active — operator is now replying")),
    );
  }

  function handleReturnToBot() {
    if (!selected) return;
    patch(selected.id, (c) =>
      appendMessage({ ...c, status: "bot", priority: null, flag: null }, note("Returned to bot — the agent will continue")),
    );
  }

  function handleResolve() {
    if (!selected) return;
    patch(selected.id, (c) =>
      appendMessage({ ...c, status: "resolved" }, note("Conversation marked resolved")),
    );
  }

  function handleSendHuman(text: string) {
    if (!selected) return;
    patch(selected.id, (c) =>
      appendMessage({ ...c, status: "human_takeover" }, {
        id: `h-${c.messages.length + 1}-${c.id}`,
        sender: "human",
        text,
        createdAt: new Date().toISOString(),
        authorLabel: "Sent by Human",
      }),
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-surface shadow-card">
      <div
        className={
          contextOpen
            ? "grid h-[38rem] md:grid-cols-[minmax(260px,300px)_1fr] xl:grid-cols-[300px_1fr_300px]"
            : "grid h-[38rem] md:grid-cols-[minmax(260px,300px)_1fr]"
        }
      >
        <WhatsAppChatList
          conversations={visible}
          selectedId={selectedId}
          onSelect={handleSelect}
          query={query}
          onQuery={setQuery}
          filter={filter}
          onFilter={setFilter}
          counts={counts}
          className={mobileChatOpen ? "hidden border-r md:flex" : "flex border-r"}
        />

        <WhatsAppConversationPane
          conversation={selected}
          onBack={() => setMobileChatOpen(false)}
          contextOpen={contextOpen}
          onToggleContext={() => setContextOpen((v) => !v)}
          onTakeOver={handleTakeOver}
          onReturnToBot={handleReturnToBot}
          onResolve={handleResolve}
          onSendHuman={handleSendHuman}
          className={mobileChatOpen ? "flex" : "hidden md:flex"}
        />

        {contextOpen && selected && (
          <ConversationContextPanel conversation={selected} className="hidden border-l xl:block" />
        )}
      </div>
    </div>
  );
}

function note(text: string): InboxMessage {
  return {
    id: `n-${Math.random().toString(36).slice(2, 9)}`,
    sender: "system",
    text,
    createdAt: new Date().toISOString(),
    isInternal: true,
  };
}
