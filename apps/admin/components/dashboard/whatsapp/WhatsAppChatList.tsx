"use client";

import { Search, SearchX, Inbox, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { StatusBadge } from "@/components/dashboard/ui/primitives";
import { formatClock } from "@/lib/dashboard/formatters";
import {
  statusMeta,
  activeFilterLabels,
  inboxFilterCount,
  type InboxConversation,
  type InboxFilter,
  type InboxFilterState,
} from "@/lib/dashboard/whatsapp-inbox";
import { InboxFilterMenu } from "./InboxFilterMenu";

/**
 * WhatsApp-Web-style chat list: search, a compact filter button, and one row per
 * conversation. Purely presentational — filtering/search state is owned by the
 * parent inbox so the selection and mobile view stay in sync.
 */
export function WhatsAppChatList({
  conversations,
  selectedId,
  onSelect,
  query,
  onQuery,
  filterState,
  onFilterChange,
  onClear,
  counts,
  className,
}: {
  conversations: InboxConversation[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  query: string;
  onQuery: (q: string) => void;
  filterState: InboxFilterState;
  onFilterChange: (next: InboxFilterState) => void;
  /** Clears both the search text and every active filter. */
  onClear: () => void;
  counts: Record<InboxFilter, number>;
  className?: string;
}) {
  const filterActive = inboxFilterCount(filterState) > 0;
  const activeLabels = activeFilterLabels(filterState);

  return (
    <div className={cn("flex min-h-0 flex-col border-border bg-surface", className)}>
      {/* Search + Filter */}
      <div className="border-b border-border p-3">
        <div className="flex items-center gap-2">
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-faint" />
            <input
              value={query}
              onChange={(e) => onQuery(e.target.value)}
              placeholder="Search chats"
              aria-label="Search chats"
              className="h-9 w-full rounded-full border border-border bg-surface-2 pl-9 pr-3 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none"
            />
          </div>
          <InboxFilterMenu state={filterState} onChange={onFilterChange} counts={counts} />
        </div>

        {/* Compact active-filter summary — one row, only when filters are set */}
        {filterActive && (
          <div className="mt-2 flex items-center">
            <span className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-full bg-rose/10 py-0.5 pl-2.5 pr-1 text-xxs font-medium text-rose">
              <span className="truncate">
                {activeLabels[0]}
                {activeLabels.length > 1 && <span className="text-rose/70"> +{activeLabels.length - 1}</span>}
              </span>
              <button
                type="button"
                onClick={() => onFilterChange({ humanNeeded: false, urgent: false, orderStatus: "any" })}
                aria-label="Clear filters"
                className="grid h-4 w-4 shrink-0 place-items-center rounded-full text-rose/70 transition-colors hover:bg-rose/20 hover:text-rose focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          </div>
        )}
      </div>

      {/* Rows */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {conversations.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center px-6 py-12 text-center text-ink-faint">
            <span className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-rose/10 text-rose">
              {query || filterActive ? <SearchX className="h-5 w-5" /> : <Inbox className="h-5 w-5" />}
            </span>
            <p className="text-sm font-medium text-ink">
              {query || filterActive ? "No conversations match" : "No conversations yet"}
            </p>
            <p className="mt-1 max-w-[15rem] text-xs">
              {query || filterActive
                ? "No conversations match the selected filters."
                : "Incoming WhatsApp conversations will appear here."}
            </p>
            {(query || filterActive) && (
              <button
                type="button"
                onClick={onClear}
                className="mt-3 inline-flex items-center gap-1 rounded-lg border border-border bg-surface-2 px-3 py-1.5 text-xs font-medium text-ink-muted transition-colors hover:border-border-strong hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40"
              >
                Clear filters
              </button>
            )}
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
