"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Tone } from "@/lib/dashboard/types";
import { StatusBadge } from "@/components/dashboard/ui/primitives";

export type CompactField = { label: string; value: ReactNode };

/**
 * CompactRecordCard — the minimal, click-through record card used on main pages.
 *
 * Progressive-disclosure contract (docs/architecture/minimal-dashboard-design-system.md):
 *   • ONE status badge, never a cluster.
 *   • 2–3 preview fields MAX (anything past index 3 is dropped on purpose).
 *   • NO actions — the whole card is a link/button into the full detail page.
 *   • A trailing chevron signals "there is more inside".
 */
export function CompactRecordCard({
  id,
  title,
  status,
  fields,
  meta,
  href,
  onClick,
}: {
  /** Short record identifier, e.g. an order id (rendered mono). */
  id?: string;
  title: ReactNode;
  /** Single status chip. Keep to one signal per card. */
  status?: { label: ReactNode; tone: Tone };
  /** Preview fields — capped at 3. Full data lives on the detail page. */
  fields?: CompactField[];
  /** Optional trailing note (e.g. SLA, amount) shown quietly on the right. */
  meta?: ReactNode;
  href?: string;
  onClick?: () => void;
}) {
  const preview = (fields ?? []).slice(0, 3);
  const interactive = !!href || !!onClick;

  const body = (
    <>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          {id && <span className="font-mono text-xs font-semibold text-rose">{id}</span>}
          {status && (
            <StatusBadge tone={status.tone} dot={false}>
              {status.label}
            </StatusBadge>
          )}
        </div>
        <p className="mt-1.5 truncate text-[0.95rem] font-semibold text-ink">{title}</p>
        {preview.length > 0 && (
          <dl className="mt-3 flex flex-wrap gap-x-8 gap-y-2">
            {preview.map((f, i) => (
              <div key={i} className="min-w-0">
                <dt className="text-xxs uppercase tracking-eyebrow text-ink-faint">{f.label}</dt>
                <dd className="mt-0.5 truncate text-sm font-medium text-ink">{f.value ?? "—"}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-3 self-center">
        {meta && <div className="text-right text-xs text-ink-muted">{meta}</div>}
        {interactive && <ChevronRight className="h-4 w-4 text-ink-faint transition-colors group-hover:text-rose" />}
      </div>
    </>
  );

  const base = "flex w-full items-stretch gap-4 rounded-2xl border border-border/70 bg-surface p-5 text-left shadow-card";
  const cls = interactive
    ? `group ${base} transition-all duration-200 ease-out-quint hover:-translate-y-0.5 hover:border-border-strong hover:shadow-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40`
    : base;

  if (href) {
    return (
      <Link href={href} className={cls}>
        {body}
      </Link>
    );
  }
  if (onClick) {
    return (
      <button type="button" onClick={onClick} className={cls}>
        {body}
      </button>
    );
  }
  return <div className={cls}>{body}</div>;
}

/**
 * Vertical list wrapper for CompactRecordCards. A single-column list reads calmer
 * and more scannable than a dense multi-column card grid (Linear-style). Use this
 * as the default main-page record layout.
 */
export function RecordList({ children }: { children: ReactNode }) {
  return <div className="space-y-3">{children}</div>;
}
