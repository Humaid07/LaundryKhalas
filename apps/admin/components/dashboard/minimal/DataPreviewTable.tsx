"use client";

import type { ReactNode } from "react";
import { useRouter } from "next/navigation";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

export type PreviewColumn<T> = {
  key: string;
  header: string;
  cell: (row: T) => ReactNode;
  align?: "left" | "right";
  /** Becomes the card title on mobile. */
  primary?: boolean;
};

/**
 * DataPreviewTable — a calm, click-through table for main pages.
 *
 * Rows are previews: keep to the few columns that let an operator scan and
 * choose. The full record opens on its detail page (rowHref / onRowClick). No
 * inline row actions — actions live on the detail page. Responsive: collapses to
 * labeled cards under md. See docs/architecture/minimal-dashboard-design-system.md.
 */
export function DataPreviewTable<T>({
  columns,
  rows,
  rowKey,
  rowHref,
  onRowClick,
  empty,
  className,
}: {
  columns: PreviewColumn<T>[];
  rows: T[];
  rowKey: (row: T, i: number) => string;
  rowHref?: (row: T) => string;
  onRowClick?: (row: T) => void;
  empty?: ReactNode;
  className?: string;
}) {
  const router = useRouter();
  if (rows.length === 0 && empty) return <>{empty}</>;
  const primary = columns.find((c) => c.primary) ?? columns[0];
  const rest = columns.filter((c) => c !== primary);

  const go = (row: T) => {
    if (onRowClick) return onRowClick(row);
    if (rowHref) router.push(rowHref(row));
  };
  const clickable = !!rowHref || !!onRowClick;

  return (
    <div className={cn("overflow-hidden rounded-2xl border border-border/70 bg-surface shadow-card", className)}>
      {/* Desktop / tablet table */}
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-border">
              {columns.map((c) => (
                <th
                  key={c.key}
                  className={cn(
                    "whitespace-nowrap px-5 py-3 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint",
                    c.align === "right" ? "text-right" : "text-left",
                  )}
                >
                  {c.header}
                </th>
              ))}
              {clickable && <th className="w-10" aria-hidden />}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr
                key={rowKey(row, i)}
                onClick={clickable ? () => go(row) : undefined}
                className={cn(
                  "group border-b border-border/60 transition-colors last:border-0",
                  clickable && "cursor-pointer hover:bg-surface-2",
                )}
              >
                {columns.map((c) => (
                  <td
                    key={c.key}
                    className={cn(
                      "px-5 py-3.5 align-middle text-ink",
                      c.align === "right" ? "text-right" : "text-left",
                    )}
                  >
                    {c.cell(row)}
                  </td>
                ))}
                {clickable && (
                  <td className="pr-4 text-right align-middle">
                    <ChevronRight className="ml-auto h-4 w-4 text-ink-faint transition-colors group-hover:text-rose" />
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="divide-y divide-border/60 md:hidden">
        {rows.map((row, i) => (
          <button
            key={rowKey(row, i)}
            type="button"
            onClick={clickable ? () => go(row) : undefined}
            className="flex w-full items-center gap-3 px-4 py-4 text-left transition-colors hover:bg-surface-2"
          >
            <div className="min-w-0 flex-1">
              <div className="mb-2 font-medium text-ink">{primary.cell(row)}</div>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
                {rest.map((c) => (
                  <div key={c.key} className="min-w-0">
                    <dt className="text-xxs uppercase tracking-eyebrow text-ink-faint">{c.header}</dt>
                    <dd className="mt-0.5 truncate text-sm text-ink">{c.cell(row)}</dd>
                  </div>
                ))}
              </dl>
            </div>
            {clickable && <ChevronRight className="h-4 w-4 shrink-0 text-ink-faint" />}
          </button>
        ))}
      </div>
    </div>
  );
}
