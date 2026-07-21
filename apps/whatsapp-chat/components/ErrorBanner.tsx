import { AlertCircle } from "lucide-react";

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="mx-4 my-2 flex items-center gap-2 rounded-lg border border-wa-danger/30 bg-wa-danger/10 px-3 py-2 text-xs text-wa-danger">
      <AlertCircle size={14} className="shrink-0" />
      <span>{message}</span>
    </div>
  );
}
