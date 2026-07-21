"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import {
  EMPTY_FILTERS,
  MARKET_REGION,
  marketOptionsForRegion,
  cityOptionsFor,
  type Filters,
} from "@/lib/dashboard/filters";
import { MARKETS, CITIES } from "@/lib/dashboard/mock-data";

interface FiltersContextValue {
  filters: Filters;
  setFilter: (key: keyof Filters, value: string) => void;
  clearFilter: (key: keyof Filters) => void;
  clearAll: () => void;
  /** Back-compat alias for clearAll. */
  clear: () => void;
  /** Market options cascaded from the selected region. */
  marketOptions: readonly string[];
  /** City options cascaded from the selected market/region. */
  cityOptions: readonly string[];
}

const FiltersContext = createContext<FiltersContextValue | null>(null);

/**
 * In-memory global filter store. Lives in the dashboard layout so a selection
 * persists as you move between sections AND into subsection pages, and updates
 * every consuming view instantly. (Not URL-synced — filters reset on a hard
 * reload; acceptable for this mock. URL sync is a documented next step.)
 */
export function FiltersProvider({ children }: { children: ReactNode }) {
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);

  const value = useMemo<FiltersContextValue>(() => {
    const clearAll = () => setFilters(EMPTY_FILTERS);
    return {
      filters,
      setFilter: (key, val) =>
        setFilters((prev) => {
          const next = { ...prev, [key]: val };
          // Geo dependency resets: coarser choice wins cleanly.
          // Region change clears an incompatible market/city.
          if (key === "region") {
            const markets = marketOptionsForRegion(val, MARKETS);
            if (next.market && !markets.includes(next.market)) next.market = "";
            if (next.city) {
              const cities = cityOptionsFor(next.market, val, CITIES);
              if (!cities.includes(next.city)) next.city = "";
            }
          }
          // Market change clears a now-inconsistent city.
          if (key === "market") {
            const cities = cityOptionsFor(val, next.region, CITIES);
            if (next.city && !cities.includes(next.city)) next.city = "";
          }
          return next;
        }),
      clearFilter: (key) => setFilters((prev) => ({ ...prev, [key]: "" })),
      clearAll,
      clear: clearAll,
      marketOptions: marketOptionsForRegion(filters.region, MARKETS),
      cityOptions: cityOptionsFor(filters.market, filters.region, CITIES),
    };
  }, [filters]);

  return <FiltersContext.Provider value={value}>{children}</FiltersContext.Provider>;
}

export function useFilters(): FiltersContextValue {
  const ctx = useContext(FiltersContext);
  if (!ctx) throw new Error("useFilters must be used within FiltersProvider");
  return ctx;
}

export { MARKET_REGION };
