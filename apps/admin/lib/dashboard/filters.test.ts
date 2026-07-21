/**
 * Pure-function tests for the global filter engine (lib/dashboard/filters.ts).
 *
 * No test framework is configured for the admin app, so this is a tiny
 * self-contained assertion script. Run it with:
 *
 *     npx tsx lib/dashboard/filters.test.ts
 *
 * It exits non-zero on the first failed assertion. These cover the filter
 * acceptance matrix: region/market/city/channel/service/date matching, the
 * Region → Market → City cascade, dimension pass-through, global-scope bypass,
 * and empty-result behaviour. See docs/architecture/dashboard-filter-system.md.
 */
import {
  EMPTY_FILTERS,
  applyGlobalFilters,
  getFilteredSummary,
  getAvailableFilterOptions,
  marketOptionsForRegion,
  cityOptionsFor,
  matchesDateRange,
  type Filters,
  type Filterable,
} from "./filters";
import { MARKETS, CITIES } from "./mock-data";

let passed = 0;
function assert(cond: boolean, msg: string) {
  if (!cond) {
    console.error(`✗ FAIL: ${msg}`);
    process.exit(1);
  }
  passed += 1;
}
function f(over: Partial<Filters>): Filters {
  return { ...EMPTY_FILTERS, ...over };
}

/* A representative mixed dataset spanning sections + a site-wide row. */
interface Row extends Filterable {
  id: string;
}
const rows: Row[] = [
  { id: "dxb-wa-dry", city: "Dubai", channel: "WhatsApp", service: "Dry Cleaning", createdAt: "2026-07-20", status: "Active" },
  { id: "dxb-web-wash", city: "Dubai", channel: "Website", service: "Wash & Fold", createdAt: "2026-07-10" },
  { id: "auh-wa-dry", city: "Abu Dhabi", channel: "WhatsApp", service: "Dry Cleaning", createdAt: "2026-07-19" },
  { id: "doha-app-iron", market: "Qatar", channel: "App", service: "Ironing", createdAt: "2026-07-18" },
  { id: "ruh-b2b", country: "Saudi Arabia", channel: "B2B", service: "Wash & Fold", createdAt: "2026-07-01" },
  { id: "london-lead", region: "Europe", city: "London", createdAt: "2026-07-15" }, // non-GCC
  { id: "facility-marina", area: "Dubai · Marina", service: "Dry Cleaning" }, // area-derived city
  { id: "sitewide-seo", scope: "global", service: "Dry Cleaning" }, // bypasses geo
  { id: "no-geo-note" }, // carries no geo signal at all
];

/* 1. Region filter — GCC keeps the six GCC rows + pass-through rows, drops Europe. */
{
  const out = applyGlobalFilters(rows, f({ region: "GCC" }));
  const ids = out.map((r) => r.id);
  assert(!ids.includes("london-lead"), "Region=GCC drops the Europe lead");
  assert(ids.includes("dxb-wa-dry") && ids.includes("doha-app-iron") && ids.includes("ruh-b2b"), "Region=GCC keeps GCC rows");
  assert(ids.includes("sitewide-seo"), "Region=GCC keeps a scope:global row");
  assert(ids.includes("no-geo-note"), "Region=GCC passes through a row with no geo signal");
}

/* 2. Market filter — UAE keeps Dubai/Abu Dhabi/area rows, drops Qatar/KSA/Europe. */
{
  const ids = applyGlobalFilters(rows, f({ market: "UAE" })).map((r) => r.id);
  assert(ids.includes("dxb-wa-dry") && ids.includes("auh-wa-dry") && ids.includes("facility-marina"), "Market=UAE keeps UAE + area-derived rows");
  assert(!ids.includes("doha-app-iron") && !ids.includes("ruh-b2b") && !ids.includes("london-lead"), "Market=UAE drops non-UAE geo rows");
  assert(ids.includes("sitewide-seo"), "Market=UAE keeps a global-scope row");
}

/* 3. City filter — Dubai keeps only Dubai + Dubai-area + pass-through/global. */
{
  const ids = applyGlobalFilters(rows, f({ city: "Dubai" })).map((r) => r.id);
  assert(ids.includes("dxb-wa-dry") && ids.includes("dxb-web-wash") && ids.includes("facility-marina"), "City=Dubai keeps Dubai + 'Dubai · Marina' area row");
  assert(!ids.includes("auh-wa-dry") && !ids.includes("doha-app-iron"), "City=Dubai drops other cities");
  assert(ids.includes("sitewide-seo") && ids.includes("no-geo-note"), "City=Dubai keeps global + no-geo rows");
}

/* 4. Channel filter — WhatsApp keeps WhatsApp rows + rows with no channel. */
{
  const ids = applyGlobalFilters(rows, f({ channel: "WhatsApp" })).map((r) => r.id);
  assert(ids.includes("dxb-wa-dry") && ids.includes("auh-wa-dry"), "Channel=WhatsApp keeps WhatsApp rows");
  assert(!ids.includes("dxb-web-wash") && !ids.includes("doha-app-iron"), "Channel=WhatsApp drops other channels");
  assert(ids.includes("facility-marina"), "Channel filter passes through a row with no channel field");
}

/* 5. Service filter — Dry Cleaning keeps dry-cleaning rows + rows with no service. */
{
  const ids = applyGlobalFilters(rows, f({ service: "Dry Cleaning" })).map((r) => r.id);
  assert(ids.includes("dxb-wa-dry") && ids.includes("auh-wa-dry") && ids.includes("facility-marina"), "Service=Dry Cleaning keeps dry-cleaning rows");
  assert(!ids.includes("dxb-web-wash") && !ids.includes("doha-app-iron"), "Service=Dry Cleaning drops other services");
  assert(ids.includes("no-geo-note"), "Service filter passes through a row with no service field");
}

/* 6. Date filter — Today keeps only 2026-07-20; open ranges keep everything. */
{
  assert(matchesDateRange("2026-07-20", "Today"), "matchesDateRange Today = 2026-07-20 true");
  assert(!matchesDateRange("2026-07-10", "Today"), "matchesDateRange Today != 2026-07-10 false");
  assert(matchesDateRange(undefined, "Today"), "matchesDateRange passes through a row with no date");
  const ids = applyGlobalFilters(rows, f({ range: "Today" })).map((r) => r.id);
  assert(ids.includes("dxb-wa-dry"), "range=Today keeps the 2026-07-20 row");
  assert(!ids.includes("dxb-web-wash"), "range=Today drops the 2026-07-10 row");
  assert(ids.includes("facility-marina"), "range=Today passes through a row with no date");
}

/* 7. Combined filters — UAE + Dubai + WhatsApp + Dry Cleaning narrows correctly. */
{
  const ids = applyGlobalFilters(rows, f({ market: "UAE", city: "Dubai", channel: "WhatsApp", service: "Dry Cleaning" })).map((r) => r.id);
  assert(ids.includes("dxb-wa-dry"), "Combined UAE/Dubai/WhatsApp/Dry Cleaning keeps the matching row");
  assert(!ids.includes("dxb-web-wash") && !ids.includes("auh-wa-dry"), "Combined filters exclude non-matching rows");
}

/* 8. Cascade — Region → Market → City option narrowing. */
{
  const gccMarkets = marketOptionsForRegion("GCC", MARKETS);
  assert(gccMarkets.includes("UAE"), "GCC market options include UAE");
  assert(!gccMarkets.includes("United Kingdom"), "GCC market options exclude non-GCC markets");
  assert(cityOptionsFor("UAE", "GCC", CITIES).join(",") === "Dubai,Abu Dhabi,Sharjah", "Market=UAE cities = Dubai/Abu Dhabi/Sharjah");
  assert(cityOptionsFor("Qatar", "GCC", CITIES).join(",") === "Doha", "Market=Qatar cities = Doha");
}

/* 9. Empty result — a filter that matches nothing yields an empty list + summary. */
{
  const geoRows = rows.filter((r) => r.id !== "sitewide-seo" && r.id !== "no-geo-note");
  const out = applyGlobalFilters(geoRows, f({ city: "Muscat" }));
  assert(out.length === 0, "City=Muscat over UAE/Qatar/KSA/Europe rows yields empty");
  const summary = getFilteredSummary(geoRows, f({ city: "Muscat" }));
  assert(summary.shown === 0 && summary.isFiltered && summary.hidden === summary.total, "getFilteredSummary reports an empty filtered result");
}

/* 10. Available options are derived from structured fields, not display text. */
{
  const opts = getAvailableFilterOptions(rows);
  assert(opts.cities.includes("Dubai") && opts.cities.includes("Abu Dhabi"), "getAvailableFilterOptions surfaces cities");
  assert(opts.channels.includes("WhatsApp") && opts.services.includes("Dry Cleaning"), "getAvailableFilterOptions surfaces channels & services");
}

/* 11. No filters — everything passes (isFiltered false). */
{
  const out = applyGlobalFilters(rows, EMPTY_FILTERS);
  assert(out.length === rows.length, "EMPTY_FILTERS keeps every row");
  assert(!getFilteredSummary(rows, EMPTY_FILTERS).isFiltered, "EMPTY_FILTERS reports isFiltered=false");
}

/* 12. Alternate date-field names — the Date filter reads domain date fields, not
      just createdAt (rows across sections timestamp under many names). */
{
  const dated: Row[] = [
    { id: "lastContact", city: "Dubai", lastContact: "2026-07-20T09:00:00Z" } as Row,
    { id: "reportedAt", city: "Dubai", reportedAt: "2026-07-10T09:00:00Z" } as Row,
    { id: "dueDate", city: "Dubai", dueDate: "2026-07-20" } as Row,
    { id: "queuedAt", city: "Dubai", queuedAt: "2026-07-01T09:00:00Z" } as Row,
  ];
  const ids = applyGlobalFilters(dated, f({ range: "Today" })).map((r) => r.id);
  assert(ids.includes("lastContact"), "Date=Today matches a row dated via lastContact");
  assert(ids.includes("dueDate"), "Date=Today matches a row dated via dueDate (2026-07-20)");
  assert(!ids.includes("reportedAt"), "Date=Today drops a reportedAt row from 2026-07-10");
  assert(!ids.includes("queuedAt"), "Date=Today drops a queuedAt row from 2026-07-01");
}

/* 13. Newly geo-tagged operational rows filter by city (facility/driver/order
      issues, B2B invoices) — previously these rendered raw. */
{
  const opsRows: Row[] = [
    { id: "facilityIssue-doha", city: "Doha", raisedAt: "2026-07-20T06:00:00Z" } as Row,
    { id: "driverIssue-dubai", city: "Dubai", reportedAt: "2026-07-20T09:10:00Z" } as Row,
    { id: "orderIssue-sharjah", city: "Sharjah", lastUpdate: "2026-07-20T09:22:00Z" } as Row,
    { id: "invoice-doha", city: "Doha", channel: "B2B", dueDate: "2026-08-01" } as Row,
  ];
  const dubai = applyGlobalFilters(opsRows, f({ city: "Dubai" })).map((r) => r.id);
  assert(dubai.length === 1 && dubai[0] === "driverIssue-dubai", "City=Dubai keeps only the Dubai driver issue");
  const uae = applyGlobalFilters(opsRows, f({ market: "UAE" })).map((r) => r.id);
  assert(uae.includes("driverIssue-dubai") && uae.includes("orderIssue-sharjah"), "Market=UAE keeps Dubai + Sharjah ops rows");
  assert(!uae.includes("facilityIssue-doha") && !uae.includes("invoice-doha"), "Market=UAE drops Doha ops rows");
  // A B2B invoice is excluded by a non-B2B Channel filter.
  const wa = applyGlobalFilters(opsRows, f({ channel: "WhatsApp" })).map((r) => r.id);
  assert(!wa.includes("invoice-doha"), "Channel=WhatsApp drops the B2B invoice; other (channel-less) ops rows pass through");
  assert(wa.includes("facilityIssue-doha"), "Channel=WhatsApp passes through a channel-less facility issue");
}

/* 14. SEO tasks: city-tagged tasks filter by geo; scope:"global" tasks (sitewide
      linking, service/blog pages) survive any geo filter. */
{
  const tasks: Row[] = [
    { id: "task-dubai", city: "Dubai" } as Row,
    { id: "task-sharjah", city: "Sharjah" } as Row,
    { id: "task-sitewide", scope: "global" } as Row,
  ];
  const dubai = applyGlobalFilters(tasks, f({ city: "Dubai" })).map((r) => r.id);
  assert(dubai.includes("task-dubai") && dubai.includes("task-sitewide"), "City=Dubai keeps the Dubai task + the sitewide (global) task");
  assert(!dubai.includes("task-sharjah"), "City=Dubai drops the Sharjah SEO task");
}

console.log(`✓ filter engine: ${passed} assertions passed`);
