import { Avatar } from "./Avatar";
import { cn } from "@/lib/utils";
import type { LocalConversation } from "@/lib/local-conversations";

export function ConversationListItem({
  conversation,
  active,
  onClick,
}: {
  conversation: LocalConversation;
  active: boolean;
  onClick: () => void;
}) {
  const time = new Date(conversation.updatedAt).toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });

  return (
    <button
      onClick={onClick}
      className={cn(
        "flex w-full items-center gap-3 border-b border-wa-border px-3 py-3 text-left transition-colors hover:bg-wa-panel",
        active && "bg-wa-panel"
      )}
    >
      <Avatar name={conversation.name} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <span className="truncate text-sm font-medium text-wa-text">{conversation.name}</span>
          <span className="shrink-0 text-[11px] text-wa-muted">{time}</span>
        </div>
        <p className="truncate text-xs text-wa-muted">{conversation.lastMessage || "No messages yet"}</p>
      </div>
    </button>
  );
}
