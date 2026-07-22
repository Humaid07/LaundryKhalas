/**
 * WhatsApp-style "agent is typing" bubble: a small incoming bubble with three
 * animated dots, aligned left like an agent message. It is a normal message
 * row (no overlay, no full-screen loader) that appears while we hold the reply
 * for a natural 2-3s, then is replaced by the actual agent bubble.
 */
export function TypingIndicator() {
  return (
    <div className="flex flex-col items-start" aria-live="polite" aria-label="LaundryKhalas is typing">
      <div className="wa-bubble-tail-in relative max-w-[75%] rounded-bubble rounded-tl-none bg-wa-incoming px-3 py-2.5 shadow-sm">
        <span className="flex items-center gap-1">
          <span className="wa-typing-dot" />
          <span className="wa-typing-dot" />
          <span className="wa-typing-dot" />
        </span>
      </div>
    </div>
  );
}
