import type { ReactNode } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * DetailPageShell — the frame for a full record detail page. This is where the
 * heavy information and ALL record actions live.
 */
export function DetailPageShell({
  backHref,
  backLabel = "Back",
  eyebrow,
  title,
  status,
  actions,
  children,
}: {
  backHref: string;
  backLabel?: string;
  eyebrow?: string;
  title: ReactNode;
  status?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="lk-enter space-y-8">
      <div>
        <Link
          href={backHref}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-ink-muted transition-colors hover:text-ink"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> {backLabel}
        </Link>
        <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            {eyebrow && <p className="mb-1.5 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">{eyebrow}</p>}
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="font-display text-2xl font-semibold tracking-tight text-ink">{title}</h1>
              {status && <div className="flex flex-wrap items-center gap-1.5">{status}</div>}
            </div>
          </div>
          {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
        </div>
      </div>
      {children}
    </div>
  );
}

/** Two-column detail body: a wide main column + a sticky sidebar (Stripe-style). */
export function DetailColumns({
  main,
  sidebar,
  className,
}: {
  main: ReactNode;
  sidebar: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("grid gap-6 lg:grid-cols-3", className)}>
      <div className="space-y-6 lg:col-span-2">{main}</div>
      <div className="space-y-6">
        <div className="space-y-6 lg:sticky lg:top-6">{sidebar}</div>
      </div>
    </div>
  );
}
