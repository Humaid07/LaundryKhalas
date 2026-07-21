"use client";

import { useMemo, useState } from "react";
import { SlidersHorizontal, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { FilterSelect } from "@/components/dashboard/ui/FilterSelect";

/**
 * Lightweight, self-contained filter bar for sections where the *global* geo
 * filters (market/city/channel) don't cleanly apply — e.g. Partner Acquisition
 * (worldwide) or Dev & Automation (technical dimensions). Local-only state,
 * mock filtering, same visual language as the global FilterBar.
 */

export type LocalFilterDef = {
  key: string;
  label: string;
  options: readonly string[];
};

export type LocalFilterValues = Record<string, string>;

export function useLocalFilters(defs: LocalFilterDef[]) {
  const empty = useMemo(() => Object.fromEntries(defs.map((d) => [d.key, ""])), [defs]);
  const [values, setValues] = useState<LocalFilterValues>(empty);
  const set = (key: string, value: string) => setValues((v) => ({ ...v, [key]: value }));
  const clear = () => setValues(empty);
  const activeCount = Object.values(values).filter(Boolean).length;
  return { values, set, clear, activeCount };
}

/** Does a row match the active local filters? `accessor` maps a filter key → row value. */
export function matchesLocal<T>(
  row: T,
  values: LocalFilterValues,
  accessor: (row: T, key: string) => string | undefined,
): boolean {
  return Object.entries(values).every(([key, val]) => !val || accessor(row, key) === val);
}

export function LocalFilterBar({
  defs,
  values,
  onChange,
  onClear,
  className,
}: {
  defs: LocalFilterDef[];
  values: LocalFilterValues;
  onChange: (key: string, value: string) => void;
  onClear: () => void;
  className?: string;
}) {
  const chips = defs.filter((d) => values[d.key]);
  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      <span className="inline-flex items-center gap-1.5 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">
        <SlidersHorizontal className="h-3.5 w-3.5" /> Filters
      </span>
      {defs.map((d) => (
        <FilterSelect key={d.key} label={d.label} options={d.options} value={values[d.key] ?? ""} onChange={(v) => onChange(d.key, v)} />
      ))}
      {chips.length > 0 && (
        <button
          type="button"
          onClick={onClear}
          className="inline-flex h-9 items-center gap-1 rounded-full border border-border px-3.5 text-xxs font-semibold text-ink-muted transition-colors hover:border-border-strong hover:bg-surface-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40"
        >
          <X className="h-3 w-3" /> Clear all
        </button>
      )}
    </div>
  );
}
