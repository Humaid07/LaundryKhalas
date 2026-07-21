"use client";

import { Send } from "lucide-react";
import { useState } from "react";

export function Composer({
  disabled,
  onSend,
}: {
  disabled: boolean;
  onSend: (text: string) => void;
}) {
  const [value, setValue] = useState("");

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  };

  return (
    <div className="flex items-end gap-2 border-t border-wa-border bg-wa-panel px-4 py-3">
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
        placeholder="Type a message"
        rows={1}
        className="max-h-32 flex-1 resize-none rounded-lg border border-wa-border bg-white px-4 py-2.5 text-sm text-wa-text placeholder:text-wa-muted focus:outline-none focus:ring-1 focus:ring-wa-accent"
      />
      <button
        onClick={submit}
        disabled={disabled || !value.trim()}
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-wa-accent text-white transition-colors hover:bg-wa-accent-dark disabled:cursor-not-allowed disabled:opacity-40"
        title="Send"
      >
        <Send size={17} />
      </button>
    </div>
  );
}
