import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export type Column<T> = {
  key: string;
  header: string;
  cell: (row: T) => ReactNode;
  align?: "left" | "right" | "center";
  /** Used as the card title on mobile. */
  primary?: boolean;
  className?: string;
};

/**
 * Responsive table. Desktop: a clean, compact table (horizontal-scroll if
 * needed). Mobile (< md): each row becomes a labeled card so nothing overflows.
 */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  onRowLabel,
  empty,
  className,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T, i: number) => string;
  /** Optional right-aligned action rendered per mobile card header. */
  onRowLabel?: (row: T) => ReactNode;
  empty?: ReactNode;
  className?: string;
}) {
  if (rows.length === 0 && empty) return <>{empty}</>;
  const primary = columns.find((c) => c.primary) ?? columns[0];
  const rest = columns.filter((c) => c !== primary);

  return (
    <div className={className}>
      {/* Desktop / tablet table */}
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-border">
              {columns.map((c) => (
                <th
                  key={c.key}
                  className={cn(
                    "whitespace-nowrap px-3 py-2.5 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint",
                    c.align === "right" && "text-right",
                    c.align === "center" && "text-center",
                    !c.align && "text-left",
                  )}
                >
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr
                key={rowKey(row, i)}
                className="border-b border-border/70 transition-colors last:border-0 hover:bg-surface-2"
              >
                {columns.map((c) => (
                  <td
                    key={c.key}
                    className={cn(
                      "px-3 py-3 align-middle text-ink",
                      c.align === "right" && "text-right",
                      c.align === "center" && "text-center",
                      c.className,
                    )}
                  >
                    {c.cell(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="space-y-3 md:hidden">
        {rows.map((row, i) => (
          <div key={rowKey(row, i)} className="rounded-xl border border-border bg-surface-2 p-4">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div className="min-w-0 font-medium text-ink">{primary.cell(row)}</div>
              {onRowLabel?.(row)}
            </div>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
              {rest.map((c) => (
                <div key={c.key} className="min-w-0">
                  <dt className="text-xxs uppercase tracking-eyebrow text-ink-faint">{c.header}</dt>
                  <dd className="mt-0.5 truncate text-sm text-ink">{c.cell(row)}</dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </div>
  );
}
