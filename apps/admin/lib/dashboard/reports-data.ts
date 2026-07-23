/**
 * Reports mock data — one detailed entry per report subsection. Each report shows
 * a summary, key metrics, what changed, risks/blockers and next actions plus an
 * export placeholder. Mock-only.
 */
export interface ReportDetail {
  slug: string;
  cadence: string;
  audience: string;
  summary: string;
  metrics: { label: string; value: string }[];
  changed: string[];
  risks: string[];
  next: string[];
}

export const reportDetails: Record<string, ReportDetail> = {
  "daily-standup": {
    slug: "daily-standup",
    cadence: "Daily · 09:00",
    audience: "All teams",
    summary: "Cross-team daily standup — the single snapshot of what shipped, what's blocked and what needs a decision today.",
    metrics: [
      { label: "Open approvals", value: "6" },
      { label: "Urgent tickets", value: "5" },
      { label: "Failed jobs", value: "4" },
      { label: "Partner follow-ups", value: "7" },
    ],
    changed: ["18 new WhatsApp orders overnight", "1 SEO ranking drop flagged (Dubai Marina)", "2 refunds awaiting Finance approval"],
    risks: ["Sharjah facility license expired — compliance flagged", "AI Search Visibility agent degraded"],
    next: ["Approve 6 pending items", "Resubmit 3 pages for indexing", "Confirm Riyadh partner meeting"],
  },
  operations: {
    slug: "operations",
    cadence: "Daily · 20:00",
    audience: "Ops team",
    summary: "Operational health — automation rate, tickets, deliveries and SLA across customer, facility and driver surfaces.",
    metrics: [
      { label: "Automation rate", value: "76%" },
      { label: "Active tickets", value: "38" },
      { label: "Deliveries today", value: "241" },
      { label: "Delayed orders", value: "6" },
    ],
    changed: ["Automation rate up 3pts week-on-week", "Driver delayed deliveries down to 4", "12 order changes processed"],
    risks: ["6 orders delayed at facility", "3 escalated customer concerns open"],
    next: ["Reassign delayed Doha facility orders", "Follow up on curtain re-clean concern"],
  },
  sales: {
    slug: "sales",
    cadence: "Weekly · Sun",
    audience: "Sales lead",
    summary: "Revenue and growth — new customers, AOV, top markets and B2B pipeline.",
    metrics: [
      { label: "Revenue", value: "AED 612K" },
      { label: "New customers", value: "842" },
      { label: "AOV", value: "AED 176" },
      { label: "B2B share", value: "34%" },
    ],
    changed: ["Revenue +11.2% MoM", "Dubai remains top city", "B2B revenue +21.5%"],
    risks: ["Marina Residences account flagged At Risk", "Kuwait pilot conversion below target"],
    next: ["Re-engage At-Risk B2B account", "Push app-channel conversion experiment"],
  },
  "partner-acquisition": {
    slug: "partner-acquisition",
    cadence: "Weekly · Wed",
    audience: "Partnerships",
    summary: "Partner pipeline health — leads, onboarded partners and compliance review across regions.",
    metrics: [
      { label: "Partner leads", value: "184" },
      { label: "Onboarded", value: "12" },
      { label: "In compliance", value: "6" },
      { label: "Avg score", value: "72" },
    ],
    changed: ["184 leads (+12.4%)", "Kuwait City Salmiya qualified", "GCC coverage strongest"],
    risks: ["Sharjah Industrial rejected — license expired", "Americas coverage still a gap"],
    next: ["Send Al Quoz contract follow-up", "Publish Asia market intelligence report"],
  },
  seo: {
    slug: "seo",
    cadence: "Weekly · Mon",
    audience: "Growth team",
    summary: "Organic performance — ranking movement, clicks, CTR and content opportunities.",
    metrics: [
      { label: "Clicks", value: "8.4K" },
      { label: "CTR", value: "2.48%" },
      { label: "Indexed", value: "94%" },
      { label: "Pages w/ issues", value: "9" },
    ],
    changed: ["Clicks up 9.6% WoW", "Two hyperlocal pages entered top 10", "Pages with issues fell 12%"],
    risks: ["'laundry service dubai marina' dropped 4 positions", "Jumeirah Village page at duplicate risk"],
    next: ["Refresh Dubai Marina money page", "Approve Al Nahda dry-cleaning page", "Resubmit 5 pages for indexing"],
  },
  marketing: {
    slug: "marketing",
    cadence: "Weekly · Mon",
    audience: "Marketing lead",
    summary: "Brand & growth — engagement, leads and posts pending approval across channels.",
    metrics: [
      { label: "Leads", value: "1,010" },
      { label: "TikTok engagement", value: "+22.6%" },
      { label: "Posts pending", value: "3" },
      { label: "Active campaigns", value: "4" },
    ],
    changed: ["TikTok engagement +22.6%", "Eid Fresh Linen campaign live", "1,010 leads this month"],
    risks: ["4 posts awaiting approval could miss schedule", "Apollo outreach still not connected"],
    next: ["Approve 3 pending posts", "Launch B2B Hotel Laundry campaign"],
  },
  "finance-compliance": {
    slug: "finance-compliance",
    cadence: "Weekly · Fri",
    audience: "Finance + Founders",
    summary: "Financial and compliance health — revenue, margin, compliance pass rate and risk flags.",
    metrics: [
      { label: "Revenue", value: "AED 612K" },
      { label: "Net margin", value: "28.3%" },
      { label: "Compliance pass", value: "82%" },
      { label: "Audit flags", value: "7" },
    ],
    changed: ["Cost per order down to AED 126", "Duplicate payment resolved", "Compliance pass rate +2.4pts"],
    risks: ["Damage cost up 14%", "4 documents expiring soon", "2 refunds pending > 48h"],
    next: ["Approve 2 pending refunds", "Chase Doha West Bay license renewal"],
  },
  "dev-automation": {
    slug: "dev-automation",
    cadence: "Daily · 21:00",
    audience: "Platform + Ops",
    summary: "Technical health — agents live/staged, failed jobs, uptime and LLM cost.",
    metrics: [
      { label: "Agents", value: "22" },
      { label: "Failed jobs", value: "4" },
      { label: "Uptime", value: "99.94%" },
      { label: "Est. LLM cost", value: "AED 3.2K" },
    ],
    changed: ["Avg API latency down to 142ms", "Failed jobs down to 4", "1 live agent (WhatsApp)"],
    risks: ["Orders API degraded (1.8s)", "AI visibility scan failing", "Classifier agent not built"],
    next: ["Fix Orders API list endpoint", "Add server-side approval persistence"],
  },
  "monthly-executive": {
    slug: "monthly-executive",
    cadence: "Monthly",
    audience: "Founders",
    summary: "The month in one page — revenue, margin, growth and the decisions that need founder sign-off.",
    metrics: [
      { label: "Revenue", value: "AED 612K" },
      { label: "Net margin", value: "28.3%" },
      { label: "B2B growth", value: "+21.5%" },
      { label: "Markets live", value: "3" },
    ],
    changed: ["Revenue +11.2% MoM", "12 partners onboarded", "Net margin 28.3%"],
    risks: ["Americas partner coverage gap", "Damage cost trending up"],
    next: ["Decide on Qatar expansion budget", "Approve partner hiring plan"],
  },
};

/**
 * Human-readable report titles, mirroring the subsection labels in sections.ts.
 * Kept as a small local map so reports-data stays decoupled from the icon-heavy
 * sections module.
 */
export const reportTitles: Record<string, string> = {
  "daily-standup": "Daily Standup",
  operations: "Operations Report",
  sales: "Sales Report",
  "partner-acquisition": "Partner Acquisition Report",
  seo: "SEO Report",
  marketing: "Marketing Report",
  "finance-compliance": "Finance & Compliance Report",
  "dev-automation": "Dev & Automation Report",
  "monthly-executive": "Monthly Executive",
};

/** Pure getter — look up a single report by its slug (used by the detail page). */
export function getReport(slug: string): ReportDetail | undefined {
  return reportDetails[slug];
}

/** Display title for a report slug (falls back to a generic label). */
export function getReportTitle(slug: string): string {
  return reportTitles[slug] ?? "Report";
}
