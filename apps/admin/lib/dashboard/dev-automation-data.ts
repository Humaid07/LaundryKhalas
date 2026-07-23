/**
 * Dev & Automation mock data — technical operations, automation and agent
 * health command center. Deterministic, mock-only.
 *
 * PRIVACY: no secrets, API keys, tokens or raw environment values. Errors are
 * safe, human-readable summaries only.
 */
import type { KpiStat, Tone, TimeSeriesPoint } from "./types";

const spark = (n: number[]) => n;

/* --------------------------------- KPI cards -------------------------------- */

export const devKpis: KpiStat[] = [
  { label: "Total Agents", value: "22", delta: 0, tone: "rose", hint: "Across ops, SEO & marketing" },
  { label: "Live Agents", value: "1", delta: 0, tone: "success", hint: "WhatsApp Agent" },
  { label: "Staged Agents", value: "18", delta: 0, tone: "info" },
  { label: "Agents With Issues", value: "3", delta: 1.0, tone: "warning", spark: spark([1, 2, 2, 2, 3, 3, 3]) },
  { label: "Failed Jobs Today", value: "4", delta: -2.0, tone: "danger", spark: spark([8, 7, 6, 6, 5, 4, 4]) },
  { label: "Average API Latency", value: "142ms", delta: -6.0, tone: "success", spark: spark([168, 162, 158, 152, 148, 145, 142]) },
  { label: "Uptime", value: "99.94%", delta: 0.1, tone: "success", spark: spark([99.8, 99.85, 99.9, 99.9, 99.92, 99.93, 99.94]) },
  { label: "Active Automations", value: "11", delta: 10.0, tone: "rose", spark: spark([8, 9, 9, 10, 10, 11, 11]) },
  { label: "Pending Approvals", value: "6", delta: 2.0, tone: "warning", spark: spark([3, 4, 4, 5, 5, 6, 6]) },
  { label: "LLM Calls Today", value: "1,284", delta: 12.0, tone: "plum", spark: spark([840, 920, 1010, 1080, 1160, 1220, 1284]) },
  { label: "Estimated LLM Cost", value: "AED 3.2K", delta: 26.0, tone: "plum", spark: spark([1.8, 2.1, 2.3, 2.6, 2.8, 3.0, 3.2]) },
  { label: "Webhook Health", value: "Healthy", delta: 0, tone: "success", hint: "Inbound webhooks OK" },
  { label: "Queue Backlog", value: "12", delta: -4.0, tone: "info", spark: spark([22, 20, 18, 16, 15, 13, 12]) },
  { label: "Open Technical Issues", value: "7", delta: 1.0, tone: "warning", spark: spark([4, 5, 5, 6, 6, 7, 7]) },
];

/* ------------------------------- Agent health ------------------------------- */

export type AgentStatusD =
  | "Live"
  | "Staged"
  | "Scheduled"
  | "Paused"
  | "Degraded"
  | "Failed"
  | "Needs Review";

export type AgentMode = "live" | "staged" | "draft-only" | "monitor-only" | "approval-required";

export type AgentCategory = "Operations" | "SEO" | "Marketing" | "Platform" | "Reporting";

export const AGENT_CATEGORIES: AgentCategory[] = ["Operations", "SEO", "Marketing", "Platform", "Reporting"];
export const AGENT_STATUSES: AgentStatusD[] = ["Live", "Staged", "Scheduled", "Paused", "Degraded", "Failed", "Needs Review"];
export const AGENT_MODES: AgentMode[] = ["live", "staged", "draft-only", "monitor-only", "approval-required"];
export const AGENT_OWNERS = ["Platform", "Ops", "SEO Team", "Marketing", "Unassigned"] as const;

export interface AgentHealth {
  name: string;
  category: AgentCategory;
  status: AgentStatusD;
  mode: AgentMode;
  lastRun: string;
  nextRun: string;
  successRate: number;
  avgLatency: string;
  costToday: number;
  issues: number;
  owner: string;
}

export const agentHealth: AgentHealth[] = [
  { name: "WhatsApp Agent", category: "Operations", status: "Live", mode: "approval-required", lastRun: "2026-07-20T09:40:00Z", nextRun: "—", successRate: 97.4, avgLatency: "0.9s", costToday: 1.2, issues: 0, owner: "Ops" },
  { name: "Classifier Agent", category: "Operations", status: "Needs Review", mode: "draft-only", lastRun: "—", nextRun: "—", successRate: 0, avgLatency: "—", costToday: 0, issues: 1, owner: "Ops" },
  { name: "Order Flow Agent", category: "Operations", status: "Staged", mode: "staged", lastRun: "2026-07-20T09:35:00Z", nextRun: "2026-07-20T10:05:00Z", successRate: 99.1, avgLatency: "0.4s", costToday: 0, issues: 0, owner: "Ops" },
  { name: "SEO Crawl-State Agent", category: "SEO", status: "Staged", mode: "monitor-only", lastRun: "2026-07-20T08:00:00Z", nextRun: "2026-07-20T20:00:00Z", successRate: 98.7, avgLatency: "1.8s", costToday: 0.2, issues: 0, owner: "SEO Team" },
  { name: "GSC Performance Monitor", category: "SEO", status: "Scheduled", mode: "staged", lastRun: "2026-07-20T06:00:00Z", nextRun: "2026-07-21T06:00:00Z", successRate: 100, avgLatency: "2.1s", costToday: 0, issues: 0, owner: "SEO Team" },
  { name: "Indexing Agent", category: "SEO", status: "Staged", mode: "approval-required", lastRun: "2026-07-19T22:00:00Z", nextRun: "2026-07-20T22:00:00Z", successRate: 96.0, avgLatency: "1.2s", costToday: 0.1, issues: 0, owner: "SEO Team" },
  { name: "Content Research Agent", category: "SEO", status: "Staged", mode: "draft-only", lastRun: "2026-07-20T07:30:00Z", nextRun: "2026-07-20T19:30:00Z", successRate: 94.5, avgLatency: "3.4s", costToday: 0.6, issues: 0, owner: "SEO Team" },
  { name: "Blog Content Agent", category: "SEO", status: "Staged", mode: "approval-required", lastRun: "2026-07-19T18:00:00Z", nextRun: "2026-07-20T18:00:00Z", successRate: 92.0, avgLatency: "4.1s", costToday: 0.4, issues: 0, owner: "SEO Team" },
  { name: "Hyperlocal Area Page Agent", category: "SEO", status: "Paused", mode: "approval-required", lastRun: "2026-07-18T12:00:00Z", nextRun: "—", successRate: 90.2, avgLatency: "3.9s", costToday: 0, issues: 1, owner: "SEO Team" },
  { name: "Money Page Optimizer", category: "SEO", status: "Staged", mode: "approval-required", lastRun: "2026-07-20T05:00:00Z", nextRun: "2026-07-21T05:00:00Z", successRate: 95.3, avgLatency: "2.8s", costToday: 0.2, issues: 0, owner: "SEO Team" },
  { name: "Internal Linking Agent", category: "SEO", status: "Staged", mode: "draft-only", lastRun: "2026-07-20T04:00:00Z", nextRun: "2026-07-21T04:00:00Z", successRate: 97.8, avgLatency: "1.5s", costToday: 0.1, issues: 0, owner: "SEO Team" },
  { name: "Duplicate / Cannibalization Agent", category: "SEO", status: "Staged", mode: "monitor-only", lastRun: "2026-07-20T03:00:00Z", nextRun: "2026-07-21T03:00:00Z", successRate: 99.0, avgLatency: "2.2s", costToday: 0.1, issues: 0, owner: "SEO Team" },
  { name: "Topical Authority Agent", category: "SEO", status: "Staged", mode: "draft-only", lastRun: "2026-07-19T20:00:00Z", nextRun: "2026-07-20T20:00:00Z", successRate: 93.4, avgLatency: "3.1s", costToday: 0.3, issues: 0, owner: "SEO Team" },
  { name: "Keyword Mapping Agent", category: "SEO", status: "Staged", mode: "monitor-only", lastRun: "2026-07-20T02:00:00Z", nextRun: "2026-07-21T02:00:00Z", successRate: 98.2, avgLatency: "1.9s", costToday: 0.1, issues: 0, owner: "SEO Team" },
  { name: "AI Search Visibility Agent", category: "SEO", status: "Degraded", mode: "monitor-only", lastRun: "2026-07-20T01:00:00Z", nextRun: "2026-07-20T13:00:00Z", successRate: 84.0, avgLatency: "5.6s", costToday: 0.5, issues: 1, owner: "SEO Team" },
  { name: "Competitor Monitor", category: "Marketing", status: "Staged", mode: "monitor-only", lastRun: "2026-07-20T06:30:00Z", nextRun: "2026-07-20T18:30:00Z", successRate: 97.1, avgLatency: "2.4s", costToday: 0.2, issues: 0, owner: "Marketing" },
  { name: "News & Brand Monitor", category: "Marketing", status: "Staged", mode: "monitor-only", lastRun: "2026-07-20T08:15:00Z", nextRun: "2026-07-20T14:15:00Z", successRate: 96.4, avgLatency: "2.0s", costToday: 0.2, issues: 0, owner: "Marketing" },
  { name: "Social Posting Agent", category: "Marketing", status: "Staged", mode: "approval-required", lastRun: "2026-07-20T07:00:00Z", nextRun: "2026-07-20T15:00:00Z", successRate: 95.0, avgLatency: "1.6s", costToday: 0.1, issues: 0, owner: "Marketing" },
  { name: "Outreach Drafting Agent", category: "Marketing", status: "Staged", mode: "draft-only", lastRun: "2026-07-19T16:00:00Z", nextRun: "2026-07-20T16:00:00Z", successRate: 91.8, avgLatency: "3.3s", costToday: 0.3, issues: 0, owner: "Marketing" },
  { name: "PR Drafting Agent", category: "Marketing", status: "Staged", mode: "draft-only", lastRun: "2026-07-18T15:00:00Z", nextRun: "2026-07-21T15:00:00Z", successRate: 90.0, avgLatency: "3.8s", costToday: 0.2, issues: 0, owner: "Marketing" },
  { name: "UTM Agent", category: "Platform", status: "Staged", mode: "monitor-only", lastRun: "2026-07-20T09:00:00Z", nextRun: "2026-07-20T21:00:00Z", successRate: 99.6, avgLatency: "0.3s", costToday: 0, issues: 0, owner: "Platform" },
  { name: "Reporting Agent", category: "Reporting", status: "Staged", mode: "staged", lastRun: "2026-07-20T07:00:00Z", nextRun: "2026-07-21T07:00:00Z", successRate: 99.2, avgLatency: "1.1s", costToday: 0.1, issues: 0, owner: "Platform" },
];

export const agentStatusToneD: Record<AgentStatusD, Tone> = {
  Live: "success",
  Staged: "info",
  Scheduled: "plum",
  Paused: "neutral",
  Degraded: "warning",
  Failed: "danger",
  "Needs Review": "warning",
};

export const AGENT_ACTIONS = ["View Logs", "Retry Job", "Pause Agent", "Resume Agent", "View Config", "Assign Owner", "Create Issue"];

/** URL-safe slug for an agent name (agent names contain spaces and "/"). */
export function agentSlug(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

/** Look up a single agent by its URL slug for its detail page. */
export function getAgentBySlug(slug: string): AgentHealth | undefined {
  return agentHealth.find((a) => agentSlug(a.name) === slug);
}

/** True when an agent should surface in the "Needs attention" view. */
export function agentNeedsAttention(a: AgentHealth): boolean {
  return a.issues > 0 || a.status === "Degraded" || a.status === "Failed" || a.status === "Needs Review" || a.status === "Paused";
}

/* ------------------------------ Technical issues ---------------------------- */

export interface TechIssue {
  id: string;
  title: string;
  severity: "Critical" | "High" | "Medium" | "Low";
  module: string;
  owner: string;
  status: "Open" | "In Progress" | "Blocked" | "Resolved";
  createdAt: string;
  lastUpdate: string;
  /** Set on WhatsApp channel-specific issues so the Channel filter applies. */
  channel?: string;
  /** Set on genuinely site-wide/technical issues → bypass geo filters. */
  scope?: "global";
}

export const techIssues: TechIssue[] = [
  { id: "DEV-101", title: "WhatsApp conversation list endpoint missing", severity: "High", module: "WhatsApp Agent API", owner: "Platform", status: "Open", createdAt: "2026-07-18T10:00:00Z", lastUpdate: "2026-07-20T08:00:00Z", channel: "WhatsApp" },
  { id: "DEV-102", title: "Server-side approval persistence missing", severity: "High", module: "Approvals", owner: "Platform", status: "In Progress", createdAt: "2026-07-18T11:00:00Z", lastUpdate: "2026-07-20T09:10:00Z", scope: "global" },
  { id: "DEV-103", title: "Dashboard order API wiring pending", severity: "Medium", module: "Orders API", owner: "Platform", status: "Open", createdAt: "2026-07-19T09:00:00Z", lastUpdate: "2026-07-20T07:30:00Z", scope: "global" },
  { id: "DEV-104", title: "Classifier agent not built", severity: "Medium", module: "Classifier Agent", owner: "Ops", status: "Blocked", createdAt: "2026-07-17T14:00:00Z", lastUpdate: "2026-07-19T16:00:00Z", scope: "global" },
  { id: "DEV-105", title: "URL-synced filters not implemented", severity: "Low", module: "Admin Dashboard", owner: "Platform", status: "Open", createdAt: "2026-07-19T12:00:00Z", lastUpdate: "2026-07-20T06:00:00Z", scope: "global" },
  { id: "DEV-106", title: "Settings toggles not persisted", severity: "Low", module: "Settings API", owner: "Platform", status: "Open", createdAt: "2026-07-19T13:00:00Z", lastUpdate: "2026-07-20T06:15:00Z", scope: "global" },
  { id: "DEV-107", title: "Meta interactive payload support pending", severity: "Medium", module: "WhatsApp Agent", owner: "Ops", status: "Open", createdAt: "2026-07-19T15:00:00Z", lastUpdate: "2026-07-20T08:45:00Z", channel: "WhatsApp" },
];

export const severityTone: Record<TechIssue["severity"], Tone> = {
  Critical: "danger",
  High: "danger",
  Medium: "warning",
  Low: "info",
};

export const issueStatusTone: Record<TechIssue["status"], Tone> = {
  Open: "warning",
  "In Progress": "info",
  Blocked: "danger",
  Resolved: "success",
};

/* ---------------------------- API & webhook health -------------------------- */

export interface ApiHealth {
  endpoint: string;
  status: "Operational" | "Degraded" | "Down" | "Standby";
  lastChecked: string;
  latency: string;
  errorRate: number;
  uptime: number;
  lastError: string;
  /** Endpoints are shared infrastructure → global, never geo-filtered. */
  scope?: "global";
}

export const apiHealth: ApiHealth[] = [
  { endpoint: "WhatsApp Agent API", status: "Operational", lastChecked: "2026-07-20T09:45:00Z", latency: "0.9s", errorRate: 0.4, uptime: 99.9, lastError: "—", scope: "global" },
  { endpoint: "Admin Dashboard", status: "Operational", lastChecked: "2026-07-20T09:45:00Z", latency: "0.2s", errorRate: 0.0, uptime: 100, lastError: "—", scope: "global" },
  { endpoint: "Orders API", status: "Degraded", lastChecked: "2026-07-20T09:44:00Z", latency: "1.8s", errorRate: 3.1, uptime: 98.6, lastError: "Timeout on list endpoint", scope: "global" },
  { endpoint: "Settings API", status: "Operational", lastChecked: "2026-07-20T09:45:00Z", latency: "0.3s", errorRate: 0.0, uptime: 100, lastError: "—", scope: "global" },
  { endpoint: "Webhook Verify", status: "Operational", lastChecked: "2026-07-20T09:43:00Z", latency: "0.1s", errorRate: 0.0, uptime: 100, lastError: "—", scope: "global" },
  { endpoint: "Meta WhatsApp Webhook", status: "Standby", lastChecked: "—", latency: "—", errorRate: 0, uptime: 0, lastError: "Not connected", scope: "global" },
  { endpoint: "Stripe Webhook", status: "Standby", lastChecked: "—", latency: "—", errorRate: 0, uptime: 0, lastError: "Not connected", scope: "global" },
  { endpoint: "GSC Connector", status: "Standby", lastChecked: "—", latency: "—", errorRate: 0, uptime: 0, lastError: "Not connected", scope: "global" },
  { endpoint: "GA4 Connector", status: "Standby", lastChecked: "—", latency: "—", errorRate: 0, uptime: 0, lastError: "Not connected", scope: "global" },
];

export const apiStatusTone: Record<ApiHealth["status"], Tone> = {
  Operational: "success",
  Degraded: "warning",
  Down: "danger",
  Standby: "neutral",
};

/* --------------------------------- Job queue -------------------------------- */

export interface JobRow {
  name: string;
  agent: string;
  status: "Queued" | "Running" | "Retrying" | "Failed" | "Done";
  queuedAt: string;
  attempts: number;
  nextRetry: string;
  error: string;
  /** Background/scheduled jobs run site-wide → global, never geo-filtered. */
  scope?: "global";
}

export const jobQueue: JobRow[] = [
  { name: "generate-daily-brief", agent: "Reporting Agent", status: "Running", queuedAt: "2026-07-20T09:40:00Z", attempts: 1, nextRetry: "—", error: "—", scope: "global" },
  { name: "crawl-state-refresh", agent: "SEO Crawl-State Agent", status: "Queued", queuedAt: "2026-07-20T09:42:00Z", attempts: 0, nextRetry: "—", error: "—", scope: "global" },
  { name: "submit-indexing-batch", agent: "Indexing Agent", status: "Retrying", queuedAt: "2026-07-20T09:20:00Z", attempts: 2, nextRetry: "2026-07-20T10:00:00Z", error: "Rate limit", scope: "global" },
  { name: "ai-visibility-scan", agent: "AI Search Visibility Agent", status: "Failed", queuedAt: "2026-07-20T09:00:00Z", attempts: 3, nextRetry: "—", error: "Provider timeout", scope: "global" },
  { name: "draft-social-posts", agent: "Social Posting Agent", status: "Done", queuedAt: "2026-07-20T08:00:00Z", attempts: 1, nextRetry: "—", error: "—", scope: "global" },
  { name: "competitor-snapshot", agent: "Competitor Monitor", status: "Queued", queuedAt: "2026-07-20T09:43:00Z", attempts: 0, nextRetry: "—", error: "—", scope: "global" },
];

export const jobStatusTone: Record<JobRow["status"], Tone> = {
  Queued: "info",
  Running: "rose",
  Retrying: "warning",
  Failed: "danger",
  Done: "success",
};

/** Ordered lifecycle used to render a job's progress on its detail page. */
export const JOB_LIFECYCLE: JobRow["status"][] = ["Queued", "Running", "Done"];

/** Look up a single background job by its name (used as the route id). */
export function getJob(name: string): JobRow | undefined {
  return jobQueue.find((j) => j.name === name);
}

/* ------------------------------- LLM / cost usage --------------------------- */

export interface LlmUsageRow {
  agent: string;
  calls: number;
  tokens: number;
  estCost: number;
  mode: "staged" | "live";
}

export const llmUsage: LlmUsageRow[] = [
  { agent: "WhatsApp Agent", calls: 486, tokens: 512000, estCost: 1.2, mode: "staged" },
  { agent: "Content Research Agent", calls: 214, tokens: 386000, estCost: 0.6, mode: "staged" },
  { agent: "Blog Content Agent", calls: 132, tokens: 298000, estCost: 0.4, mode: "staged" },
  { agent: "AI Search Visibility Agent", calls: 168, tokens: 240000, estCost: 0.5, mode: "staged" },
  { agent: "Topical Authority Agent", calls: 98, tokens: 176000, estCost: 0.3, mode: "staged" },
  { agent: "Outreach Drafting Agent", calls: 94, tokens: 158000, estCost: 0.2, mode: "staged" },
  { agent: "Others", calls: 92, tokens: 120000, estCost: 0.0, mode: "staged" },
];

/* -------------------------------- Deployments ------------------------------- */

export interface DeployRow {
  app: string;
  environment: "Local" | "Staging" | "Production";
  version: string;
  lastDeploy: string;
  deployStatus: "Success" | "Building" | "Failed" | "Not deployed";
  buildStatus: "Passing" | "Failing" | "Pending";
  owner: string;
}

export const deployments: DeployRow[] = [
  { app: "whatsapp-agent (API)", environment: "Local", version: "0.4.1", lastDeploy: "2026-07-20T09:00:00Z", deployStatus: "Success", buildStatus: "Passing", owner: "Platform" },
  { app: "admin (Dashboard)", environment: "Local", version: "0.6.0", lastDeploy: "2026-07-20T09:30:00Z", deployStatus: "Success", buildStatus: "Passing", owner: "Platform" },
  { app: "whatsapp-chat (UI)", environment: "Local", version: "0.3.2", lastDeploy: "2026-07-20T08:00:00Z", deployStatus: "Success", buildStatus: "Passing", owner: "Platform" },
  { app: "admin (Dashboard)", environment: "Staging", version: "—", lastDeploy: "—", deployStatus: "Not deployed", buildStatus: "Pending", owner: "Platform" },
  { app: "whatsapp-agent (API)", environment: "Production", version: "—", lastDeploy: "—", deployStatus: "Not deployed", buildStatus: "Pending", owner: "Platform" },
];

export const deployStatusTone: Record<DeployRow["deployStatus"], Tone> = {
  Success: "success",
  Building: "info",
  Failed: "danger",
  "Not deployed": "neutral",
};

export const buildStatusTone: Record<DeployRow["buildStatus"], Tone> = {
  Passing: "success",
  Failing: "danger",
  Pending: "neutral",
};

/* ------------------------------ Integration status -------------------------- */

export interface IntegrationRow {
  name: string;
  category: string;
  status: "Connected" | "Standby" | "Not connected";
  /** Platform-level connections → global, never geo-filtered. */
  scope?: "global";
}

export const integrations: IntegrationRow[] = [
  { name: "WhatsApp API", category: "Messaging", status: "Standby", scope: "global" },
  { name: "Stripe", category: "Payments", status: "Standby", scope: "global" },
  { name: "GSC", category: "SEO", status: "Standby", scope: "global" },
  { name: "GA4", category: "Analytics", status: "Standby", scope: "global" },
  { name: "Semrush", category: "SEO", status: "Not connected", scope: "global" },
  { name: "Ahrefs", category: "SEO", status: "Not connected", scope: "global" },
  { name: "Instagram", category: "Social", status: "Not connected", scope: "global" },
  { name: "Facebook", category: "Social", status: "Not connected", scope: "global" },
  { name: "TikTok", category: "Social", status: "Not connected", scope: "global" },
  { name: "LinkedIn", category: "Social", status: "Not connected", scope: "global" },
  { name: "HeyGen", category: "Creative", status: "Not connected", scope: "global" },
  { name: "Gamma", category: "Creative", status: "Not connected", scope: "global" },
  { name: "Composio", category: "Automation", status: "Not connected", scope: "global" },
  { name: "Apollo", category: "Outreach", status: "Not connected", scope: "global" },
  { name: "Gmail", category: "Outreach", status: "Not connected", scope: "global" },
  { name: "Cloudflare R2", category: "Storage", status: "Standby", scope: "global" },
  { name: "PostgreSQL", category: "Database", status: "Standby", scope: "global" },
  { name: "Redis", category: "Cache / Queue", status: "Standby", scope: "global" },
];

export const integrationStatusTone: Record<IntegrationRow["status"], Tone> = {
  Connected: "success",
  Standby: "warning",
  "Not connected": "neutral",
};

/* -------------------------------- Logs & audit ------------------------------ */

export interface LogRow {
  timestamp: string;
  module: string;
  event: string;
  source: string;
  severity: "Info" | "Warning" | "Error" | "Debug";
  message: string;
  traceId: string;
  /** Set on channel/geo-scoped events (e.g. an inbound WhatsApp message). */
  channel?: string;
  city?: string;
  /** Set on genuinely site-wide system events → bypass geo filters. */
  scope?: "global";
}

export const logs: LogRow[] = [
  { timestamp: "2026-07-20T09:45:12Z", module: "WhatsApp Agent", event: "message.processed", source: "MockWhatsAppAdapter", severity: "Info", message: "Inbound message handled, reply drafted for approval", traceId: "trc_8f21a", channel: "WhatsApp", city: "Dubai" },
  { timestamp: "2026-07-20T09:44:03Z", module: "Orders API", event: "request.slow", source: "orders.list", severity: "Warning", message: "List endpoint exceeded 1.5s threshold", traceId: "trc_7b02c", scope: "global" },
  { timestamp: "2026-07-20T09:40:55Z", module: "AI Visibility", event: "job.failed", source: "ai-visibility-scan", severity: "Error", message: "Provider timeout after 3 attempts", traceId: "trc_5c99d", scope: "global" },
  { timestamp: "2026-07-20T09:38:20Z", module: "Reporting Agent", event: "job.started", source: "generate-daily-brief", severity: "Info", message: "Daily brief generation started", traceId: "trc_4a12e", scope: "global" },
  { timestamp: "2026-07-20T09:35:10Z", module: "Indexing Agent", event: "job.retry", source: "submit-indexing-batch", severity: "Warning", message: "Rate limit hit, scheduled retry", traceId: "trc_3f77a", scope: "global" },
  { timestamp: "2026-07-20T09:30:00Z", module: "Admin Dashboard", event: "auth.session", source: "web", severity: "Debug", message: "Session refreshed for internal user", traceId: "trc_2d45b", scope: "global" },
];

export const logSeverityTone: Record<LogRow["severity"], Tone> = {
  Info: "info",
  Warning: "warning",
  Error: "danger",
  Debug: "neutral",
};

/* ----------------------------------- Charts --------------------------------- */

export const liveVsMock: TimeSeriesPoint[] = [
  { label: "Live", value: 1 },
  { label: "Staged", value: 18 },
  { label: "Paused", value: 1 },
  { label: "Degraded", value: 1 },
  { label: "Needs Review", value: 1 },
];

export const issuesByCategory: TimeSeriesPoint[] = [
  { label: "Operations", value: 2 },
  { label: "SEO", value: 2 },
  { label: "Marketing", value: 0 },
  { label: "Platform", value: 3 },
  { label: "Reporting", value: 0 },
];

export const apiLatencyOverTime: TimeSeriesPoint[] = [
  { label: "09:00", value: 168 },
  { label: "09:10", value: 160 },
  { label: "09:20", value: 155 },
  { label: "09:30", value: 149 },
  { label: "09:40", value: 145 },
  { label: "09:45", value: 142 },
];

export const failedJobsTrend: TimeSeriesPoint[] = [
  { label: "Mon", value: 9 },
  { label: "Tue", value: 7 },
  { label: "Wed", value: 8 },
  { label: "Thu", value: 6 },
  { label: "Fri", value: 5 },
  { label: "Sat", value: 4 },
  { label: "Sun", value: 4 },
];

export const llmCallsByAgent: TimeSeriesPoint[] = llmUsage.map((l) => ({ label: l.agent, value: l.calls }));
export const costByAgent: TimeSeriesPoint[] = llmUsage.filter((l) => l.estCost > 0).map((l) => ({ label: l.agent, value: l.estCost }));

export const uptimeTrend: TimeSeriesPoint[] = [
  { label: "Mon", value: 99.8 },
  { label: "Tue", value: 99.85 },
  { label: "Wed", value: 99.9 },
  { label: "Thu", value: 99.9 },
  { label: "Fri", value: 99.92 },
  { label: "Sat", value: 99.93 },
  { label: "Sun", value: 99.94 },
];

export const integrationBreakdown: TimeSeriesPoint[] = [
  { label: "Standby", value: 7 },
  { label: "Not connected", value: 11 },
];

/* --------------------------------- Activity --------------------------------- */

export interface DevActivity {
  id: string;
  title: string;
  detail: string;
  time: string;
  tone: Tone;
}

export const devActivity: DevActivity[] = [
  { id: "da1", title: "Job failed", detail: "ai-visibility-scan · provider timeout", time: "2026-07-20T09:40:00Z", tone: "danger" },
  { id: "da2", title: "Orders API degraded", detail: "List endpoint slow — 1.8s avg", time: "2026-07-20T09:44:00Z", tone: "warning" },
  { id: "da3", title: "WhatsApp Agent healthy", detail: "97.4% success · 0.9s avg latency", time: "2026-07-20T09:40:00Z", tone: "success" },
  { id: "da4", title: "New technical issue", detail: "DEV-107 · Meta interactive payload support", time: "2026-07-20T08:45:00Z", tone: "info" },
  { id: "da5", title: "Daily brief job started", detail: "Reporting Agent · generate-daily-brief", time: "2026-07-20T09:38:00Z", tone: "plum" },
];
