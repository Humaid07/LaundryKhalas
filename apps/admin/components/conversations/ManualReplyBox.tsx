"use client";

import { useState } from "react";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { InlineSpinner } from "@/components/ui/loading-state";

export function ManualReplyBox({
  onSend,
  isSending,
  notice,
}: {
  onSend: (text: string) => void;
  isSending: boolean;
  notice?: string;
}) {
  const [text, setText] = useState("");

  const handleSend = () => {
    if (!text.trim()) return;
    onSend(text.trim());
    setText("");
  };

  return (
    <div className="border-t border-border bg-white p-4">
      {notice && <p className="mb-2 text-xs text-ink-muted">{notice}</p>}
      <div className="flex items-end gap-2">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Type a manual reply…"
          rows={2}
          className="flex-1 resize-none rounded-lg border border-border-strong bg-white px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:outline-none focus:ring-2 focus:ring-brand/30"
        />
        <Button variant="primary" onClick={handleSend} disabled={isSending || !text.trim()}>
          {isSending ? <InlineSpinner className="text-white" /> : <Send className="h-3.5 w-3.5" />}
          Send Manual Reply
        </Button>
      </div>
    </div>
  );
}
