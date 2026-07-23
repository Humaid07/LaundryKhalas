/**
 * Marketing mock data for the new focused subsections (social posting, campaigns,
 * PR). Existing marketing mock (platformStats, marketingKpis, contentCalendar,
 * marketingApprovals, campaignLinks…) stays in mock-data.ts. Mock-only.
 *
 * Global-filter wiring: each row carries the OPTIONAL structured fields the global
 * filter engine understands (see lib/dashboard/filters.ts `Filterable`). Geo is
 * expressed as `city`/`market` (region auto-derives); a specific service as
 * `service`; a scheduled date as `datetime`. Brand-wide / non-geo campaigns are
 * tagged `scope: "global"` so they bypass geo dims (city/market/region) but still
 * respect date/service/channel. `channel` is only set to a value the GLOBAL
 * Channel filter uses (CHANNELS: WhatsApp/Website/App/Walk-in/B2B) — social
 * PLATFORM (Instagram/TikTok/…) is a marketing-specific axis kept in `platform`
 * and filtered LOCALLY, never forced into the global Channel dimension.
 */
import type { Tone, MarketingApproval } from "./types";
import type { Filterable } from "./filters";
import { marketingApprovals } from "./mock-data";

/* Local (marketing-specific) filter option lists — deterministic, mock. */
export const SOCIAL_PLATFORMS = ["Instagram", "TikTok", "Facebook", "LinkedIn"] as const;
export const SOCIAL_DRAFT_STATUSES = ["Draft", "Awaiting Approval", "Scheduled"] as const;
export const CAMPAIGN_STATUSES = ["Active", "Scheduled", "Paused", "Ended"] as const;
export const PR_STATUSES = ["Draft", "Ready to Send", "Held"] as const;

export interface SocialDraft extends Filterable {
  id: string;
  title: string;
  platform: string;
  type: "Image" | "Carousel" | "Reel" | "Story" | "Video";
  scheduledFor: string;
  status: "Draft" | "Awaiting Approval" | "Scheduled";
}

export const socialDrafts: SocialDraft[] = [
  // Brand-wide Eid push promoting Premium Wash & Fold — bypasses geo, still date/service-filterable.
  { id: "SP-01", title: "Eid fresh linen — before/after reel", platform: "Instagram", type: "Reel", scheduledFor: "2026-07-22 18:00", status: "Awaiting Approval", service: "Premium Wash & Fold", scope: "global", datetime: "2026-07-22 18:00" },
  // Dubai-Marina hyperlocal Premium Wash & Fold post.
  { id: "SP-02", title: "Premium Wash & Fold in Dubai Marina", platform: "TikTok", type: "Video", scheduledFor: "2026-07-23 12:00", status: "Awaiting Approval", city: "Dubai", service: "Premium Wash & Fold", datetime: "2026-07-23 12:00" },
  { id: "SP-03", title: "5 duvet-care tips carousel", platform: "Instagram", type: "Carousel", scheduledFor: "2026-07-24 10:00", status: "Draft", service: "Luxe Bed & Bath Care", scope: "global", datetime: "2026-07-24 10:00" },
  { id: "SP-04", title: "Same-day delivery highlight", platform: "Facebook", type: "Image", scheduledFor: "2026-07-24 16:00", status: "Scheduled", scope: "global", datetime: "2026-07-24 16:00" },
  // B2B post → genuinely maps to the global B2B channel.
  { id: "SP-05", title: "B2B laundry for hotels", platform: "LinkedIn", type: "Image", scheduledFor: "2026-07-25 09:00", status: "Draft", channel: "B2B", service: "Premium Wash & Fold", scope: "global", datetime: "2026-07-25 09:00" },
  { id: "SP-06", title: "Customer review spotlight", platform: "Instagram", type: "Story", scheduledFor: "2026-07-25 20:00", status: "Awaiting Approval", scope: "global", datetime: "2026-07-25 20:00" },
];

export const socialDraftStatusTone: Record<SocialDraft["status"], Tone> = {
  Draft: "neutral",
  "Awaiting Approval": "rose",
  Scheduled: "info",
};

export interface Campaign extends Filterable {
  id: string;
  name: string;
  /** Display grouping of ad platforms (e.g. "Instagram + TikTok"). NOT the global
   * Channel dimension — campaigns are excluded from global Channel matching. */
  channel: string;
  status: "Active" | "Scheduled" | "Paused" | "Ended";
  spend: number;
  reach: number;
  leads: number;
  roas: string;
}

export const campaigns: Campaign[] = [
  { id: "CMP-101", name: "Eid Fresh Linen", channel: "Instagram + TikTok", status: "Active", spend: 12400, reach: 184000, leads: 312, roas: "3.4x", service: "Premium Wash & Fold", scope: "global" },
  { id: "CMP-102", name: "Dubai Marina Hyperlocal", channel: "Google + Meta", status: "Active", spend: 8600, reach: 96000, leads: 188, roas: "2.9x", city: "Dubai" },
  { id: "CMP-103", name: "B2B Hotel Laundry", channel: "LinkedIn", status: "Scheduled", spend: 0, reach: 0, leads: 0, roas: "—", service: "Premium Wash & Fold", scope: "global" },
  { id: "CMP-104", name: "Same-Day Delivery Push", channel: "TikTok", status: "Active", spend: 5200, reach: 71000, leads: 141, roas: "3.1x", scope: "global" },
  { id: "CMP-105", name: "Ramadan Retention", channel: "Email + WhatsApp", status: "Paused", spend: 2100, reach: 24000, leads: 63, roas: "4.0x", scope: "global" },
];

export const campaignStatusTone: Record<Campaign["status"], Tone> = {
  Active: "success",
  Scheduled: "info",
  Paused: "warning",
  Ended: "neutral",
};

export interface PrItem extends Filterable {
  outlet: string;
  type: "PR Draft" | "Outreach Draft";
  topic: string;
  status: "Draft" | "Ready to Send" | "Held";
}

export const prItems: PrItem[] = [
  // Qatar market-expansion story → market-tagged (region auto-derives to GCC).
  { outlet: "Gulf News", type: "PR Draft", topic: "LaundryKhalas expands to Qatar", status: "Draft", market: "Qatar" },
  { outlet: "Khaleej Times", type: "PR Draft", topic: "AI-first laundry operations", status: "Held", scope: "global" },
  { outlet: "Hospitality partners list", type: "Outreach Draft", topic: "B2B laundry partnership intro", status: "Ready to Send", channel: "B2B", service: "Premium Wash & Fold", scope: "global" },
  { outlet: "Property managers list", type: "Outreach Draft", topic: "Building/community laundry program", status: "Draft", channel: "B2B", service: "Premium Wash & Fold", scope: "global" },
];

/* -------------------------------------------------------------------------- */
/* Pure getters + url-safe helpers for the click-through detail pages.        */
/* Data shapes above are unchanged — these only READ existing mock records.   */
/* -------------------------------------------------------------------------- */

/** URL-safe href for a campaign detail page (ids are already slug-safe). */
export const campaignHref = (id: string, tab?: string): string =>
  `/marketing/campaigns/${encodeURIComponent(id)}${tab ? `?tab=${encodeURIComponent(tab)}` : ""}`;

/** URL-safe href for a marketing approval detail page. */
export const approvalHref = (id: string): string =>
  `/marketing/approvals/${encodeURIComponent(id)}`;

/** Look up a single campaign by id for its detail page. */
export const getCampaign = (id: string): Campaign | undefined =>
  campaigns.find((c) => c.id === id);

/** Ordered lifecycle used to render campaign progress on the detail page. */
export const CAMPAIGN_LIFECYCLE: Campaign["status"][] = ["Scheduled", "Active", "Paused", "Ended"];

/** Cost-per-lead derived from spend/leads (mock, display-only). */
export const campaignCpl = (c: Campaign): string =>
  c.leads > 0 ? `AED ${Math.round(c.spend / c.leads)}` : "—";

/** Look up a single marketing approval by id for its detail page. */
export const getMarketingApproval = (id: string): MarketingApproval | undefined =>
  marketingApprovals.find((m) => m.id === id);
