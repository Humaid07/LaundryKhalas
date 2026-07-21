import { ShieldAlert } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatBubbleTime } from "@/lib/formatters";
import type { Message, MessageAction } from "@/lib/types";

export function MessageBubble({
  message,
  onActionClick,
  actionsDisabled,
}: {
  message: Message;
  onActionClick?: (action: MessageAction) => void;
  actionsDisabled?: boolean;
}) {
  const outgoing = message.direction === "outbound";
  const refused = message.domain_status === "out_of_domain" && outgoing;
  const actions = message.actions ?? [];

  return (
    <div className={cn("flex flex-col", outgoing ? "items-end" : "items-start")}>
      <div
        className={cn(
          "relative max-w-[75%] rounded-bubble px-3 py-2 text-sm shadow-sm",
          outgoing
            ? "wa-bubble-tail-out rounded-tr-none bg-wa-outgoing text-wa-text"
            : "wa-bubble-tail-in rounded-tl-none bg-wa-incoming text-wa-text"
        )}
      >
        {refused && (
          <div className="mb-1 flex items-center gap-1 text-[11px] font-medium text-wa-muted">
            <ShieldAlert size={12} />
            Out of scope — redirected
          </div>
        )}
        <p className="whitespace-pre-wrap break-words">{message.text}</p>
        <span className="mt-1 block text-right text-[10px] text-wa-muted">
          {formatBubbleTime(message.created_at)}
        </span>
      </div>

      {actions.length > 0 && (
        <div className="mt-1.5 flex w-full max-w-[75%] flex-col gap-1.5 rounded-lg border border-wa-border bg-white p-1.5 shadow-sm">
          {actions.map((action) => (
            <button
              key={action.id}
              disabled={actionsDisabled}
              onClick={() => onActionClick?.(action)}
              className="rounded-full border border-wa-accent px-3 py-2 text-center text-xs font-medium text-wa-accent-dark transition-colors hover:bg-wa-accent/10 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
