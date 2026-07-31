"use client";

import { useCallback, useEffect, useState } from "react";
import {
  agentApi,
  type HumanInterventionDTO,
  type HumanInterventionMetrics,
} from "@/lib/dashboard/whatsapp-agent-api";

const PRIORITY_STYLE: Record<string, string> = {
  CRITICAL: "bg-danger/10 text-danger border-danger/20",
  HIGH: "bg-warning/10 text-warning border-warning/20",
  MEDIUM: "bg-info/10 text-info border-info/20",
  NORMAL: "bg-surface-sunken text-ink border-border",
};
const STATUS_LABEL: Record<string, string> = {
  WAITING_FOR_HUMAN: "Waiting",
  ASSIGNED: "Assigned",
  HUMAN_ACTIVE: "Human active",
  RESOLVED: "Resolved",
  RELEASED_TO_AI: "Released to AI",
  CLOSED: "Closed",
};
const REASON_LABEL: Record<string, string> = {
  ABUSIVE_LANGUAGE: "Abusive language",
  THREAT: "Threat",
  CUSTOMER_REQUESTED_HUMAN: "Customer requested",
  COMPLAINT_ESCALATION: "Complaint",
  MANUAL_TAKEOVER: "Manual",
};

function waitingFor(iso: string): string {
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m`;
  const h = Math.floor(mins / 60);
  return `${h}h ${mins % 60}m`;
}

export function HumanInterventionQueue() {
  const [rows, setRows] = useState<HumanInterventionDTO[]>([]);
  const [metrics, setMetrics] = useState<HumanInterventionMetrics>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [reasonFilter, setReasonFilter] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [q, m] = await Promise.all([
        agentApi.humanInterventionQueue({
          status: statusFilter || undefined,
          severity: severityFilter || undefined,
          reason: reasonFilter || undefined,
        }),
        agentApi.humanInterventionMetrics(),
      ]);
      setRows(q);
      setMetrics(m);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load the queue.");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, severityFilter, reasonFilter]);

  // Near-real-time: refresh on filter change + poll every 15s.
  useEffect(() => {
    setLoading(true);
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [load]);

  async function act(id: string, fn: () => Promise<unknown>) {
    setBusyId(id);
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed.");
    } finally {
      setBusyId(null);
    }
  }

  const cards: Array<[string, number | undefined]> = [
    ["Waiting", metrics.waiting],
    ["Human active", metrics.human_active],
    ["Threats", metrics.threats],
    ["Critical", metrics.critical],
  ];

  return (
    <div className="space-y-4">
      {/* Metrics */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {cards.map(([label, value]) => (
          <div key={label} className="rounded-xl border border-border bg-surface p-3">
            <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">{label}</p>
            <p className="mt-1 text-2xl font-semibold text-ink">{value ?? 0}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
          className="h-9 rounded-lg border border-border bg-surface px-2 text-sm">
          <option value="">All statuses</option>
          {Object.keys(STATUS_LABEL).map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
        </select>
        <select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)}
          className="h-9 rounded-lg border border-border bg-surface px-2 text-sm">
          <option value="">All severities</option>
          {["IMMINENT", "HIGH", "MEDIUM", "LOW", "NONE"].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={reasonFilter} onChange={(e) => setReasonFilter(e.target.value)}
          className="h-9 rounded-lg border border-border bg-surface px-2 text-sm">
          <option value="">All reasons</option>
          {Object.keys(REASON_LABEL).map((r) => <option key={r} value={r}>{REASON_LABEL[r]}</option>)}
        </select>
        <button onClick={() => load()} className="h-9 rounded-lg border border-border bg-surface px-3 text-sm font-medium hover:bg-surface-2">
          Refresh
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-danger/20 bg-danger/10 px-3 py-2 text-sm text-danger">{error}</div>
      )}

      {/* Queue */}
      <div className="overflow-x-auto rounded-xl border border-border bg-surface">
        <table className="min-w-full text-sm">
          <thead className="border-b border-border bg-surface-2 text-left text-xs uppercase tracking-wide text-ink-muted">
            <tr>
              <th className="px-3 py-2">Priority</th>
              <th className="px-3 py-2">Reason</th>
              <th className="px-3 py-2">Customer</th>
              <th className="px-3 py-2">Preview (sanitized)</th>
              <th className="px-3 py-2">Waiting</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Assigned</th>
              <th className="px-3 py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {loading && (
              <tr><td colSpan={8} className="px-3 py-8 text-center text-ink-faint">Loading…</td></tr>
            )}
            {!loading && rows.length === 0 && (
              <tr><td colSpan={8} className="px-3 py-8 text-center text-ink-faint">
                No flagged conversations. 🎉
              </td></tr>
            )}
            {rows.map((r) => (
              <tr key={r.id} className="align-top">
                <td className="px-3 py-2.5">
                  <span className={`inline-block rounded-full border px-2 py-0.5 text-xs font-semibold ${PRIORITY_STYLE[r.internal_priority] ?? PRIORITY_STYLE.NORMAL}`}>
                    {r.internal_priority}
                  </span>
                </td>
                <td className="px-3 py-2.5">
                  <div className="font-medium text-ink">{REASON_LABEL[r.takeover_reason] ?? r.takeover_reason}</div>
                  {r.threat_severity && r.threat_severity !== "NONE" && (
                    <div className="text-xs text-danger">Threat: {r.threat_severity}</div>
                  )}
                  {r.abuse_category && (
                    <div className="text-xs text-ink-faint">{r.abuse_category}</div>
                  )}
                </td>
                <td className="px-3 py-2.5">
                  <div className="font-medium text-ink">{r.customer_name ?? "Customer"}</div>
                  <div className="font-mono text-xs text-ink-faint">{r.masked_phone ?? "—"}</div>
                  {r.market && <div className="text-xs text-ink-faint">{r.market}</div>}
                </td>
                <td className="px-3 py-2.5 max-w-xs">
                  <div className="truncate text-ink-muted" title={r.sanitized_preview ?? ""}>
                    ⚠️ {r.sanitized_preview || "—"}
                  </div>
                  {r.linked_order_id && <div className="text-xs text-ink-faint">Order {r.linked_order_id}</div>}
                  {r.unread_count > 0 && (
                    <span className="mt-1 inline-block rounded-full bg-rose/10 px-2 text-xs font-semibold text-rose-strong">
                      {r.unread_count} unread
                    </span>
                  )}
                </td>
                <td className="px-3 py-2.5 text-ink-muted">{waitingFor(r.flagged_at)}</td>
                <td className="px-3 py-2.5 text-ink-muted">{STATUS_LABEL[r.takeover_status] ?? r.takeover_status}</td>
                <td className="px-3 py-2.5 text-ink-muted">{r.assigned_agent_name ?? r.assigned_agent_id ?? "—"}</td>
                <td className="px-3 py-2.5">
                  <div className="flex justify-end gap-2">
                    {r.takeover_status === "WAITING_FOR_HUMAN" && (
                      <button disabled={busyId === r.id}
                        onClick={() => act(r.id, () => agentApi.claimIntervention(r.id))}
                        className="rounded-lg bg-ink px-2.5 py-1 text-xs font-semibold text-canvas hover:bg-ink/90 disabled:opacity-50">
                        Claim
                      </button>
                    )}
                    <a href={`/admin/conversations/${r.conversation_id}`}
                      className="rounded-lg border border-border px-2.5 py-1 text-xs font-semibold text-ink hover:bg-surface-2">
                      Open
                    </a>
                    {["ASSIGNED", "HUMAN_ACTIVE"].includes(r.takeover_status) && (
                      <button disabled={busyId === r.id}
                        onClick={() => act(r.id, () => agentApi.releaseInterventionToAi(r.id))}
                        className="rounded-lg border border-success/20 bg-success/10 px-2.5 py-1 text-xs font-semibold text-success hover:bg-success/20 disabled:opacity-50">
                        Release to AI
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-ink-faint">
        Auto-refreshes every 15s. Full message text is available inside the conversation view for
        authorized agents; this queue shows a sanitized preview only.
      </p>
    </div>
  );
}
