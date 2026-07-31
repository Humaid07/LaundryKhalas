import { Bot, ShieldCheck, User } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatDateTime } from "@/lib/formatters";
import type { Message } from "@/lib/types";

export function ChatMessageBubble({ message }: { message: Message }) {
  const isInbound = message.direction === "inbound";
  const senderIcon =
    message.sender_type === "agent" ? Bot : message.sender_type === "admin" ? ShieldCheck : User;
  const SenderIcon = senderIcon;

  return (
    <div className={cn("flex", isInbound ? "justify-start" : "justify-end")}>
      <div className={cn("max-w-[75%]", isInbound ? "items-start" : "items-end", "flex flex-col gap-1")}>
        <div
          className={cn(
            "rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-sm",
            isInbound
              ? "rounded-bl-sm border border-border bg-surface text-ink"
              : "rounded-br-sm bg-rose text-rose-contrast"
          )}
        >
          {message.text}
        </div>
        <div
          className={cn(
            "flex items-center gap-1.5 px-1 text-xxs text-ink-faint",
            isInbound ? "flex-row" : "flex-row-reverse"
          )}
        >
          <SenderIcon className="h-3 w-3" />
          <span className="capitalize">{message.sender_type}</span>
          <span>&middot;</span>
          <span>{formatDateTime(message.created_at)}</span>
          <span>&middot;</span>
          <span className="capitalize">{message.status.replace(/_/g, " ")}</span>
        </div>
      </div>
    </div>
  );
}

export function AgentDraftBubble({
  text,
  onApprove,
  onReject,
  isDeciding,
}: {
  text: string;
  onApprove: () => void;
  onReject: () => void;
  isDeciding: boolean;
}) {
  return (
    <div className="flex justify-end">
      <div className="flex max-w-[75%] flex-col items-end gap-1.5">
        <span className="inline-flex items-center gap-1 rounded-full bg-warning/10 px-2.5 py-0.5 text-xxs font-semibold text-warning">
          Agent Draft &mdash; Pending Approval
        </span>
        <div className="rounded-2xl rounded-br-sm border border-dashed border-warning/40 bg-warning/10 px-4 py-2.5 text-sm leading-relaxed text-ink">
          {text}
        </div>
        <div className="flex gap-2">
          <button
            onClick={onReject}
            disabled={isDeciding}
            className="rounded-lg border border-border-strong bg-surface px-3 py-1 text-xs font-medium text-ink hover:bg-surface-2 disabled:opacity-50"
          >
            Reject
          </button>
          <button
            onClick={onApprove}
            disabled={isDeciding}
            className="rounded-lg bg-rose px-3 py-1 text-xs font-medium text-rose-contrast hover:bg-rose-strong disabled:opacity-50"
          >
            Approve Reply
          </button>
        </div>
      </div>
    </div>
  );
}
