"use client";

import { Search, SearchX, Inbox } from "lucide-react";
import { cn } from "@/lib/utils";
import { StatusBadge } from "@/components/dashboard/ui/primitives";
import { formatClock } from "@/lib/dashboard/formatters";
import {
  statusMeta,
  inboxFilters,
  type InboxConversation,
  type InboxFilter,
} from "@/lib/dashboard/whatsapp-inbox";

/**
 * WhatsApp-Web-style chat list: search, filter chips, and one row per
 * conversation. Purely presentational — filtering/search state is owned by the
 * parent inbox so the selection and mobile view stay in sync.
 */
export function WhatsAppChatList({
  conversations,
  selectedId,
  onSelect,
  query,
  onQuery,
  filter,
  onFilter,
  counts,
  className,
}: {
  conversations: InboxConversation[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  query: string;
  onQuery: (q: string) => void;
  filter: InboxFilter;
  onFilter: (f: InboxFilter) => void;
  counts: Record<InboxFilter, number>;
  className?: string;
}) {
  return (
    <div className={cn("flex min-h-0 flex-col border-border bg-surface", className)}>
      {/* Search */}
      <div className="border-b border-border p-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-faint" />
          <input
            value={query}
            onChange={(e) => onQuery(e.target.value)}
            placeholder="Search chats"
            aria-label="Search chats"
            className="h-9 w-full rounded-full border border-border bg-surface-2 pl-9 pr-3 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none"
          />
        </div>

        {/* Filter chips */}
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {inboxFilters.map((f) => {
            const on = filter === f.id;
            const count = counts[f.id];
            return (
              <button
                key={f.id}
                type="button"
                onClick={() => onFilter(f.id)}
                className={cn(
                  "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xxs font-medium transition-colors",
                  on
                    ? "bg-rose text-rose-contrast"
                    : "bg-surface-2 text-ink-muted hover:text-ink ring-1 ring-inset ring-border",
                )}
              >
                {f.label}
                {count > 0 && (
                  <span className={cn("tnum", on ? "text-rose-contrast/80" : "text-ink-faint")}>
                    {count}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Rows */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {conversations.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center px-6 py-12 text-center text-ink-faint">
            <span className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-rose/10 text-rose">
              {query || filter !== "all" ? <SearchX className="h-5 w-5" /> : <Inbox className="h-5 w-5" />}
            </span>
            <p className="text-sm font-medium text-ink">
              {query || filter !== "all" ? "No matching chats" : "No conversations yet"}
            </p>
            <p className="mt-1 max-w-[14rem] text-xs">
              {query || filter !== "all"
                ? "Try a different search or filter."
                : "Incoming WhatsApp conversations will appear here."}
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {conversations.map((c) => (
              <ChatRow key={c.id} c={c} active={c.id === selectedId} onSelect={() => onSelect(c.id)} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function ChatRow({ c, active, onSelect }: { c: InboxConversation; active: boolean; onSelect: () => void }) {
  const meta = statusMeta[c.status];
  const urgent = c.priority === "urgent";
  const initials = c.customerName
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        aria-current={active}
        className={cn(
          "flex w-full items-start gap-3 px-3 py-3 text-left transition-colors",
          active ? "bg-rose/[0.06]" : "hover:bg-surface-2",
        )}
      >
        <span
          className={cn(
            "flex h-10 w-10 shrink-0 items-center justify-center rounded-full font-display text-xs font-bold",
            urgent ? "bg-danger/12 text-danger" : "bg-rose/12 text-rose",
          )}
        >
          {initials}
        </span>

        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2">
            <span className="truncate text-sm font-semibold text-ink">{c.customerName}</span>
            <span className="ml-auto shrink-0 text-xxs text-ink-faint tnum">{formatClock(c.lastMessageAt)}</span>
          </span>

          <span className="mt-0.5 flex items-center gap-2">
            <span className={cn("truncate text-xs", c.unread > 0 ? "font-medium text-ink" : "text-ink-muted")}>
              {c.lastMessage}
            </span>
            {c.unread > 0 && (
              <span className="ml-auto flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-rose px-1.5 text-[10px] font-bold text-rose-contrast tnum">
                {c.unread}
              </span>
            )}
          </span>

          <span className="mt-1.5 flex flex-wrap items-center gap-1.5">
            {urgent && (
              <StatusBadge tone="danger" dot={false} className="uppercase">
                Urgent
              </StatusBadge>
            )}
            <StatusBadge tone={meta.tone} dot={false}>
              {meta.label}
            </StatusBadge>
            {c.order && <span className="font-mono text-[10px] text-ink-faint">{c.order.id}</span>}
          </span>
        </span>
      </button>
    </li>
  );
}
