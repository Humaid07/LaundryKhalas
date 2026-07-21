"use client";

import { MessageSquarePlus, Search, Settings } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { ConversationListItem } from "./ConversationListItem";
import type { LocalConversation } from "@/lib/local-conversations";

export function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNewChat,
}: {
  conversations: LocalConversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
}) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return conversations;
    return conversations.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.phone.toLowerCase().includes(q) ||
        c.lastMessage.toLowerCase().includes(q)
    );
  }, [conversations, query]);

  return (
    <aside className="flex h-full w-full max-w-xs shrink-0 flex-col border-r border-wa-border bg-wa-sidebar">
      <div className="flex items-center justify-between border-b border-wa-border bg-wa-panel px-4 py-3">
        <span className="text-sm font-semibold text-wa-text">LaundryKhalaas Chats</span>
        <div className="flex items-center gap-1">
          <button
            onClick={onNewChat}
            title="New chat"
            className="rounded-full p-2 text-wa-muted transition-colors hover:bg-black/5 hover:text-wa-text"
          >
            <MessageSquarePlus size={18} />
          </button>
          <Link
            href="/settings"
            title="Settings"
            className="rounded-full p-2 text-wa-muted transition-colors hover:bg-black/5 hover:text-wa-text"
          >
            <Settings size={18} />
          </Link>
        </div>
      </div>

      <div className="border-b border-wa-border px-3 py-2">
        <div className="flex items-center gap-2 rounded-lg bg-wa-panel px-3 py-1.5">
          <Search size={15} className="text-wa-muted" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search or start a new chat"
            className="w-full bg-transparent text-sm text-wa-text placeholder:text-wa-muted focus:outline-none"
          />
        </div>
      </div>

      <div className="scrollbar-thin flex-1 overflow-y-auto">
        {filtered.length === 0 ? (
          <div className="px-4 py-10 text-center text-sm text-wa-muted">
            {conversations.length === 0
              ? "No conversations yet. Start a new chat to test the agent."
              : "No conversations match your search."}
          </div>
        ) : (
          filtered.map((c) => (
            <ConversationListItem
              key={c.id}
              conversation={c}
              active={c.id === activeId}
              onClick={() => onSelect(c.id)}
            />
          ))
        )}
      </div>
    </aside>
  );
}
