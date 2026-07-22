"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle, ClipboardList, Clock, MapPin, MessageSquare, Phone,
  RefreshCw, Search, User, X,
} from "lucide-react";
import { Panel, PanelHeader, StatusBadge } from "@/components/dashboard/ui/primitives";
import { StatGrid } from "@/components/dashboard/ui/StatCard";
import { Button } from "@/components/dashboard/ui/Button";
import { EmptyState, LoadingState } from "@/components/dashboard/ui/states";
import { formatCurrency } from "@/lib/dashboard/formatters";
import type { KpiStat } from "@/lib/dashboard/types";
import {
  agentApi, type OrderDTO, type OrderEventDTO, type OrderMetricsSummary,
} from "@/lib/dashboard/whatsapp-agent-api";
import {
  DASHBOARD_STATUS_OPTIONS, ORDER_VIEWS, statusMeta,
} from "@/lib/dashboard/order-status";

const POLL_MS = 15000;

function fmtDateTime(v?: string | null): string {
  if (!v) return "—";
  const d = new Date(v);
  return Number.isNaN(d.getTime())
    ? String(v)
    : d.toLocaleString("en-GB", { timeZone: "Asia/Dubai", dateStyle: "medium", timeStyle: "short" });
}
function fmtDate(v?: string | null): string {
  if (!v) return "—";
  const d = new Date(v);
  return Number.isNaN(d.getTime())
    ? String(v)
    : d.toLocaleDateString("en-GB", { timeZone: "Asia/Dubai", dateStyle: "medium" });
}

/* ------------------------------- Order card -------------------------------- */
function OrderCard({ order, onOpen }: { order: OrderDTO; onOpen: (o: OrderDTO) => void }) {
  const meta = statusMeta(order.status);
  const attn = order.needs_attention;
  return (
    <button
      type="button"
      onClick={() => onOpen(order)}
      className={`group flex flex-col gap-3 rounded-2xl border bg-surface p-4 text-left shadow-card transition hover:border-rose/40 hover:shadow-lg ${
        attn ? "border-danger/40 ring-1 ring-danger/20" : "border-border"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <span className="font-mono text-xs font-semibold text-ink">{order.order_id}</span>
          <p className="mt-0.5 truncate text-sm font-semibold text-ink">
            {order.customer_name ?? "Unknown customer"}
          </p>
        </div>
        <StatusBadge tone={meta.tone}>{order.status_label || meta.label}</StatusBadge>
      </div>

      <div className="grid gap-1.5 text-xs text-ink-muted">
        <span className="flex items-center gap-1.5"><ClipboardList className="h-3 w-3 text-ink-faint" />{order.service_display_name ?? order.service_type ?? "Service pending"}</span>
        <span className="flex items-center gap-1.5"><Clock className="h-3 w-3 text-ink-faint" />{fmtDate(order.pickup_date)}{order.pickup_time ? ` · ${order.pickup_time}` : ""}</span>
        <span className="flex items-center gap-1.5"><MapPin className="h-3 w-3 text-ink-faint" />{[order.pickup_area, order.city].filter(Boolean).join(", ") || "Address pending"}</span>
        {order.pickup_instructions && (
          <span className="flex items-center gap-1.5"><MessageSquare className="h-3 w-3 text-ink-faint" />{order.pickup_instructions}</span>
        )}
        <span className="flex items-center gap-1.5"><Phone className="h-3 w-3 text-ink-faint" />{order.customer_phone ?? "—"}</span>
      </div>

      <div className="flex items-center justify-between border-t border-border pt-2">
        <span className="text-xxs uppercase tracking-wide text-ink-faint">
          {order.source_channel ?? "whatsapp"} · {fmtDateTime(order.created_at)}
        </span>
        {attn && (
          <span className="inline-flex items-center gap-1 text-xxs font-semibold text-danger">
            <AlertTriangle className="h-3 w-3" /> Needs attention
          </span>
        )}
      </div>
    </button>
  );
}

/* ---------------------------- Order detail panel --------------------------- */
function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 border-b border-border py-2 text-xs last:border-0">
      <span className="text-ink-faint">{label}</span>
      <span className="text-right font-medium text-ink">{value || "—"}</span>
    </div>
  );
}

function OrderDetailPanel({ order, onClose, onChanged }: {
  order: OrderDTO; onClose: () => void; onChanged: () => void;
}) {
  const [full, setFull] = useState<OrderDTO>(order);
  const [events, setEvents] = useState<OrderEventDTO[]>([]);
  const [status, setStatus] = useState(order.status);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [detail, evs] = await Promise.all([
          agentApi.getOrder(order.order_id),
          agentApi.getOrderEvents(order.order_id),
        ]);
        if (!alive) return;
        setFull(detail);
        setStatus(detail.status);
        setEvents(evs);
      } catch (e) {
        if (alive) setErr(e instanceof Error ? e.message : "Failed to load order");
      }
    })();
    return () => { alive = false; };
  }, [order.order_id]);

  const meta = statusMeta(full.status);
  const convoId = full.conversation_id;

  async function saveStatus() {
    if (status === full.status) return;
    setSaving(true); setErr(null);
    try {
      const updated = await agentApi.updateOrderStatus(order.order_id, status, "Operations");
      setFull(updated);
      setEvents(await agentApi.getOrderEvents(order.order_id));
      onChanged();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to update status");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={onClose}>
      <aside
        className="flex h-full w-full max-w-lg flex-col overflow-y-auto bg-surface shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="sticky top-0 z-10 flex items-start justify-between gap-3 border-b border-border bg-surface p-4">
          <div className="min-w-0">
            <span className="font-mono text-xs font-semibold text-ink">{full.order_id}</span>
            <p className="truncate text-sm font-semibold text-ink">{full.customer_name ?? "Unknown customer"}</p>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge tone={meta.tone}>{full.status_label || meta.label}</StatusBadge>
            <button onClick={onClose} aria-label="Close" className="rounded-lg p-1 text-ink-faint hover:bg-surface-2 hover:text-ink">
              <X className="h-4 w-4" />
            </button>
          </div>
        </header>

        <div className="space-y-4 p-4">
          {err && <p className="rounded-lg bg-danger/10 px-3 py-2 text-xs text-danger">{err}</p>}

          {convoId && (
            <Link
              href={`/operations/customer-facing?conversationId=${convoId}&orderId=${full.order_id}`}
              className="flex items-center justify-center gap-2 rounded-xl bg-rose px-3 py-2 text-sm font-semibold text-white transition hover:bg-rose/90"
            >
              <MessageSquare className="h-4 w-4" /> Open Chat in Operations
            </Link>
          )}

          <Panel padded className="!rounded-xl">
            <PanelHeader title="Order" />
            <DetailRow label="Service" value={full.service_display_name ?? full.service_type} />
            <DetailRow label="Pickup date" value={fmtDate(full.pickup_date)} />
            <DetailRow label="Pickup time" value={full.pickup_time} />
            <DetailRow label="Address" value={full.pickup_address ?? full.pickup_area} />
            <DetailRow label="Area / City" value={[full.pickup_area, full.city].filter(Boolean).join(", ")} />
            <DetailRow label="Instructions" value={full.pickup_instructions} />
            <DetailRow label="Amount" value={full.amount != null ? formatCurrency(full.amount) : null} />
            <DetailRow label="Source" value={full.source_channel} />
            <DetailRow label="Created" value={fmtDateTime(full.created_at)} />
            <DetailRow label="Updated" value={fmtDateTime(full.updated_at)} />
            <DetailRow label="Human takeover" value={full.human_takeover ? "Active" : "No"} />
          </Panel>

          <Panel padded className="!rounded-xl">
            <PanelHeader title="Customer" />
            <DetailRow label="Name" value={full.customer_name} />
            <DetailRow label="WhatsApp" value={full.customer_phone} />
          </Panel>

          <Panel padded className="!rounded-xl">
            <PanelHeader title="Update status" />
            <div className="flex items-center gap-2">
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="flex-1 rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-ink"
              >
                {[full.status, ...DASHBOARD_STATUS_OPTIONS.filter((s) => s !== full.status)].map((s) => (
                  <option key={s} value={s}>{statusMeta(s).label}</option>
                ))}
              </select>
              <Button size="sm" variant="primary" onClick={saveStatus} disabled={saving || status === full.status}>
                {saving ? "Saving…" : "Update"}
              </Button>
            </div>
          </Panel>

          <Panel padded className="!rounded-xl">
            <PanelHeader title="Order timeline" subtitle={`${events.length} event${events.length === 1 ? "" : "s"}`} />
            {events.length === 0 ? (
              <p className="text-xs text-ink-muted">No events recorded yet.</p>
            ) : (
              <ol className="space-y-2">
                {events.map((e) => (
                  <li key={e.id} className="flex gap-2 text-xs">
                    <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-rose" />
                    <div>
                      <p className="font-medium text-ink">{e.event_type.replace(/_/g, " ")}</p>
                      <p className="text-ink-faint">
                        {e.to_status ? `→ ${statusMeta(e.to_status).label} · ` : ""}
                        {e.actor_type ?? "system"} · {fmtDateTime(e.created_at)}
                      </p>
                      {e.notes && <p className="text-ink-muted">{e.notes}</p>}
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </Panel>
        </div>
      </aside>
    </div>
  );
}

/* ------------------------------- Main section ------------------------------ */
export function OrdersSection() {
  const [view, setView] = useState("all");
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [data, setData] = useState<OrderDTO[]>([]);
  const [total, setTotal] = useState(0);
  const [metrics, setMetrics] = useState<OrderMetricsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<OrderDTO | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);

  const load = useCallback(async (showSpinner = false) => {
    if (showSpinner) setLoading(true);
    try {
      const params = { ...ORDER_VIEWS[view].params, search: debounced || undefined, page_size: 60 };
      const [page, summary] = await Promise.all([
        agentApi.searchOrders(params),
        agentApi.orderMetricsSummary(),
      ]);
      setData(page.orders);
      setTotal(page.total);
      setMetrics(summary);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not reach the backend");
    } finally {
      setLoading(false);
    }
  }, [view, debounced]);

  // Reload on filter change + poll every 15s (near-real-time; refresh always works).
  useEffect(() => {
    load(true);
    const id = setInterval(() => load(false), POLL_MS);
    return () => clearInterval(id);
  }, [load]);

  const metricStats: KpiStat[] = metrics
    ? [
        { label: "New today", value: String(metrics.new_today), tone: "info" },
        { label: "Active", value: String(metrics.active_orders), tone: "info" },
        { label: "Confirmed pickups", value: String(metrics.confirmed_pickups), tone: "plum" },
        { label: "Completed", value: String(metrics.completed), tone: "success" },
        { label: "Cancelled", value: String(metrics.cancelled), tone: "danger" },
        { label: "Needs attention", value: String(metrics.needs_attention), tone: "danger" },
      ]
    : [];

  return (
    <div className="space-y-5">
      {metricStats.length > 0 && <StatGrid stats={metricStats} />}

      <Panel padded={false}>
        <PanelHeader
          title="Orders"
          subtitle={`Live from the WhatsApp agent · ${total} order${total === 1 ? "" : "s"}`}
          className="p-4"
          action={
            <Button size="sm" variant="secondary" onClick={() => load(true)} aria-label="Refresh orders">
              <RefreshCw className="h-3.5 w-3.5" /> Refresh
            </Button>
          }
        />

        <div className="flex flex-wrap items-center gap-2 px-4">
          {Object.entries(ORDER_VIEWS).map(([key, v]) => (
            <button
              key={key}
              onClick={() => setView(key)}
              className={`rounded-full px-3 py-1 text-xs font-semibold transition ${
                view === key ? "bg-rose text-white" : "bg-surface-2 text-ink-muted hover:text-ink"
              }`}
            >
              {v.label}
            </button>
          ))}
          <div className="relative ml-auto">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-faint" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search name, phone, order #"
              className="w-56 rounded-lg border border-border bg-surface-2 py-1.5 pl-8 pr-3 text-xs text-ink placeholder:text-ink-faint"
            />
          </div>
        </div>

        <div className="p-4">
          {loading ? (
            <LoadingState label="Loading orders…" />
          ) : error ? (
            <EmptyState
              icon={AlertTriangle}
              title="Backend unavailable"
              description={error}
              action={<Button size="sm" variant="secondary" onClick={() => load(true)}>Try again</Button>}
            />
          ) : data.length === 0 ? (
            <EmptyState
              icon={ClipboardList}
              title="No orders here yet"
              description="Orders confirmed over WhatsApp appear here automatically."
            />
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {data.map((o) => (
                <OrderCard key={o.id} order={o} onOpen={setSelected} />
              ))}
            </div>
          )}
        </div>
      </Panel>

      {selected && (
        <OrderDetailPanel
          order={selected}
          onClose={() => setSelected(null)}
          onChanged={() => load(false)}
        />
      )}
    </div>
  );
}
