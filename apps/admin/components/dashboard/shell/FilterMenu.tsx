"use client";

import { useEffect, useRef, useState } from "react";
import { SlidersHorizontal, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { CHANNELS, SERVICES, REGIONS } from "@/lib/dashboard/mock-data";
import { FILTER_LABELS, activeFilterChips, activeFilterCount, type Filters } from "@/lib/dashboard/filters";
import { FilterSelect } from "@/components/dashboard/ui/FilterSelect";
import { useFilters } from "./FiltersProvider";

const DATE_RANGES = ["Today", "Last 7 days", "Last 30 days", "This quarter", "Year to date"] as const;

/**
 * Consolidated global-filter control. Replaces the always-visible 6-pill wall
 * with ONE "Filters" button (carrying an active-count badge) that opens a
 * grouped popover, plus an always-visible active-chip row so what's scoped stays
 * glanceable and one-click clearable.
 *
 * The FiltersProvider contract is untouched — same setFilter/clear + Region →
 * Market → City cascade, same accessible FilterSelect components, just relocated
 * into a focus-managed popover.
 */
export function FilterMenu({ className }: { className?: string }) {
  const { filters, setFilter, clear, marketOptions, cityOptions } = useFilters();
  const count = activeFilterCount(filters);
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  // Close on Escape + return focus to the trigger.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
        btnRef.current?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  // Move focus into the panel when it opens.
  useEffect(() => {
    if (open) panelRef.current?.focus();
  }, [open]);

  return (
    <div ref={rootRef} className={cn("relative", className)}>
      <button
        ref={btnRef}
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "inline-flex h-9 items-center gap-2 rounded-lg border px-3 text-sm font-medium transition-all duration-200 ease-out-quint focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40",
          count > 0
            ? "border-rose/40 bg-rose/10 text-rose hover:bg-rose/[0.14]"
            : "border-border bg-surface text-ink-muted hover:border-border-strong hover:text-ink",
        )}
      >
        <SlidersHorizontal className="h-4 w-4" />
        Filters
        {count > 0 && (
          <span className="grid h-5 min-w-[1.25rem] place-items-center rounded-full bg-rose px-1 text-xxs font-bold text-rose-contrast tnum">
            {count}
          </span>
        )}
      </button>

      {open && (
        <div
          ref={panelRef}
          role="dialog"
          aria-label="Filters"
          tabIndex={-1}
          className="lk-menu-in absolute right-0 z-50 mt-2 w-[min(20rem,calc(100vw-2rem))] rounded-2xl border border-border-strong bg-surface-raised p-4 shadow-pop focus:outline-none"
        >
          <div className="mb-3 flex items-center justify-between">
            <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Scope data</p>
            {count > 0 && (
              <button
                type="button"
                onClick={clear}
                className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xxs font-semibold text-ink-muted transition-colors hover:bg-surface-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40"
              >
                <X className="h-3 w-3" /> Clear all
              </button>
            )}
          </div>

          <FilterGroup label="Time">
            <FilterSelect label="Date" options={DATE_RANGES} value={filters.range} onChange={(v) => setFilter("range", v)} className="w-full" clearable />
          </FilterGroup>

          <FilterGroup label="Geography">
            <FilterSelect label="Region" options={REGIONS} value={filters.region} onChange={(v) => setFilter("region", v)} className="w-full" clearable />
            <FilterSelect label="Market" options={marketOptions} value={filters.market} onChange={(v) => setFilter("market", v)} className="w-full" clearable />
            <FilterSelect label="City" options={cityOptions} value={filters.city} onChange={(v) => setFilter("city", v)} className="w-full" clearable />
          </FilterGroup>

          <FilterGroup label="Scope" last>
            <FilterSelect label="Channel" options={CHANNELS} value={filters.channel} onChange={(v) => setFilter("channel", v)} className="w-full" clearable />
            <FilterSelect label="Service" options={SERVICES} value={filters.service} onChange={(v) => setFilter("service", v)} className="w-full" clearable />
          </FilterGroup>
        </div>
      )}
    </div>
  );
}

function FilterGroup({ label, children, last }: { label: string; children: React.ReactNode; last?: boolean }) {
  return (
    <div className={cn("space-y-1.5", !last && "mb-3 border-b border-border pb-3")}>
      <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">{label}</p>
      <div className="flex flex-col gap-1.5">{children}</div>
    </div>
  );
}

/**
 * Always-visible active-filter chips. Each removes its own dimension; sits under
 * the header so the current scope is glanceable without opening the popover.
 */
export function FilterChips({ className }: { className?: string }) {
  const { filters, setFilter } = useFilters();
  const chips = activeFilterChips(filters);
  if (chips.length === 0) return null;
  return (
    <div className={cn("flex flex-wrap items-center gap-1.5", className)}>
      {chips.map((c) => (
        <button
          key={c.key}
          type="button"
          onClick={() => setFilter(c.key as keyof Filters, "")}
          className="inline-flex items-center gap-1 rounded-full bg-rose/10 px-2.5 py-0.5 text-xxs font-medium text-rose transition-colors hover:bg-rose/16 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40"
        >
          <span className="text-rose/70">{FILTER_LABELS[c.key]}:</span> {c.value}
          <X className="h-3 w-3" />
        </button>
      ))}
    </div>
  );
}
