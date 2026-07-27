"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

export type DateRange = "today" | "week" | "month" | "custom";

const PRESETS: { id: DateRange; label: string }[] = [
  { id: "today", label: "Today" },
  { id: "week", label: "This Week" },
  { id: "month", label: "This Month" },
  { id: "custom", label: "Custom" },
];

/**
 * DateRangeFilter — a sticky, horizontally-scrollable pill row for choosing the
 * active date window. When "Custom" is selected, two native date inputs appear
 * (they collapse cleanly on mobile). Controlled by the parent.
 */
export function DateRangeFilter({
  value,
  onChange,
  from,
  to,
  onCustomChange,
  className,
}: {
  value: DateRange;
  onChange: (r: DateRange) => void;
  from?: string;
  to?: string;
  onCustomChange?: (from: string, to: string) => void;
  className?: string;
}) {
  const [localFrom, setLocalFrom] = useState(from ?? "");
  const [localTo, setLocalTo] = useState(to ?? "");

  return (
    <div className={cn("space-y-3", className)}>
      <div className="overflow-x-auto">
        <div className="inline-flex min-w-max gap-1 rounded-xl border border-border bg-surface-2 p-1">
          {PRESETS.map((p) => {
            const on = p.id === value;
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => onChange(p.id)}
                aria-pressed={on}
                className={cn(
                  "whitespace-nowrap rounded-lg px-3.5 py-2 text-sm font-semibold transition-all duration-200",
                  on ? "bg-surface text-rose shadow-card" : "text-ink-muted hover:text-ink",
                )}
              >
                {p.label}
              </button>
            );
          })}
        </div>
      </div>

      {value === "custom" && (
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <label className="flex flex-1 items-center gap-2 text-xs text-ink-muted">
            <span className="shrink-0">From</span>
            <input
              type="date"
              value={localFrom}
              onChange={(e) => {
                setLocalFrom(e.target.value);
                onCustomChange?.(e.target.value, localTo);
              }}
              className="h-10 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink focus:border-rose focus-visible:outline-none"
            />
          </label>
          <label className="flex flex-1 items-center gap-2 text-xs text-ink-muted">
            <span className="shrink-0">To</span>
            <input
              type="date"
              value={localTo}
              onChange={(e) => {
                setLocalTo(e.target.value);
                onCustomChange?.(localFrom, e.target.value);
              }}
              className="h-10 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink focus:border-rose focus-visible:outline-none"
            />
          </label>
        </div>
      )}
    </div>
  );
}
