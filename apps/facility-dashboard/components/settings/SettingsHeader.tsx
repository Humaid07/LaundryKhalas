import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowLeft } from "lucide-react";

/** Consistent back-link + title header for a settings subpage. */
export function SettingsHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div>
      <Link
        href="/settings"
        className="inline-flex items-center gap-1.5 text-xs font-medium text-ink-muted transition-colors hover:text-ink"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Settings
      </Link>
      <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">{title}</h1>
          {description && <p className="mt-1.5 max-w-2xl text-sm text-ink-muted">{description}</p>}
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </div>
    </div>
  );
}
