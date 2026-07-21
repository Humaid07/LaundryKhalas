"use client";

import { useState } from "react";
import { Send, Bot, UserCog, CheckCircle2, Lock } from "lucide-react";
import { Button } from "@/components/dashboard/ui/Button";
import type { InboxStatus } from "@/lib/dashboard/whatsapp-inbox";

/**
 * Bottom-of-conversation control. It is NOT a general chat box — customer
 * messages never originate here. The text composer is available ONLY while a
 * human takeover is active; otherwise the operator sees why the bot is in
 * control and a way to take over.
 */
export function HumanTakeoverComposer({
  status,
  onTakeOver,
  onReturnToBot,
  onSend,
  suggestedReply,
}: {
  status: InboxStatus;
  onTakeOver: () => void;
  onReturnToBot: () => void;
  onSend: (text: string) => void;
  suggestedReply?: string;
}) {
  const [text, setText] = useState("");

  function submit() {
    const value = text.trim();
    if (!value) return;
    onSend(value);
    setText("");
  }

  if (status === "resolved") {
    return (
      <div className="flex items-center justify-center gap-2 border-t border-border bg-surface-2/60 px-4 py-3.5 text-xs text-ink-muted">
        <CheckCircle2 className="h-4 w-4 text-success" />
        This conversation is resolved.
        <button type="button" onClick={onTakeOver} className="font-medium text-rose hover:underline">
          Reopen with takeover
        </button>
      </div>
    );
  }

  // Bot handling (with or without a raised flag) — composer stays closed.
  if (status !== "human_takeover") {
    const flagged = status === "human_needed";
    return (
      <div className="flex flex-col gap-2.5 border-t border-border bg-surface-2/60 px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between">
        <p className="flex items-center gap-2 text-xs text-ink-muted">
          {flagged ? (
            <>
              <UserCog className="h-4 w-4 text-warning" />
              The agent flagged this for a human. Take over to reply.
            </>
          ) : (
            <>
              <Bot className="h-4 w-4 text-info" />
              Bot is handling this conversation.
            </>
          )}
        </p>
        <Button size="sm" variant={flagged ? "primary" : "secondary"} onClick={onTakeOver}>
          <UserCog className="h-3.5 w-3.5" /> Take over
        </Button>
      </div>
    );
  }

  // Human takeover active — real composer.
  return (
    <div className="border-t border-border bg-rose/[0.03] px-4 py-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-xxs font-semibold uppercase tracking-eyebrow text-rose">
          <Lock className="h-3 w-3" /> Human takeover active
        </span>
        <Button size="sm" variant="ghost" onClick={onReturnToBot}>
          <Bot className="h-3.5 w-3.5" /> Return to bot
        </Button>
      </div>

      {suggestedReply && !text && (
        <button
          type="button"
          onClick={() => setText(suggestedReply)}
          className="mb-2 w-full truncate rounded-lg border border-dashed border-border bg-surface px-3 py-1.5 text-left text-xs text-ink-muted transition-colors hover:border-rose/40 hover:text-ink"
          title="Use suggested reply"
        >
          Use suggested: “{suggestedReply}”
        </button>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="flex items-end gap-2"
      >
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          rows={1}
          placeholder="Type a human reply…"
          className="max-h-32 min-h-[2.5rem] flex-1 resize-none rounded-xl border border-border bg-surface px-3.5 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none"
        />
        <Button type="submit" variant="primary" size="icon" disabled={!text.trim()} aria-label="Send reply">
          <Send className="h-4 w-4" />
        </Button>
      </form>
    </div>
  );
}
