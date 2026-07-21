"use client";

import { SlidersHorizontal, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { CHANNELS, SERVICES, REGIONS } from "@/lib/dashboard/mock-data";
import { FILTER_LABELS, activeFilterChips, type Filters } from "@/lib/dashboard/filters";
import { FilterSelect } from "@/components/dashboard/ui/FilterSelect";
import { useFilters } from "./FiltersProvider";

const DATE_RANGES = ["Today", "Last 7 days", "Last 30 days", "This quarter", "Year to date"] as const;

/**
 * Global filter bar — controlled by the shared FiltersProvider. Selections
 * live-filter the data views on the current page and persist across navigation;
 * the active chips show what's scoped and clear individual filters. Market/City
 * options cascade from the selected Region → Market (Region → Market → City).
 */
export function FilterBar({ className }: { className?: string }) {
  const { filters, setFilter, clear, marketOptions, cityOptions } = useFilters();
  const chips = activeFilterChips(filters);

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1.5 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">
          <SlidersHorizontal className="h-3.5 w-3.5" /> Filters
        </span>
        <FilterSelect label="Date" options={DATE_RANGES} value={filters.range} onChange={(v) => setFilter("range", v)} />
        <FilterSelect label="Region" options={REGIONS} value={filters.region} onChange={(v) => setFilter("region", v)} />
        <FilterSelect label="Market" options={marketOptions} value={filters.market} onChange={(v) => setFilter("market", v)} />
        <FilterSelect label="City" options={cityOptions} value={filters.city} onChange={(v) => setFilter("city", v)} />
        <FilterSelect label="Channel" options={CHANNELS} value={filters.channel} onChange={(v) => setFilter("channel", v)} />
        <FilterSelect label="Service" options={SERVICES} value={filters.service} onChange={(v) => setFilter("service", v)} />
        {chips.length > 0 && (
          <button
            type="button"
            onClick={clear}
            className="inline-flex h-9 items-center gap-1 rounded-full border border-border px-3.5 text-xxs font-semibold text-ink-muted transition-colors hover:border-border-strong hover:bg-surface-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40"
          >
            <X className="h-3 w-3" /> Clear all
          </button>
        )}
      </div>

      {chips.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          {chips.map((c) => (
            <button
              key={c.key}
              type="button"
              onClick={() => setFilter(c.key as keyof Filters, "")}
              className="inline-flex items-center gap-1 rounded-full bg-rose/10 px-2.5 py-0.5 text-xxs font-medium text-rose transition-colors hover:bg-rose/16"
            >
              <span className="text-rose/70">{FILTER_LABELS[c.key]}:</span> {c.value}
              <X className="h-3 w-3" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
