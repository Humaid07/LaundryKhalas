"use client";

import { useEffect, useRef } from "react";
import { ArrowLeft, PanelRightOpen, PanelRightClose, MapPin, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import { StatusBadge } from "@/components/dashboard/ui/primitives";
import { maskPhone, formatClock } from "@/lib/dashboard/formatters";
import {
  statusMeta,
  priorityTone,
  type InboxConversation,
  type InboxMessage,
  type InboxStatus,
} from "@/lib/dashboard/whatsapp-inbox";
import { HumanTakeoverComposer } from "./HumanTakeoverComposer";
import { ConversationFlagCard, OrderContextCard } from "./ConversationFlagCard";

/**
 * Right pane — the selected WhatsApp thread. Reads like WhatsApp: incoming
 * bubbles left, outgoing (agent/human) bubbles right, internal flags as
 * separate note cards. The composer only appears during a human takeover.
 */
export function WhatsAppConversationPane({
  conversation,
  onBack,
  contextOpen,
  onToggleContext,
  onTakeOver,
  onReturnToBot,
  onResolve,
  onSendHuman,
  className,
}: {
  conversation: InboxConversation | null;
  onBack: () => void;
  contextOpen: boolean;
  onToggleContext: () => void;
  onTakeOver: () => void;
  onReturnToBot: () => void;
  onResolve: () => void;
  onSendHuman: (text: string) => void;
  className?: string;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [conversation?.id, conversation?.messages.length]);

  if (!conversation) {
    return (
      <div className={cn("hidden flex-col items-center justify-center bg-surface-2/40 text-center md:flex", className)}>
        <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-rose/10 text-rose">
          <Info className="h-5 w-5" />
        </span>
        <p className="text-sm font-medium text-ink">Select a conversation</p>
        <p className="mt-1 max-w-xs text-xs text-ink-muted">
          Pick a chat on the left to view the thread and take over when needed.
        </p>
      </div>
    );
  }

  const meta = statusMeta[conversation.status];

  return (
    <div className={cn("flex min-h-0 min-w-0 flex-col bg-surface", className)}>
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-border p-3">
        <button
          type="button"
          onClick={onBack}
          className="flex h-9 w-9 items-center justify-center rounded-lg text-ink-muted hover:bg-surface-2 md:hidden"
          aria-label="Back to chats"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-rose/12 font-display text-xs font-bold text-rose">
          {conversation.customerName.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase()}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-ink">{conversation.customerName}</p>
          <p className="flex items-center gap-1.5 text-xxs text-ink-faint">
            <span>{maskPhone(conversation.phone)}</span>
            <span aria-hidden>·</span>
            <MapPin className="h-3 w-3" />
            <span className="truncate">
              {conversation.area}, {conversation.city}
            </span>
            {conversation.service && (
              <>
                <span aria-hidden>·</span>
                <span className="truncate">{conversation.service}</span>
              </>
            )}
          </p>
        </div>
        <div className="hidden items-center gap-1.5 sm:flex">
          {conversation.priority === "urgent" && (
            <StatusBadge tone="danger" dot={false} className="uppercase">
              Urgent
            </StatusBadge>
          )}
          {conversation.order && (
            <span className="font-mono text-xxs text-ink-faint">{conversation.order.id}</span>
          )}
          <StatusBadge tone={meta.tone} dot={false}>
            {meta.label}
          </StatusBadge>
        </div>
        <button
          type="button"
          onClick={onToggleContext}
          className="hidden h-9 w-9 items-center justify-center rounded-lg text-ink-muted hover:bg-surface-2 xl:flex"
          aria-label={contextOpen ? "Hide details" : "Show details"}
        >
          {contextOpen ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
        </button>
      </div>

      {/* Thread */}
      <div
        ref={scrollRef}
        className="min-h-0 flex-1 space-y-2.5 overflow-y-auto bg-surface-2/40 p-4"
      >
        {conversation.messages.map((m) => (
          <MessageBubble key={m.id} m={m} />
        ))}
      </div>

      {/* Resolve strip (only when a human is/was involved and it isn't resolved) */}
      {conversation.status !== "resolved" && conversation.status !== "bot" && (
        <div className="flex items-center justify-end border-t border-border bg-surface px-4 py-1.5">
          <button type="button" onClick={onResolve} className="text-xxs font-medium text-ink-muted hover:text-success">
            Mark resolved
          </button>
        </div>
      )}

      {/* Composer / takeover control */}
      <HumanTakeoverComposer
        status={conversation.status}
        onTakeOver={onTakeOver}
        onReturnToBot={onReturnToBot}
        onSend={onSendHuman}
        suggestedReply={conversation.flag?.suggestedReply}
      />
    </div>
  );
}

/* ------------------------------ message bubble ----------------------------- */

function MessageBubble({ m }: { m: InboxMessage }) {
  // Internal / system note — a distinct card, never a customer-style bubble.
  if (m.sender === "system" || m.isInternal) {
    return (
      <div className="flex justify-center py-1">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-warning/25 bg-warning/[0.08] px-3 py-1 text-[11px] text-warning">
          <Info className="h-3 w-3" />
          {m.text}
        </span>
      </div>
    );
  }

  const incoming = m.sender === "customer";
  const isHuman = m.sender === "human";

  return (
    <div className={incoming ? "flex justify-start" : "flex justify-end"}>
      <div className="max-w-[78%]">
        <div
          className={cn(
            "px-3.5 py-2 text-sm shadow-card",
            incoming
              ? "rounded-2xl rounded-tl-sm border border-border bg-surface text-ink"
              : isHuman
                ? "rounded-2xl rounded-tr-sm bg-info text-white"
                : "rounded-2xl rounded-tr-sm bg-rose/90 text-rose-contrast",
          )}
        >
          <p className="whitespace-pre-wrap">{m.text}</p>
          <span
            className={cn(
              "mt-0.5 flex items-center justify-end gap-1 text-[10px]",
              incoming ? "text-ink-faint" : "text-white/75",
            )}
          >
            {m.authorLabel && <span>{m.authorLabel}</span>}
            {m.authorLabel && <span aria-hidden>·</span>}
            {formatClock(m.createdAt)}
          </span>
        </div>

        {/* Quick-reply / menu buttons attach to this specific agent message. */}
        {m.actions && m.actions.length > 0 && (
          <div className="mt-1.5 flex flex-wrap justify-end gap-1.5">
            {m.actions.map((a) => (
              <span
                key={a.id}
                className="rounded-lg border border-rose/30 bg-rose/8 px-2.5 py-1 text-xxs font-medium text-rose"
              >
                {a.label}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ------------------------------ context panel ------------------------------ */

export function ConversationContextPanel({
  conversation,
  className,
}: {
  conversation: InboxConversation;
  className?: string;
}) {
  const statusLabel = statusMeta[conversation.status].label;
  return (
    <aside className={cn("min-h-0 space-y-3 overflow-y-auto border-border bg-surface p-3.5", className)}>
      <div>
        <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Conversation</p>
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <StatusBadge tone={statusMeta[conversation.status].tone} dot={false}>
            {statusLabel}
          </StatusBadge>
          {conversation.priority && (
            <StatusBadge tone={priorityTone[conversation.priority]} dot={false} className="uppercase">
              {conversation.priority}
            </StatusBadge>
          )}
        </div>
        <p className="mt-2 text-xs text-ink-muted">
          {maskPhone(conversation.phone)} · {conversation.area}, {conversation.city}
        </p>
      </div>

      {conversation.flag && <ConversationFlagCard flag={conversation.flag} />}

      <div>
        <p className="mb-2 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Linked order</p>
        {conversation.order ? (
          <OrderContextCard order={conversation.order} />
        ) : (
          <div className="rounded-xl border border-dashed border-border bg-surface-2 px-3.5 py-4 text-center text-xs text-ink-muted">
            No linked order yet
          </div>
        )}
      </div>

      {conversation.notes.length > 0 && (
        <div>
          <p className="mb-2 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Internal notes</p>
          <ul className="space-y-1.5">
            {conversation.notes.map((n, i) => (
              <li key={i} className="rounded-lg border border-border bg-surface-2 px-3 py-2 text-xs text-ink-muted">
                {n}
              </li>
            ))}
          </ul>
        </div>
      )}
    </aside>
  );
}

// Re-export status type consumers may want alongside the pane.
export type { InboxStatus };
