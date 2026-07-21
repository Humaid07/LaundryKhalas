/**
 * Global filter engine (mock data). Pure functions — no React here.
 *
 * Design: filters are applied over *structured fields* on each row (never by
 * parsing display text). The geo hierarchy is Region → Market/Country → City,
 * with the continental region model (GCC / MENA / Asia / Europe / Americas).
 *
 * Every dimension **passes through** a row that does not carry that field, so a
 * global filter never wrongly empties a section that doesn't have the dimension
 * (e.g. Channel does not apply to a driver row). Rows explicitly tagged
 * `scope: "global"` bypass all geo dimensions (site-wide SEO/technical items).
 *
 * See docs/architecture/dashboard-filter-system.md.
 */
import type { Order, Conversation, Ticket } from "./types";
import type { FacilityOrder, Facility, Followup, Driver, PaymentRecord } from "./operations-data";

export interface Filters {
  range: string;
  region: string;
  market: string;
  country: string;
  city: string;
  channel: string;
  service: string;
  status: string;
  owner: string;
}

export const EMPTY_FILTERS: Filters = {
  range: "",
  region: "",
  market: "",
  country: "",
  city: "",
  channel: "",
  service: "",
  status: "",
  owner: "",
};

export const FILTER_LABELS: Record<keyof Filters, string> = {
  range: "Date",
  region: "Region",
  market: "Market",
  country: "Country",
  city: "City",
  channel: "Channel",
  service: "Service",
  status: "Status",
  owner: "Owner",
};

/** A range value that means "no narrowing". */
const OPEN_RANGES = new Set(["", "Last 30 days", "This quarter", "Year to date"]);

/* --------------------------------- Geo model -------------------------------- */

/** Continental regions — the single global Region taxonomy. */
export const CONTINENTAL_REGIONS = ["GCC", "MENA", "Asia", "Europe", "Americas"] as const;

/** Operating market → region. All six GCC markets roll up to GCC. */
export const MARKET_REGION: Record<string, string> = {
  UAE: "GCC",
  Qatar: "GCC",
  "Saudi Arabia": "GCC",
  Kuwait: "GCC",
  Bahrain: "GCC",
  Oman: "GCC",
};

/** Region → the operating markets inside it (used to cascade Market options). */
export const REGION_MARKETS: Record<string, string[]> = {
  GCC: ["UAE", "Qatar", "Saudi Arabia", "Kuwait", "Bahrain", "Oman"],
  MENA: [],
  Asia: [],
  Europe: [],
  Americas: [],
};

export const MARKET_CITIES: Record<string, string[]> = {
  UAE: ["Dubai", "Abu Dhabi", "Sharjah"],
  Qatar: ["Doha"],
  "Saudi Arabia": ["Riyadh"],
  Kuwait: ["Kuwait City"],
  Bahrain: ["Manama"],
  Oman: ["Muscat"],
};

export const CITY_MARKET: Record<string, string> = {
  Dubai: "UAE",
  "Abu Dhabi": "UAE",
  Sharjah: "UAE",
  Doha: "Qatar",
  Riyadh: "Saudi Arabia",
  "Kuwait City": "Kuwait",
  Manama: "Bahrain",
  Muscat: "Oman",
};

/** Country → operating market (only where the country IS an operating market). */
export const COUNTRY_MARKET: Record<string, string> = {
  "United Arab Emirates": "UAE",
  UAE: "UAE",
  Qatar: "Qatar",
  "Saudi Arabia": "Saudi Arabia",
  Kuwait: "Kuwait",
  Bahrain: "Bahrain",
  Oman: "Oman",
};

const TODAY = "2026-07-20";

/* ------------------------------ Generic row shape --------------------------- */

/**
 * The optional structured fields the engine understands. A section's row type
 * only needs the subset it actually has; missing fields pass through.
 */
export interface Filterable {
  region?: string;
  market?: string;
  country?: string;
  city?: string;
  area?: string; // "City · District"
  channel?: string;
  service?: string;
  status?: string;
  owner?: string;
  createdAt?: string;
  date?: string;
  datetime?: string;
  scope?: "global" | "geo";
  // Rows may also carry a domain-specific date field (lastContact, expiry,
  // queuedAt, timestamp, …). `rowDate` reads those via DATE_KEYS with a runtime
  // cast, so a row never needs to be renamed to `createdAt` to become
  // date-filterable — and Filterable needs no index signature (which would
  // otherwise break the `<T extends Filterable>` constraint for concrete rows).
}

/**
 * Date-ish field names the engine understands, in priority order. Rows across
 * sections timestamp their primary event under many names; the Date-range filter
 * reads the first present so it works everywhere without display-text parsing.
 */
const DATE_KEYS = [
  "createdAt",
  "date",
  "datetime",
  "requestedAt",
  "raisedAt",
  "reportedAt",
  "queuedAt",
  "lastContact",
  "lastUpdate",
  "lastGenerated",
  "scheduledFor",
  "timestamp",
  "expiry",
  "dueDate",
  "due",
] as const;

/** City implied by an `area` string like "Dubai · Marina". */
export function facilityCity(area: string): string {
  return (area ?? "").split("·")[0].trim();
}

function rowCity(r: Filterable): string | undefined {
  if (r.city) return r.city;
  if (r.area) return facilityCity(r.area);
  return undefined;
}

function rowMarket(r: Filterable): string | undefined {
  if (r.market) return r.market;
  const c = rowCity(r);
  if (c && CITY_MARKET[c]) return CITY_MARKET[c];
  if (r.country && COUNTRY_MARKET[r.country]) return COUNTRY_MARKET[r.country];
  return undefined;
}

function rowRegion(r: Filterable): string | undefined {
  if (r.region) return r.region;
  const m = rowMarket(r);
  return m ? MARKET_REGION[m] : undefined;
}

function rowDate(r: Filterable): string | undefined {
  for (const k of DATE_KEYS) {
    const v = (r as Record<string, unknown>)[k];
    if (typeof v === "string" && v && v !== "—") return v;
  }
  return undefined;
}

/* --------------------------------- Matchers --------------------------------- */

export function matchesDateRange(iso: string | undefined, range: string): boolean {
  if (OPEN_RANGES.has(range) || !iso || iso === "—") return true;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return true;
  if (range === "Today") return d.toISOString().slice(0, 10) === TODAY;
  if (range === "Last 7 days") {
    const now = new Date(`${TODAY}T23:59:59Z`).getTime();
    return now - d.getTime() <= 7 * 86_400_000;
  }
  return true;
}

/** Back-compat alias used by existing typed helpers. */
export const withinRange = matchesDateRange;

export function matchesRegion(r: Filterable, region: string): boolean {
  if (!region) return true;
  if (r.scope === "global") return true;
  const rr = rowRegion(r);
  return rr === undefined ? !hasGeo(r) : rr === region;
}

export function matchesMarket(r: Filterable, market: string): boolean {
  if (!market) return true;
  if (r.scope === "global") return true;
  const rm = rowMarket(r);
  return rm === undefined ? !hasGeo(r) : rm === market;
}

export function matchesCountry(r: Filterable, country: string): boolean {
  if (!country) return true;
  if (r.scope === "global") return true;
  if (r.country) return r.country === country;
  const rm = rowMarket(r);
  return rm === undefined ? !hasGeo(r) : COUNTRY_MARKET[country] === rm;
}

export function matchesCity(r: Filterable, city: string): boolean {
  if (!city) return true;
  if (r.scope === "global") return true;
  const rc = rowCity(r);
  return rc === undefined ? !hasGeo(r) : rc === city;
}

export function matchesChannel(r: Filterable, channel: string): boolean {
  if (!channel) return true;
  if (r.channel === undefined) return true; // dimension not applicable → pass through
  return r.channel === channel;
}

export function matchesService(r: Filterable, service: string): boolean {
  if (!service) return true;
  if (r.service === undefined) return true;
  return r.service === service;
}

export function matchesStatus(r: Filterable, status: string): boolean {
  if (!status) return true;
  if (r.status === undefined) return true;
  return r.status === status;
}

export function matchesOwner(r: Filterable, owner: string): boolean {
  if (!owner) return true;
  if (r.owner === undefined) return true;
  return r.owner === owner;
}

/** True if the row carries *any* geo signal (so absence can pass through). */
function hasGeo(r: Filterable): boolean {
  return Boolean(r.region || r.market || r.country || r.city || r.area);
}

/* ----------------------------- Apply all filters ---------------------------- */

/**
 * The one entry point every section uses. Applies all active global filters to a
 * list of structured rows; rows missing a dimension pass through for it.
 */
export function applyGlobalFilters<T extends Filterable>(rows: T[], f: Filters): T[] {
  return rows.filter(
    (r) =>
      matchesDateRange(rowDate(r), f.range) &&
      matchesRegion(r, f.region) &&
      matchesMarket(r, f.market) &&
      matchesCountry(r, f.country) &&
      matchesCity(r, f.city) &&
      matchesChannel(r, f.channel) &&
      matchesService(r, f.service) &&
      matchesStatus(r, f.status) &&
      matchesOwner(r, f.owner),
  );
}

/** Filter a named subset (category) of rows — convenience for pages. */
export function filterCategoryRows<T extends Filterable>(rows: T[], f: Filters): T[] {
  return applyGlobalFilters(rows, f);
}

export interface FilteredSummary {
  total: number;
  shown: number;
  hidden: number;
  isFiltered: boolean;
}

export function getFilteredSummary<T extends Filterable>(rows: T[], f: Filters): FilteredSummary {
  const shown = applyGlobalFilters(rows, f).length;
  return { total: rows.length, shown, hidden: rows.length - shown, isFiltered: activeFilterCount(f) > 0 };
}

/** Distinct structured values present in a dataset (build local option lists). */
export function getAvailableFilterOptions<T extends Filterable>(rows: T[]) {
  const uniq = (vals: (string | undefined)[]) =>
    Array.from(new Set(vals.filter((v): v is string => Boolean(v && v !== "—")))).sort();
  return {
    regions: uniq(rows.map(rowRegion)),
    markets: uniq(rows.map(rowMarket)),
    cities: uniq(rows.map(rowCity)),
    channels: uniq(rows.map((r) => r.channel)),
    services: uniq(rows.map((r) => r.service)),
    statuses: uniq(rows.map((r) => r.status)),
    owners: uniq(rows.map((r) => r.owner)),
  };
}

/* ------------------------------ Cascade options ----------------------------- */

/** Market dropdown options given the selected region (falls back to all). */
export function marketOptionsForRegion(region: string, allMarkets: readonly string[]): readonly string[] {
  if (!region) return allMarkets;
  const scoped = REGION_MARKETS[region];
  return scoped && scoped.length ? scoped : allMarkets;
}

/** City dropdown options given the selected market/region (falls back to all). */
export function cityOptionsFor(market: string, region: string, allCities: readonly string[]): readonly string[] {
  if (market) return MARKET_CITIES[market] ?? allCities;
  if (region) {
    const markets = REGION_MARKETS[region] ?? [];
    const cities = markets.flatMap((m) => MARKET_CITIES[m] ?? []);
    if (cities.length) return cities;
  }
  return allCities;
}

/* --------------------------------- Chips ------------------------------------ */

export function activeFilterCount(f: Filters): number {
  return Object.values(f).filter(Boolean).length;
}

export function activeFilterChips(f: Filters): { key: keyof Filters; value: string }[] {
  return (Object.keys(f) as (keyof Filters)[])
    .filter((k) => f[k])
    .map((k) => ({ key: k, value: f[k] }));
}

/** Human-readable active-filter context, e.g. "Dubai · UAE · Dry Cleaning · Today". */
export function filterContextLabel(f: Filters): string {
  const parts = [f.city, f.market, f.region, f.service, f.channel, f.range].filter(Boolean);
  return parts.length ? parts.join(" · ") : "All data";
}

/* --------------------------- Typed helpers (ops) ---------------------------- */
/* Kept for the operations views that predate the generic engine. Each is a thin
   wrapper whose behaviour equals applyGlobalFilters for that row's fields. */

export function orderMatchesFilters(o: Order | undefined, f: Filters): boolean {
  if (!o) return true; // no order to test against → don't hide
  return applyGlobalFilters([o as unknown as Filterable], f).length === 1;
}

export function filterOrders(rows: Order[], f: Filters): Order[] {
  return rows.filter((o) => orderMatchesFilters(o, f));
}

export function filterConversations(rows: Conversation[], f: Filters): Conversation[] {
  return rows.filter(
    (c) =>
      matchesCity(c, f.city) &&
      matchesMarket(c, f.market) &&
      matchesRegion(c, f.region) &&
      (!f.channel || f.channel === "WhatsApp"),
  );
}

export function filterTickets(rows: Ticket[], f: Filters): Ticket[] {
  return rows.filter(
    (t) =>
      matchesCity(t, f.city) &&
      matchesMarket(t, f.market) &&
      matchesRegion(t, f.region) &&
      (!f.channel || (t as { source?: string }).source === f.channel) &&
      matchesDateRange(t.createdAt, f.range),
  );
}

export function filterFollowups(rows: Followup[], f: Filters): Followup[] {
  return rows.filter((r) => matchesCity(r, f.city) && matchesMarket(r, f.market) && matchesRegion(r, f.region));
}

/** Cancellations/changes carry no geo of their own — resolve via the order. */
export function filterByOrderRef<T extends { orderId: string }>(
  rows: T[],
  f: Filters,
  orderIndex: Map<string, Order>,
): T[] {
  return rows.filter((r) => orderMatchesFilters(orderIndex.get(r.orderId), f));
}

export function filterFacilityOrders(rows: FacilityOrder[], f: Filters): FacilityOrder[] {
  return applyGlobalFilters(rows as unknown as (FacilityOrder & Filterable)[], {
    ...f,
    channel: "", // facility orders have no customer channel
  });
}

export function filterFacilities(rows: Facility[], f: Filters): Facility[] {
  return rows.filter((fa) => matchesCity(fa, f.city) && matchesMarket(fa, f.market) && matchesRegion(fa, f.region));
}

/** Rows exposing an `area` string like "City · District" + optional `service`. */
export function filterByArea<T extends { area: string; service?: string }>(rows: T[], f: Filters): T[] {
  return applyGlobalFilters(rows as unknown as (T & Filterable)[], { ...f, channel: "" });
}

export function filterDrivers(rows: Driver[], f: Filters): Driver[] {
  return rows.filter((d) => matchesCity(d, f.city) && matchesMarket(d, f.market) && matchesRegion(d, f.region));
}

export function filterPayments(rows: PaymentRecord[], f: Filters): PaymentRecord[] {
  return applyGlobalFilters(rows as unknown as (PaymentRecord & Filterable)[], f);
}

/** Categorical chart data: keep only the selected category (or all). */
export function filterCategory<T extends { label: string }>(rows: T[], selected: string): T[] {
  return selected ? rows.filter((r) => r.label === selected) : rows;
}
