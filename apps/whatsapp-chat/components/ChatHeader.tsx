"use client";

import { Bug, MoreVertical } from "lucide-react";
import { Avatar } from "./Avatar";
import { cn } from "@/lib/utils";

export function ChatHeader({
  name,
  phone,
  editable,
  onNameChange,
  onPhoneChange,
  debugOpen,
  onToggleDebug,
}: {
  name: string;
  phone: string;
  editable: boolean;
  onNameChange: (v: string) => void;
  onPhoneChange: (v: string) => void;
  debugOpen: boolean;
  onToggleDebug: () => void;
}) {
  return (
    <div className="flex items-center justify-between border-b border-wa-border bg-wa-panel px-4 py-2.5">
      <div className="flex min-w-0 items-center gap-3">
        <Avatar name={name} size={38} />
        <div className="min-w-0">
          {editable ? (
            <input
              value={name}
              onChange={(e) => onNameChange(e.target.value)}
              placeholder="Customer name"
              className="w-40 bg-transparent text-sm font-medium text-wa-text placeholder:text-wa-muted focus:outline-none"
            />
          ) : (
            <p className="truncate text-sm font-medium text-wa-text">{name}</p>
          )}
          {editable ? (
            <input
              value={phone}
              onChange={(e) => onPhoneChange(e.target.value)}
              placeholder="Phone number (optional)"
              className="w-40 bg-transparent text-xs text-wa-muted placeholder:text-wa-muted/70 focus:outline-none"
            />
          ) : (
            <p className="truncate text-xs text-wa-muted">{phone || "local test conversation"}</p>
          )}
        </div>
      </div>
      <div className="flex items-center gap-1">
        <button
          onClick={onToggleDebug}
          title="Toggle developer/debug panel"
          className={cn(
            "rounded-full p-2 text-wa-muted transition-colors hover:bg-black/5 hover:text-wa-text",
            debugOpen && "bg-black/5 text-wa-accent-dark"
          )}
        >
          <Bug size={17} />
        </button>
        <button className="rounded-full p-2 text-wa-muted hover:bg-black/5 hover:text-wa-text">
          <MoreVertical size={17} />
        </button>
      </div>
    </div>
  );
}
