import type { LucideIcon } from "lucide-react";
import {
  // operations
  Headset, Factory, Truck, ClipboardList,
  // sales
  TrendingUp, Globe2, Radio, WashingMachine, Building2, Users, Filter,
  // partner
  GitBranch, Map as MapIcon, Send, CalendarClock, ShieldCheck, Gauge, UsersRound,
  // seo
  Sparkles, Bot, Search, FileSearch, PenLine, MapPinned, Wrench, Swords, BrainCircuit, FileBarChart,
  // marketing
  LayoutGrid, BarChart3, Calendar, Wand2, Megaphone, CheckCircle2, Mail, Link2,
  // finance
  LineChart, PieChart, CreditCard, Undo2, FileClock, ScrollText, AlertTriangle,
  // dev
  Activity, Bug, ListChecks, Coins, Rocket, Plug,
  // reports
  Sun, FileText,
  // settings
  User, Shield, Bell, Palette,
} from "lucide-react";
import type { Tone } from "./types";

export type SubKpi = { label: string; value: string; tone?: Tone };

export type Subsection = {
  slug: string;
  label: string;
  description: string;
  icon: LucideIcon;
  kpis?: SubKpi[];
  status?: { label: string; tone: Tone };
  /** Optional sidebar sub-tab count badge (subsection-specific). */
  badge?: number;
};

export type SectionDef = {
  key: string;
  base: string; // e.g. "/sales"
  eyebrow: string;
  title: string;
  description: string;
  /** Landing card grid density. */
  cols?: 2 | 3 | 4;
  /**
   * Whether the section's data can be sliced by the global geo/date/channel/
   * service filters. When true (the default), the shell shows the global filter
   * bar on the landing page and every subsection page, and the section's views
   * respect the active filters. Set false only for sections whose rows are never
   * market/city-specific (e.g. Settings). See docs/architecture/dashboard-filter-system.md.
   */
  filterable?: boolean;
  subsections: Subsection[];
};

/* Each top-level section = a landing page (cards) + focused subsection routes.
 * This config is the single source of truth for landing cards AND breadcrumb
 * sub-nav. Content lives in each section's own component (a `slug` router). */
export const SECTIONS: Record<string, SectionDef> = {
  operations: {
    key: "operations",
    base: "/operations",
    eyebrow: "Operations",
    title: "Operations",
    description:
      "Your operational command center. Open a section to manage it on its own focused page.",
    cols: 2,
    subsections: [
      { slug: "customer-facing", label: "Customer Facing", icon: Headset, badge: 7, description: "WhatsApp conversations, tickets, cancellations, follow-ups and support escalations.", kpis: [{ label: "Open convos", value: "24" }, { label: "Pending", value: "8", tone: "warning" }, { label: "Urgent", value: "5", tone: "danger" }], status: { label: "Live console", tone: "success" } },
      { slug: "facility-facing", label: "Facility Facing", icon: Factory, badge: 3, description: "Facility assignment, cleaning progress, quality checks, issues and delivery handoff.", kpis: [{ label: "In cleaning", value: "18" }, { label: "QC pending", value: "6", tone: "warning" }, { label: "Delayed", value: "3", tone: "danger" }], status: { label: "Privacy on", tone: "info" } },
      { slug: "drivers", label: "Drivers", icon: Truck, badge: 12, description: "Pickup/delivery drivers, queues, delivery progress, route status and driver issues.", kpis: [{ label: "Active", value: "12", tone: "success" }, { label: "Assigned", value: "9" }, { label: "Delayed", value: "4", tone: "danger" }] },
      { slug: "customer-orders", label: "Customer Orders", icon: ClipboardList, badge: 82, description: "Every customer order from WhatsApp, website, app, B2B and manual bookings.", kpis: [{ label: "Active", value: "82", tone: "rose" }, { label: "Done today", value: "31", tone: "success" }, { label: "Changes", value: "7", tone: "warning" }] },
    ],
  },

  sales: {
    key: "sales",
    base: "/sales",
    eyebrow: "Revenue & growth",
    title: "Sales",
    description: "Revenue, growth and customer performance — split into focused views.",
    cols: 3,
    subsections: [
      { slug: "overview", label: "Sales Overview", icon: TrendingUp, description: "Revenue & order KPIs, growth summary and quick charts.", kpis: [{ label: "Revenue", value: "AED 612K", tone: "rose" }, { label: "Growth", value: "+11.2%", tone: "success" }] },
      { slug: "markets", label: "Markets", icon: Globe2, description: "Sales by market, region and city — market comparison.", kpis: [{ label: "Top market", value: "UAE" }, { label: "Markets", value: "6" }] },
      { slug: "channels", label: "Channels", icon: Radio, description: "WhatsApp, Website, App, Manual and B2B — channel conversion.", kpis: [{ label: "Top channel", value: "WhatsApp" }, { label: "Channels", value: "5" }] },
      { slug: "services", label: "Services", icon: WashingMachine, description: "Revenue and volume by service type.", kpis: [{ label: "Top service", value: "Premium Wash & Fold" }, { label: "Services", value: "8" }] },
      { slug: "b2b-b2c", label: "B2B / B2C", icon: Building2, description: "Corporate/hotel/business vs consumer sales split.", kpis: [{ label: "B2B share", value: "34%", tone: "plum" }, { label: "B2C share", value: "66%" }] },
      { slug: "top-customers", label: "Top Customers", icon: Users, description: "Repeat, high-value customers and business accounts.", kpis: [{ label: "Accounts", value: "8" }, { label: "Top AOV", value: "AED 1.6K" }] },
      { slug: "conversion-funnel", label: "Conversion Funnel", icon: Filter, description: "Leads → inquiries → bookings → completed → lost.", kpis: [{ label: "Lead→order", value: "18.5%", tone: "success" }] },
    ],
  },

  "partner-acquisition": {
    key: "partner-acquisition",
    base: "/partner-acquisition",
    eyebrow: "Business development",
    title: "Partner Acquisition",
    description: "Acquire, track, score and onboard partners across regions — focused command hub.",
    cols: 4,
    subsections: [
      { slug: "team", label: "Team & Ownership", icon: UsersRound, description: "Head of Partnership, Market Intelligence and Partner Executives.", kpis: [{ label: "Roles", value: "4" }, { label: "Meetings/wk", value: "16" }] },
      { slug: "pipeline", label: "Partner Pipeline", icon: GitBranch, description: "Lead stages, partner score, owner, next step and compliance.", kpis: [{ label: "Leads", value: "184", tone: "rose" }, { label: "Active", value: "12", tone: "success" }] },
      { slug: "market-intelligence", label: "Market Intelligence", icon: MapIcon, description: "Opportunity score, demand/supply, competitors and targets.", kpis: [{ label: "Cities", value: "8" }, { label: "Priority", value: "5", tone: "danger" }] },
      { slug: "outreach", label: "Outreach Tracker", icon: Send, description: "Outreach sent, replies, meetings and follow-ups by region.", kpis: [{ label: "Active", value: "41" }, { label: "Replies", value: "87" }] },
      { slug: "meetings", label: "Meetings & Follow-ups", icon: CalendarClock, description: "Meeting schedule, next action and owner.", kpis: [{ label: "Upcoming", value: "5", tone: "plum" }] },
      { slug: "compliance-queue", label: "Compliance Queue", icon: ShieldCheck, description: "Trade license, documents, agreement and onboarding checklist.", kpis: [{ label: "Open", value: "6", tone: "warning" }, { label: "Passed", value: "82%", tone: "success" }] },
      { slug: "regional-coverage", label: "Regional Coverage", icon: Globe2, description: "MENA, Asia, EU, Americas and GCC coverage.", kpis: [{ label: "Regions", value: "8/14" }] },
      { slug: "performance-preview", label: "Performance Preview", icon: Gauge, description: "Future partner performance once onboarded.", kpis: [{ label: "Onboarded", value: "2" }] },
    ],
  },

  "seo-agents": {
    key: "seo-agents",
    base: "/seo-agents",
    eyebrow: "Autonomous SEO",
    title: "SEO Agents",
    description: "Fleet of approval-gated SEO agents — monitoring, drafting and reporting.",
    cols: 3,
    subsections: [
      { slug: "overview", label: "SEO Overview", icon: Sparkles, description: "Daily SEO brief, key KPIs and alerts.", kpis: [{ label: "Clicks", value: "8.4K", tone: "success" }, { label: "Alerts", value: "1", tone: "danger" }] },
      { slug: "agent-fleet", label: "Agent Fleet", icon: Bot, description: "All SEO agent cards — status, last/next run and owner.", kpis: [{ label: "Agents", value: "14" }, { label: "Attention", value: "3", tone: "warning" }] },
      { slug: "gsc-performance", label: "GSC Performance", icon: Search, description: "Clicks, impressions, CTR, position and pages gaining/losing.", kpis: [{ label: "CTR", value: "2.48%" }] },
      { slug: "indexing", label: "Indexing", icon: FileSearch, description: "Indexed, submitted, failed and resubmission queue.", kpis: [{ label: "Indexed", value: "94%", tone: "success" }] },
      { slug: "content-pipeline", label: "Content Pipeline", icon: PenLine, description: "Content research, blog drafts, approvals and internal links.", kpis: [{ label: "Drafts", value: "12" }] },
      { slug: "hyperlocal-pages", label: "Hyperlocal Pages", icon: MapPinned, description: "Area pages, duplicate checks, market pages, publishing.", kpis: [{ label: "Area pages", value: "37" }] },
      { slug: "technical-seo", label: "Technical SEO", icon: Wrench, description: "Crawl issues, cannibalization, decay and linking issues.", kpis: [{ label: "Issues", value: "9", tone: "warning" }] },
      { slug: "competitors", label: "Competitors", icon: Swords, description: "Competitor changes, new pages, ranking and backlinks.", kpis: [{ label: "Tracked", value: "6" }] },
      { slug: "ai-search", label: "AI Search", icon: BrainCircuit, description: "AI visibility, answer-engine presence, structured content.", kpis: [{ label: "Visibility", value: "Degraded", tone: "warning" }] },
      { slug: "reports", label: "SEO Reports", icon: FileBarChart, description: "Daily brief, weekly report and monthly strategy.", kpis: [{ label: "Reports", value: "3" }] },
    ],
  },

  marketing: {
    key: "marketing",
    base: "/marketing",
    eyebrow: "Growth & brand",
    title: "Marketing",
    description: "Social analytics, AI creative studio and approval-gated marketing agents.",
    cols: 3,
    subsections: [
      { slug: "overview", label: "Marketing Overview", icon: LayoutGrid, description: "Key KPIs, urgent approvals and performance summary.", kpis: [{ label: "Leads", value: "1,010", tone: "success" }, { label: "Approvals", value: "3", tone: "warning" }] },
      { slug: "platform-analytics", label: "Platform Analytics", icon: BarChart3, description: "Instagram, Facebook, TikTok, LinkedIn — Metricool-style.", kpis: [{ label: "Platforms", value: "4" }] },
      { slug: "content-calendar", label: "Content Calendar", icon: Calendar, description: "Planned, scheduled posts and approval status.", kpis: [{ label: "This week", value: "9" }] },
      { slug: "creative-studio", label: "Creative Studio", icon: Wand2, description: "Image/carousel/video prompts, HeyGen & Gamma integrations.", status: { label: "Preview", tone: "info" } },
      { slug: "social-posting", label: "Social Posting", icon: Send, description: "Draft posts, channel selection — approval required.", kpis: [{ label: "Drafts", value: "6" }] },
      { slug: "campaigns", label: "Campaigns", icon: Megaphone, description: "Campaign list, channel, spend and performance.", kpis: [{ label: "Active", value: "4" }] },
      { slug: "approvals", label: "Approvals", icon: CheckCircle2, description: "Pending post, creative and copy approvals.", kpis: [{ label: "Pending", value: "3", tone: "warning" }] },
      { slug: "influencer-ugc", label: "Influencer / UGC", icon: Users, description: "Influencer leads, outreach and UGC pipeline.", kpis: [{ label: "Shortlist", value: "3" }] },
      { slug: "pr-outreach", label: "PR & Outreach", icon: Mail, description: "PR drafts, outreach drafts and publisher list.", status: { label: "Drafts only", tone: "info" } },
      { slug: "utm-tracking", label: "UTM Tracking", icon: Link2, description: "Campaign links, UTM builder and click tracking.", kpis: [{ label: "Links", value: "5" }] },
    ],
  },

  "finance-compliance": {
    key: "finance-compliance",
    base: "/finance-compliance",
    eyebrow: "Finance, compliance & risk",
    title: "Finance & Compliance",
    description: "Financial analytics combined with operational compliance and risk oversight.",
    cols: 3,
    subsections: [
      { slug: "financial-overview", label: "Financial Overview", icon: LineChart, description: "Revenue, cost, profit, margin and AOV.", kpis: [{ label: "Revenue", value: "AED 612K", tone: "rose" }, { label: "Margin", value: "28.3%", tone: "success" }] },
      { slug: "cost-breakdown", label: "Cost Breakdown", icon: PieChart, description: "Tech, AI/LLM, marketing, driver, facility, damage, refund cost.", kpis: [{ label: "Total cost", value: "AED 450K" }] },
      { slug: "customer-payments", label: "Customer Payments", icon: CreditCard, description: "Paid, pending, failed, overdue and invoiced.", kpis: [{ label: "Pending", value: "96", tone: "warning" }] },
      { slug: "refunds-adjustments", label: "Refunds & Adjustments", icon: Undo2, description: "Refund/adjustment requests, approval status and reviewer.", kpis: [{ label: "Awaiting", value: "2", tone: "rose" }] },
      { slug: "partner-facility-compliance", label: "Partner / Facility Compliance", icon: Factory, description: "Facility license, agreement, quality checklist and risk.", kpis: [{ label: "Pass rate", value: "82%", tone: "success" }] },
      { slug: "driver-compliance", label: "Driver Compliance", icon: Truck, description: "Driver documents, ID, vehicle and training status.", kpis: [{ label: "Issues", value: "5", tone: "warning" }] },
      { slug: "documents-expiry", label: "Documents & Expiry", icon: FileClock, description: "Expiring/missing documents, owner and action needed.", kpis: [{ label: "Expiring", value: "4", tone: "danger" }] },
      { slug: "audit-trail", label: "Audit Trail", icon: ScrollText, description: "Event, actor, module, timestamp and risk.", kpis: [{ label: "Events", value: "5" }] },
      { slug: "risk-flags", label: "Risk Flags", icon: AlertTriangle, description: "Duplicate payments, damage claims, expiring docs, spikes.", kpis: [{ label: "Open", value: "5", tone: "danger" }] },
    ],
  },

  "dev-automation": {
    key: "dev-automation",
    base: "/dev-automation",
    eyebrow: "Technical operations",
    title: "Dev & Automation",
    description: "Agent health, automations, API & system status — the technical command center.",
    cols: 3,
    subsections: [
      { slug: "overview", label: "Automation Overview", icon: Activity, description: "Total agents, live/staged split, issues and failed jobs.", kpis: [{ label: "Agents", value: "22" }, { label: "Issues", value: "3", tone: "warning" }] },
      { slug: "agent-health", label: "Agent Health", icon: Bot, description: "All agents — status, mode, last run, success rate, cost.", kpis: [{ label: "Live", value: "1", tone: "success" }, { label: "Staged", value: "18", tone: "info" }] },
      { slug: "technical-issues", label: "Technical Issues", icon: Bug, description: "Backlog, severity, owner, affected module and status.", kpis: [{ label: "Open", value: "7", tone: "warning" }] },
      { slug: "api-webhook-health", label: "API & Webhook Health", icon: Radio, description: "Endpoint health, latency, uptime, error rate, last error.", kpis: [{ label: "Latency", value: "142ms", tone: "success" }] },
      { slug: "job-queue", label: "Job Queue", icon: ListChecks, description: "Queued/failed jobs, retries and next retry.", kpis: [{ label: "Failed", value: "1", tone: "danger" }] },
      { slug: "llm-cost-usage", label: "LLM / Cost Usage", icon: Coins, description: "Calls by agent, estimated cost, staged vs live, tokens.", kpis: [{ label: "Calls", value: "1,284", tone: "plum" }] },
      { slug: "deployments", label: "Deployments", icon: Rocket, description: "App, environment, version, last deploy and status.", kpis: [{ label: "Apps", value: "3" }] },
      { slug: "integration-status", label: "Integration Status", icon: Plug, description: "WhatsApp, Stripe, GSC, GA4, Cloudflare, PostgreSQL, Redis.", kpis: [{ label: "Integrations", value: "18" }] },
      { slug: "logs-audit", label: "Logs & Audit", icon: ScrollText, description: "Safe logs — event, module, severity and trace ID.", status: { label: "No secrets", tone: "success" } },
    ],
  },

  reports: {
    key: "reports",
    base: "/reports",
    eyebrow: "Central hub",
    title: "Reports",
    description: "Scheduled briefs and executive reports — generated automatically, ready to export.",
    cols: 3,
    subsections: [
      { slug: "daily-standup", label: "Daily Standup", icon: Sun, description: "Cross-team daily standup — highlights and blockers.", status: { label: "Daily", tone: "info" } },
      { slug: "operations", label: "Operations Report", icon: Headset, description: "Automation rate, tickets, deliveries and SLA.", status: { label: "Daily", tone: "info" } },
      { slug: "sales", label: "Sales Report", icon: TrendingUp, description: "New customers, AOV and top markets.", status: { label: "Weekly", tone: "info" } },
      { slug: "partner-acquisition", label: "Partner Acquisition Report", icon: GitBranch, description: "Leads, onboarded partners and compliance review.", status: { label: "Weekly", tone: "info" } },
      { slug: "seo", label: "SEO Report", icon: Search, description: "Ranking movement, clicks, CTR and opportunities.", status: { label: "Weekly", tone: "info" } },
      { slug: "marketing", label: "Marketing Report", icon: Megaphone, description: "Engagement, leads and posts pending approval.", status: { label: "Weekly", tone: "info" } },
      { slug: "finance-compliance", label: "Finance & Compliance Report", icon: LineChart, description: "Revenue, compliance pass rate, audit flags, expiries.", status: { label: "Weekly", tone: "info" } },
      { slug: "dev-automation", label: "Dev & Automation Report", icon: Activity, description: "Agents live/staged, failed jobs, uptime and LLM cost.", status: { label: "Daily", tone: "info" } },
      { slug: "monthly-executive", label: "Monthly Executive", icon: FileText, description: "Revenue, net margin and B2B growth for founders.", status: { label: "Monthly", tone: "plum" } },
    ],
  },

  settings: {
    key: "settings",
    base: "/settings",
    eyebrow: "Workspace",
    title: "Settings",
    description: "Team, markets, connected apps and preferences for the command center.",
    cols: 3,
    // Workspace configuration is not market/city-specific — the geo filters don't apply.
    filterable: false,
    subsections: [
      { slug: "profile-team", label: "Profile & Team", icon: User, description: "Your account and team members.", kpis: [{ label: "Team", value: "5" }] },
      { slug: "roles-permissions", label: "Roles & Permissions", icon: Shield, description: "Access levels for each role.", kpis: [{ label: "Roles", value: "5" }] },
      { slug: "markets", label: "Markets", icon: Globe2, description: "Regions, cities and currencies.", kpis: [{ label: "Markets", value: "6" }] },
      { slug: "notifications", label: "Notifications", icon: Bell, description: "What you get pinged about.", status: { label: "Configurable", tone: "info" } },
      { slug: "agent-guardrails", label: "Agent Guardrails", icon: Bot, description: "Approval gates for autonomous agents.", status: { label: "Approval-first", tone: "success" } },
      { slug: "connected-apps", label: "Connected Apps", icon: Plug, description: "Connected apps and integrations.", kpis: [{ label: "Apps", value: "22" }] },
      { slug: "theme", label: "Theme", icon: Palette, description: "Light and dark mode appearance.", status: { label: "Light + Dark", tone: "neutral" } },
    ],
  },
};

/** Convenience: the subsection list for a section (used by landing + subnav). */
export function subsectionsOf(key: string): Subsection[] {
  return SECTIONS[key]?.subsections ?? [];
}
