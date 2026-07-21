import { MessageCircle } from "lucide-react";

export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-wa-panel text-wa-muted">
        <MessageCircle size={28} />
      </div>
      <div>
        <p className="text-sm font-medium text-wa-text">{title}</p>
        <p className="mt-1 max-w-xs text-xs text-wa-muted">{description}</p>
      </div>
    </div>
  );
}
