"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity, CheckCircle2, Clock, Gauge, AlertTriangle, ClipboardList,
  RotateCcw, Trophy, MapPin, Layers, ArrowRight,
} from "lucide-react";
import { Button } from "@/components/dashboard/ui/Button";
import { Panel, PanelHeader, KpiBand, StatusBadge } from "@/components/dashboard/ui/primitives";
import { StatGrid } from "@/components/dashboard/ui/StatCard";
import { EmptyState, LoadingState } from "@/components/dashboard/ui/states";
import type { KpiStat } from "@/lib/dashboard/types";
import {
  getFacilitiesOverview, getCatalogueCategories,
  EMIRATES, STATUS_TONE,
  type FacilitiesOverview as Overview, type FacilityOverviewCard,
  type CatalogueCategory, type OperatingStatus,
} from "@/lib/dashboard/facilities-api";

const STATUSES: OperatingStatus[] = ["open", "busy", "paused", "closed"];
const PERIODS = [
  { value: 7, label: "Last 7 days" },
  { value: 30, label: "Last 30 days" },
  { value: 90, label: "Last 90 days" },
  { value: 0, label: "All time" },
];
const selectCls =
  "h-9 rounded-lg border border-border bg-canvas px-3 text-sm text-ink focus:border-accent-orange focus-visible:outline-none";

const pct = (v: number | null | undefined) => (v == null ? "—" : `${Math.round(v * 100)}%`);
function dur(s: number | null | undefined): string {
  if (s == null) return "—";
  if (s < 3600) return `${Math.max(1, Math.round(s / 60))}m`;
  if (s < 86400) return `${(s / 3600).toFixed(1)}h`;
  return `${(s / 86400).toFixed(1)}d`;
}

/** A ranked facility row — name (→ detail), location, and a right-aligned metric. */
function RankRow({ rank, f, metric, metricLabel }: {
  rank: number; f: FacilityOverviewCard; metric: string; metricLabel: string;
}) {
  return (
    <li>
      <Link
        href={`/facilities/${f.id}`}
        className="group flex items-center gap-3 rounded-xl border border-border bg-canvas px-3.5 py-2.5 transition-colors hover:border-accent-orange/40 hover:bg-accent-orange/[0.04]"
      >
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-surface-2 text-xxs font-bold text-ink-muted">
          {rank}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-semibold text-ink">{f.name}</span>
            <StatusBadge tone={STATUS_TONE[f.operating_status]} dot>{f.operating_status}</StatusBadge>
          </div>
          <p className="truncate text-xs text-ink-faint">
            {[f.city, f.area].filter(Boolean).join(" · ") || "Location not set"}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <div className="text-sm font-semibold text-accent-orange">{metric}</div>
          <p className="text-xxs uppercase tracking-eyebrow text-ink-faint">{metricLabel}</p>
        </div>
        <ArrowRight className="h-4 w-4 shrink-0 text-ink-faint opacity-0 transition-opacity group-hover:opacity-100" />
      </Link>
    </li>
  );
}

function SectionEmpty({ label }: { label: string }) {
  return <p className="rounded-xl border border-dashed border-border px-4 py-6 text-center text-sm text-ink-faint">{label}</p>;
}

export function FacilitiesOverview() {
  const [data, setData] = useState<Overview | null>(null);
  const [categories, setCategories] = useState<CatalogueCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [city, setCity] = useState("");
  const [emirate, setEmirate] = useState("");
  const [status, setStatus] = useState("");
  const [service, setService] = useState("");
  const [days, setDays] = useState(30);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      setData(await getFacilitiesOverview({ city, emirate, status, service, days }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load facility insights.");
    } finally {
      setLoading(false);
    }
  }, [city, emirate, status, service, days]);

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [load]);

  useEffect(() => {
    getCatalogueCategories().then(setCategories).catch(() => setCategories([]));
  }, []);

  const anyFilter = Boolean(city || emirate || status || service) || days !== 30;
  const resetFilters = () => { setCity(""); setEmirate(""); setStatus(""); setService(""); setDays(30); };

  const k = data?.kpis;
  const kpiStats: KpiStat[] = k
    ? [
        { label: "Active facilities", value: String(k.active_facilities), tone: "success", hint: `of ${k.total_facilities} total` },
        { label: "Orders completed", value: String(k.orders_completed), tone: "rose" },
        { label: "Avg completion", value: dur(k.avg_completion_seconds), tone: "neutral", hint: k.avg_completion_seconds == null ? "no data yet" : "confirm → done" },
        { label: "Avg utilisation", value: pct(k.avg_utilisation), tone: "warning", hint: k.avg_utilisation == null ? "no capacity set" : "load / capacity" },
        { label: "Issues raised", value: String(k.issues_raised), tone: k.issues_raised > 0 ? "warning" : "neutral" },
        { label: "Pending actions", value: String(k.pending_actions), tone: k.pending_actions > 0 ? "danger" : "success" },
      ]
    : [];

  const maxCoverage = Math.max(1, ...(data?.service_coverage ?? []).map((s) => s.facility_count));

  return (
    <div className="space-y-6">
      <p className="max-w-2xl text-sm text-ink-muted">
        Performance, activity and coverage across the partner cleaning network. Metrics are
        computed from live orders, issues and coverage — figures with no backing data yet show as “—”.
      </p>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <input
          className={`${selectCls} min-w-[160px] flex-1`}
          placeholder="Filter by city…"
          value={city}
          onChange={(e) => setCity(e.target.value)}
          aria-label="City filter"
        />
        <select className={selectCls} value={emirate} onChange={(e) => setEmirate(e.target.value)} aria-label="Emirate filter">
          <option value="">All emirates</option>
          {EMIRATES.map((em) => <option key={em} value={em}>{em}</option>)}
        </select>
        <select className={selectCls} value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status filter">
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select className={selectCls} value={service} onChange={(e) => setService(e.target.value)} aria-label="Service filter">
          <option value="">All services</option>
          {categories.map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}
        </select>
        <select className={selectCls} value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label="Period filter">
          {PERIODS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
        </select>
        {anyFilter && (
          <Button variant="ghost" size="sm" onClick={resetFilters}>
            <RotateCcw className="h-3.5 w-3.5" /> Reset
          </Button>
        )}
      </div>

      {loading ? (
        <LoadingState label="Loading facility insights…" />
      ) : error ? (
        <EmptyState title="Could not load insights" description={error} icon={AlertTriangle}
          action={<Button variant="secondary" size="sm" onClick={load}>Retry</Button>} />
      ) : !data ? null : (
        <>
          {/* KPI band */}
          <KpiBand label="Network performance">
            <StatGrid stats={kpiStats} accent="orange" cols="auto" />
          </KpiBand>

          {/* Rankings */}
          <div className="grid gap-5 lg:grid-cols-2">
            <Panel accent="orange" padded={false}>
              <PanelHeader title="Most active facilities" subtitle="By orders in progress" icon={Activity} accent="orange" />
              <div className="p-4 pt-0">
                {data.most_active_facilities.length === 0 ? (
                  <SectionEmpty label="No facilities with active orders." />
                ) : (
                  <ul className="space-y-2">
                    {data.most_active_facilities.map((f, i) => (
                      <RankRow key={f.id} rank={i + 1} f={f} metric={String(f.in_progress)} metricLabel="active" />
                    ))}
                  </ul>
                )}
              </div>
            </Panel>

            <Panel accent="orange" padded={false}>
              <PanelHeader title="Most completed orders" subtitle="In the selected period" icon={CheckCircle2} accent="orange" />
              <div className="p-4 pt-0">
                {data.most_completed_facilities.length === 0 ? (
                  <SectionEmpty label="No completed orders in this period." />
                ) : (
                  <ul className="space-y-2">
                    {data.most_completed_facilities.map((f, i) => (
                      <RankRow key={f.id} rank={i + 1} f={f} metric={String(f.completed_period)} metricLabel="completed" />
                    ))}
                  </ul>
                )}
              </div>
            </Panel>
          </div>

          {/* Standout by city */}
          <Panel accent="orange" padded={false}>
            <PanelHeader title="Standout facility by city" subtitle="Strongest facility in each city, by completed orders" icon={Trophy} accent="orange" />
            <div className="p-4 pt-0">
              {data.standout_by_city.length === 0 ? (
                <SectionEmpty label="No city data yet." />
              ) : (
                <div className="grid gap-2 sm:grid-cols-2">
                  {data.standout_by_city.map((f) => (
                    <Link key={f.id + f.city} href={`/facilities/${f.id}`}
                      className="group flex items-center justify-between gap-3 rounded-xl border border-border bg-canvas px-3.5 py-3 transition-colors hover:border-accent-orange/40 hover:bg-accent-orange/[0.04]">
                      <div className="min-w-0">
                        <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-eyebrow text-ink-faint">
                          <MapPin className="h-3 w-3" /> {f.city}
                        </p>
                        <p className="truncate text-sm font-semibold text-ink">{f.name}</p>
                      </div>
                      <div className="shrink-0 text-right">
                        <div className="text-sm font-semibold text-accent-orange">{f.completed_period}</div>
                        <p className="text-xxs uppercase tracking-eyebrow text-ink-faint">
                          {f.completion_rate == null ? "completed" : `${pct(f.completion_rate)} rate`}
                        </p>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </Panel>

          {/* Attention + Service coverage */}
          <div className="grid gap-5 lg:grid-cols-2">
            <Panel accent="orange" padded={false}>
              <PanelHeader title="Facilities needing attention" subtitle="Delays, open issues, actions or capacity gaps" icon={AlertTriangle} accent="orange" />
              <div className="p-4 pt-0">
                {data.attention_facilities.length === 0 ? (
                  <SectionEmpty label="Nothing needs attention. 🎉" />
                ) : (
                  <ul className="space-y-2">
                    {data.attention_facilities.map((f) => (
                      <li key={f.id}>
                        <Link href={`/facilities/${f.id}`}
                          className="group flex items-start justify-between gap-3 rounded-xl border border-border bg-canvas px-3.5 py-2.5 transition-colors hover:border-accent-orange/40 hover:bg-accent-orange/[0.04]">
                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="truncate text-sm font-semibold text-ink">{f.name}</span>
                              <StatusBadge tone={STATUS_TONE[f.operating_status]} dot>{f.operating_status}</StatusBadge>
                            </div>
                            <div className="mt-1 flex flex-wrap gap-1.5">
                              {(f.reasons ?? []).map((r) => (
                                <span key={r} className="rounded-full bg-warning/12 px-2 py-0.5 text-xxs font-medium text-warning">{r}</span>
                              ))}
                            </div>
                          </div>
                          <ClipboardList className="h-4 w-4 shrink-0 text-ink-faint" />
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </Panel>

            <Panel accent="orange" padded={false}>
              <PanelHeader title="Service coverage" subtitle="Facilities offering each service (gaps = 0)" icon={Layers} accent="orange" />
              <div className="space-y-2 p-4 pt-0">
                {data.service_coverage.length === 0 ? (
                  <SectionEmpty label="No services configured." />
                ) : (
                  data.service_coverage.map((s) => (
                    <div key={s.service_code} className="flex items-center gap-3">
                      <span className="w-32 shrink-0 truncate text-sm text-ink" title={s.name}>{s.name}</span>
                      <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-2">
                        <div
                          className={`h-full rounded-full ${s.facility_count === 0 ? "bg-danger/40" : "bg-accent-orange"}`}
                          style={{ width: `${Math.round((s.facility_count / maxCoverage) * 100)}%` }}
                        />
                      </div>
                      <span className={`w-6 shrink-0 text-right text-sm font-semibold ${s.facility_count === 0 ? "text-danger" : "text-ink"}`}>
                        {s.facility_count}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}
