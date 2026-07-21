/**
 * SEO mock data for the new focused subsections (indexing queue, hyperlocal
 * pages, technical SEO, competitors, AI search). Core SEO mock (seoKpis,
 * seoAgents, gscPerformance, contentPipeline, seoTasks, seoBrief) stays in
 * mock-data.ts.
 *
 * Mock-only. SEO is a mix of geo-specific and site-wide data: market/city
 * pages carry structured geo fields (`city`/`market`) so the global geo
 * filters slice them, while truly site-wide rows (domain-wide crawl health,
 * sitewide meta issues, PR/backlink signals) are tagged `scope: "global"` so
 * geo filters do NOT hide them.
 */
import type { Tone, TimeSeriesPoint } from "./types";

/* --------------------------------- GSC pages -------------------------------- */

export interface GscPage {
  page: string;
  clicks: number;
  impressions: number;
  ctr: number;
  position: number;
  delta: number;
  /** City the landing page targets (derived from the URL). */
  city: string;
}

export const gscPages: GscPage[] = [
  { page: "/laundry-service-dubai-marina", clicks: 412, impressions: 9800, ctr: 4.2, position: 3.1, delta: -4, city: "Dubai" },
  { page: "/dry-cleaning-abu-dhabi", clicks: 318, impressions: 7200, ctr: 4.4, position: 2.6, delta: 2, city: "Abu Dhabi" },
  { page: "/wash-and-fold-doha", clicks: 265, impressions: 6100, ctr: 4.3, position: 4.0, delta: 1, city: "Doha" },
  { page: "/curtain-cleaning-sharjah", clicks: 148, impressions: 5200, ctr: 2.8, position: 6.2, delta: -1, city: "Sharjah" },
  { page: "/business-laundry-riyadh", clicks: 121, impressions: 4400, ctr: 2.7, position: 7.1, delta: 3, city: "Riyadh" },
];

/* --------------------------------- Indexing --------------------------------- */

export interface IndexRow {
  url: string;
  state: "Indexed" | "Submitted" | "Crawled — not indexed" | "Failed";
  lastChecked: string;
  action: string;
  /** City the URL belongs to (derived from the area in the slug). */
  city: string;
}

export const indexingQueue: IndexRow[] = [
  { url: "/dry-cleaning-al-nahda-sharjah", state: "Submitted", lastChecked: "2026-07-20", action: "Awaiting Google", city: "Sharjah" },
  { url: "/laundry-jumeirah-village", state: "Crawled — not indexed", lastChecked: "2026-07-19", action: "Improve content depth", city: "Dubai" },
  { url: "/duvet-cleaning-al-rayyan", state: "Failed", lastChecked: "2026-07-19", action: "Resubmit for indexing", city: "Doha" },
  { url: "/ironing-service-olaya", state: "Indexed", lastChecked: "2026-07-18", action: "—", city: "Riyadh" },
  { url: "/business-laundry-west-bay", state: "Submitted", lastChecked: "2026-07-20", action: "Awaiting Google", city: "Doha" },
];

export const indexStateTone: Record<IndexRow["state"], Tone> = {
  Indexed: "success",
  Submitted: "info",
  "Crawled — not indexed": "warning",
  Failed: "danger",
};

/* ------------------------------ Hyperlocal pages ---------------------------- */

export interface HyperlocalPage {
  area: string;
  city: string;
  status: "Published" | "Draft" | "Awaiting Approval" | "Duplicate Risk";
  wordCount: number;
  duplicateScore: number;
}

export const hyperlocalPages: HyperlocalPage[] = [
  { area: "Dubai Marina", city: "Dubai", status: "Published", wordCount: 940, duplicateScore: 4 },
  { area: "Al Nahda", city: "Sharjah", status: "Awaiting Approval", wordCount: 820, duplicateScore: 8 },
  { area: "West Bay", city: "Doha", status: "Draft", wordCount: 610, duplicateScore: 12 },
  { area: "Jumeirah Village", city: "Dubai", status: "Duplicate Risk", wordCount: 540, duplicateScore: 41 },
  { area: "Olaya", city: "Riyadh", status: "Published", wordCount: 880, duplicateScore: 6 },
];

export const hyperlocalStatusTone: Record<HyperlocalPage["status"], Tone> = {
  Published: "success",
  Draft: "neutral",
  "Awaiting Approval": "rose",
  "Duplicate Risk": "danger",
};

/* -------------------------------- Technical SEO ----------------------------- */

export interface TechSeoIssue {
  issue: string;
  type: "Crawl" | "Cannibalization" | "Decay" | "Internal Linking";
  affected: number;
  severity: "High" | "Medium" | "Low";
  status: "Open" | "Monitoring" | "Resolved";
  /** City for a market-specific issue; site-wide issues use `scope`. */
  city?: string;
  /** `"global"` = domain-wide issue, bypasses geo filters. */
  scope?: "global";
}

export const techSeoIssues: TechSeoIssue[] = [
  { issue: "Two pages target 'laundry dubai marina'", type: "Cannibalization", affected: 2, severity: "High", status: "Open", city: "Dubai" },
  { issue: "5 pages losing impressions 3 weeks running", type: "Decay", affected: 5, severity: "Medium", status: "Monitoring", scope: "global" },
  { issue: "Orphan pages with no internal links", type: "Internal Linking", affected: 7, severity: "Medium", status: "Open", scope: "global" },
  { issue: "Soft 404 on 3 old area pages", type: "Crawl", affected: 3, severity: "Low", status: "Open", scope: "global" },
  { issue: "Duplicate meta descriptions", type: "Crawl", affected: 9, severity: "Low", status: "Monitoring", scope: "global" },
];

export const techSeoSeverityTone: Record<TechSeoIssue["severity"], Tone> = {
  High: "danger",
  Medium: "warning",
  Low: "info",
};

/* --------------------------------- Competitors ------------------------------ */

export interface Competitor {
  name: string;
  change: string;
  movement: "up" | "down" | "flat";
  detail: string;
  /** City for a market-specific movement; domain-wide signals use `scope`. */
  city?: string;
  /** `"global"` = domain-wide signal (e.g. backlinks/PR), bypasses geo. */
  scope?: "global";
}

export const competitors: Competitor[] = [
  { name: "washmen.com", change: "+3 positions", movement: "up", detail: "Refreshed Dubai Marina landing page", city: "Dubai" },
  { name: "justclean.com", change: "New page", movement: "flat", detail: "Published Doha hyperlocal cluster", city: "Doha" },
  { name: "laundryheap.ae", change: "−2 positions", movement: "down", detail: "Lost featured snippet on 'dry cleaning dubai'", city: "Dubai" },
  { name: "cleanly.ae", change: "+12 backlinks", movement: "up", detail: "PR mention in Gulf News", scope: "global" },
];

/* --------------------------------- AI search -------------------------------- */

export interface AiSearchRow {
  query: string;
  presence: "Cited" | "Mentioned" | "Absent";
  engine: string;
  opportunity: string;
  /** City the query targets, when city-specific. */
  city?: string;
  /** Market the query targets, when market- but not city-specific. */
  market?: string;
}

export const aiSearch: AiSearchRow[] = [
  { query: "best laundry service in Dubai", presence: "Mentioned", engine: "AI Overviews", opportunity: "Add FAQ schema", city: "Dubai" },
  { query: "same day dry cleaning Dubai", presence: "Absent", engine: "AI Overviews", opportunity: "Create comparison content", city: "Dubai" },
  { query: "how much does wash and fold cost UAE", presence: "Cited", engine: "Perplexity", opportunity: "Keep pricing table fresh", market: "UAE" },
  { query: "laundry pickup and delivery Doha", presence: "Absent", engine: "AI Overviews", opportunity: "Build Doha service page", city: "Doha" },
];

export const aiPresenceTone: Record<AiSearchRow["presence"], Tone> = {
  Cited: "success",
  Mentioned: "info",
  Absent: "warning",
};

/* ----------------------------------- Charts --------------------------------- */

export const pagesGainingLosing: TimeSeriesPoint[] = [
  { label: "Gaining", value: 34 },
  { label: "Stable", value: 61 },
  { label: "Losing", value: 12 },
];
