/**
 * SEO Agents API client — the dashboard's ONLY door to the FastAPI SEO backend.
 *
 * Mirrors the `whatsapp-agent-api.ts` pattern (env base URL + typed `request`).
 * Every method has a deterministic MOCK fallback with the SAME DTO shape, so the
 * dashboard renders even when the backend is unreachable — this is the
 * "mock provider now, API provider next, same DTO for both" adapter. The SEO
 * backend is served by the same FastAPI app as the WhatsApp agent.
 *
 * The dashboard never calls Supabase directly — FastAPI only.
 */

import type {
  GscPage,
  IndexRow,
  HyperlocalPage,
  TechSeoIssue,
  Competitor,
  AiSearchRow,
} from "./seo-data";
import type { SeoTask, KpiStat } from "./types";
import { getToken } from "./auth-token";

const BASE_URL =
  process.env.NEXT_PUBLIC_SEO_AGENT_API_URL ??
  process.env.NEXT_PUBLIC_WHATSAPP_AGENT_API_URL ??
  "http://localhost:8100";

export class SeoApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "SeoApiError";
    this.status = status;
  }
}

// --- DTOs (mirror seo_agents/schemas.py) -----------------------------------
export interface SeoAgentDTO {
  id: string;
  name: string;
  category: string;
  owner: string;
  status: string; // Live | Staged | Scheduled | Paused
  mode: string; // monitor-only | draft-only | approval-required
  description: string;
  schedule: string;
  required_inputs: string[];
  allowed_actions: string[];
  forbidden_actions: string[];
  human_approval_required: boolean;
  dashboard_sections: string[];
}

export interface SeoRunDTO {
  run_id: string;
  agent_id: string;
  agent_name: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  market: string | null;
  city: string | null;
  service: string | null;
  summary: string;
  findings_count: number;
  recommendations_count: number;
  urgent_count: number;
  approval_tasks_created: number;
  dashboard_sections_affected: string[];
  next_action: string;
  cost_estimate: number;
  source_type: string;
  mode: string;
}

export interface SeoFindingDTO {
  finding_id: string;
  run_id: string;
  agent_id: string;
  finding_type: string;
  title: string;
  description: string;
  page_url: string | null;
  competitor_url: string | null;
  market: string | null;
  city: string | null;
  service: string | null;
  priority: string;
  severity: string;
  impact_reason: string;
  recommended_action: string;
  dashboard_section: string;
  scope: "geo" | "global";
  created_at: string;
}

export interface SeoRecommendationDTO {
  recommendation_id: string;
  run_id: string;
  agent_id: string;
  title: string;
  recommendation_type: string;
  page_url: string | null;
  market: string | null;
  city: string | null;
  service: string | null;
  suggested_change: string;
  expected_impact: string;
  approval_required: boolean;
  approval_status: string;
  dashboard_section: string;
  created_at: string;
}

export interface SeoApprovalTaskDTO {
  task_id: string;
  agent_id: string;
  run_id: string;
  task_type: string;
  title: string;
  description: string;
  page_url: string | null;
  market: string | null;
  city: string | null;
  service: string | null;
  priority: string;
  approval_status: string;
  suggested_action: string;
  assigned_to: string | null;
  created_at: string;
  due_date: string | null;
}

export interface SeoReportDTO {
  id: string;
  report_type: "daily" | "weekly";
  generated_at: string;
  title: string;
  wins: string[];
  risks: string[];
  urgent_issues: string[];
  recommended_actions: string[];
  agent_run_summary: Array<Record<string, unknown>>;
  next_steps: string[];
}

export interface SeoAgentHealthDTO {
  agent_id: string;
  name: string;
  category: string;
  status: string;
  mode: string;
  owner: string;
  schedule: string;
  last_run: string | null;
  next_run: string;
  success_rate: number;
  avg_latency: string;
  cost_today: number;
  issues: number;
  findings: number;
  approval_tasks: number;
  dashboard_sections: string[];
  human_approval_required: boolean;
}

export interface SeoOverviewDTO {
  active_agents: number;
  total_agents: number;
  runs_today: number;
  urgent_issues: number;
  high_issues: number;
  pages_gaining: number;
  pages_losing: number;
  indexing_issues: number;
  pending_approvals: number;
  content_opportunities: number;
  total_findings: number;
}

// --- fetch helper -----------------------------------------------------------
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  const token = getToken();
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
    });
  } catch {
    throw new SeoApiError(0, `Could not reach the SEO agent backend (${BASE_URL}).`);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new SeoApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

/** Try the live API; fall back to deterministic mock so the UI never breaks. */
async function withFallback<T>(fn: () => Promise<T>, fallback: T): Promise<T> {
  try {
    return await fn();
  } catch {
    return fallback;
  }
}

// --- public client ----------------------------------------------------------
export const seoAgentApi = {
  baseUrl: BASE_URL,

  listSeoAgents: () => withFallback(() => request<SeoAgentDTO[]>("/api/seo/agents"), MOCK_AGENTS),
  getSeoAgent: (id: string) => request<SeoAgentDTO>(`/api/seo/agents/${id}`),
  listSeoAgentHealth: () =>
    withFallback(() => request<SeoAgentHealthDTO[]>("/api/seo/agent-health"), MOCK_HEALTH),
  listSeoRuns: (agentId?: string) =>
    withFallback(
      () => request<SeoRunDTO[]>(`/api/seo/runs${agentId ? `?agent_id=${agentId}` : ""}`),
      [],
    ),
  runSeoAgent: (id: string, body?: Record<string, string>) =>
    request<SeoRunDTO>(`/api/seo/agents/${id}/run`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  listSeoFindings: (params?: { agentId?: string; section?: string }) => {
    const q = new URLSearchParams();
    if (params?.agentId) q.set("agent_id", params.agentId);
    if (params?.section) q.set("section", params.section);
    const qs = q.toString();
    return withFallback(() => request<SeoFindingDTO[]>(`/api/seo/findings${qs ? `?${qs}` : ""}`), []);
  },
  listSeoTasks: (status?: string) =>
    withFallback(
      () => request<SeoApprovalTaskDTO[]>(`/api/seo/tasks${status ? `?status=${status}` : ""}`),
      [],
    ),
  approveSeoTask: (id: string, operator?: string) =>
    request<SeoApprovalTaskDTO>(`/api/seo/tasks/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ operator }),
    }),
  rejectSeoTask: (id: string, operator?: string) =>
    request<SeoApprovalTaskDTO>(`/api/seo/tasks/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ operator }),
    }),
  getDailySeoReport: () =>
    withFallback(() => request<SeoReportDTO>("/api/seo/reports/daily"), MOCK_REPORT("daily")),
  getWeeklySeoReport: () =>
    withFallback(() => request<SeoReportDTO>("/api/seo/reports/weekly"), MOCK_REPORT("weekly")),
  getSeoOverview: () => withFallback(() => request<SeoOverviewDTO>("/api/seo/overview"), MOCK_OVERVIEW),

  // --- subsection tables (throw on error; the component supplies fallback) --
  // The backend returns these in the exact dashboard row shapes.
  getGscPages: () => request<GscPage[]>("/api/seo/dashboard/gsc-pages"),
  getIndexing: () => request<IndexRow[]>("/api/seo/dashboard/indexing"),
  getHyperlocal: () => request<HyperlocalPage[]>("/api/seo/dashboard/hyperlocal"),
  getTechnicalIssues: () => request<TechSeoIssue[]>("/api/seo/dashboard/technical-issues"),
  getCompetitors: () => request<Competitor[]>("/api/seo/dashboard/competitors"),
  getAiSearch: () => request<AiSearchRow[]>("/api/seo/dashboard/ai-search"),

  // Content Pipeline: live approval tasks mapped to the SeoTask table shape.
  getContentTasks: async (): Promise<SeoTask[]> => {
    const tasks = await request<SeoApprovalTaskDTO[]>("/api/seo/tasks");
    return tasks.map(taskToSeoTask);
  },

  // Overview KPI row derived from the live overview summary.
  getOverviewKpis: async (): Promise<KpiStat[]> => {
    const o = await request<SeoOverviewDTO>("/api/seo/overview");
    return [
      { label: "Active agents", value: `${o.active_agents}/${o.total_agents}` },
      { label: "Runs today", value: String(o.runs_today) },
      {
        label: "Pending approvals",
        value: String(o.pending_approvals),
        tone: o.pending_approvals > 0 ? "warning" : "success",
      },
      {
        label: "Urgent issues",
        value: String(o.urgent_issues),
        tone: o.urgent_issues > 0 ? "danger" : "success",
      },
      { label: "Content opportunities", value: String(o.content_opportunities) },
      {
        label: "Indexing issues",
        value: String(o.indexing_issues),
        tone: o.indexing_issues > 0 ? "warning" : "success",
      },
    ];
  },
};

const PRIORITY_LABEL: Record<string, SeoTask["priority"]> = {
  urgent: "Urgent",
  high: "High",
  medium: "Medium",
  low: "Low",
};
const APPROVAL_TO_STATUS: Record<string, SeoTask["status"]> = {
  pending: "Needs Review",
  approved: "Done",
  rejected: "Done",
};

function taskToSeoTask(t: SeoApprovalTaskDTO): SeoTask {
  return {
    id: t.task_id,
    task: t.title,
    agent: t.agent_id,
    priority: PRIORITY_LABEL[t.priority] ?? "Medium",
    url: t.page_url ?? "—",
    status: APPROVAL_TO_STATUS[t.approval_status] ?? "Todo",
    suggestedAction: t.suggested_action,
    approvalRequired: t.approval_status === "pending",
    // city/scope carried through for global filtering when present.
    ...(t.city ? { city: t.city as SeoTask["city"] } : { scope: "global" as const }),
  };
}

// --- deterministic mock fallback (same DTO shape) ---------------------------
const AGENT_SEED: Array<[string, string, string]> = [
  ["SEO-01", "Competitor Monitor", "monitor-only"],
  ["SEO-02", "News & Industry Trend Monitor", "monitor-only"],
  ["SEO-03", "Google Search Console Monitor", "monitor-only"],
  ["SEO-04", "Indexing & Sitemap Agent", "approval-required"],
  ["SEO-05", "Content Research Agent", "monitor-only"],
  ["SEO-06", "Blog + Schema Draft Agent", "draft-only"],
  ["SEO-07", "Topical Authority Agent", "monitor-only"],
  ["SEO-08", "Internal Linking Agent", "approval-required"],
  ["SEO-09", "Backlink Opportunity Agent", "approval-required"],
  ["SEO-10", "Duplicate Content Agent", "monitor-only"],
  ["SEO-11", "Money Page Optimization Agent", "approval-required"],
  ["SEO-12", "Local & Area Page Agent", "approval-required"],
  ["SEO-13", "Content Decay & Cannibalization Agent", "monitor-only"],
  ["SEO-14", "AI Search Visibility Agent", "monitor-only"],
  ["SEO-15", "GCC Expansion SEO Agent", "monitor-only"],
  ["SEO-16", "SEO Reporting Agent", "monitor-only"],
];

const MOCK_AGENTS: SeoAgentDTO[] = AGENT_SEED.map(([id, name, mode]) => ({
  id,
  name,
  category: "SEO",
  owner: "SEO Team",
  status: id === "SEO-16" ? "Scheduled" : "Staged",
  mode,
  description: `${name} — staged, approval-gated (offline snapshot).`,
  schedule: "Daily",
  required_inputs: [],
  allowed_actions: [],
  forbidden_actions: ["auto_publish_content"],
  human_approval_required: id !== "SEO-16",
  dashboard_sections: ["agent-health", "reports"],
}));

const MOCK_HEALTH: SeoAgentHealthDTO[] = MOCK_AGENTS.map((a) => ({
  agent_id: a.id,
  name: a.name,
  category: "SEO",
  status: a.status,
  mode: a.mode,
  owner: a.owner,
  schedule: a.schedule,
  last_run: null,
  next_run: a.schedule,
  success_rate: 100,
  avg_latency: "0.4s",
  cost_today: 0,
  issues: 0,
  findings: 0,
  approval_tasks: 0,
  dashboard_sections: a.dashboard_sections,
  human_approval_required: a.human_approval_required,
}));

const MOCK_OVERVIEW: SeoOverviewDTO = {
  active_agents: 16,
  total_agents: 16,
  runs_today: 16,
  urgent_issues: 0,
  high_issues: 0,
  pages_gaining: 0,
  pages_losing: 0,
  indexing_issues: 0,
  pending_approvals: 0,
  content_opportunities: 0,
  total_findings: 0,
};

function MOCK_REPORT(type: "daily" | "weekly"): SeoReportDTO {
  return {
    id: `seo-report-${type}`,
    report_type: type,
    generated_at: "2026-07-22T06:00:00Z",
    title: `${type === "daily" ? "Daily SEO brief" : "Weekly SEO summary"} — offline snapshot`,
    wins: [],
    risks: [],
    urgent_issues: [],
    recommended_actions: [],
    agent_run_summary: [],
    next_steps: ["Start the SEO backend to load live agent output."],
  };
}
