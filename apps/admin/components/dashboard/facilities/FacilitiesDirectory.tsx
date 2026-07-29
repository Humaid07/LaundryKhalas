"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Plus, MapPin, Gauge, Layers, Clock, RotateCcw, Search, Factory, ArrowRight,
} from "lucide-react";
import { Button } from "@/components/dashboard/ui/Button";
import { StatusBadge } from "@/components/dashboard/ui/primitives";
import { StatGrid } from "@/components/dashboard/ui/StatCard";
import { KpiBand } from "@/components/dashboard/ui/primitives";
import { EmptyState, LoadingState } from "@/components/dashboard/ui/states";
import type { KpiStat } from "@/lib/dashboard/types";
import {
  listFacilities, setFacilityStatus, getCatalogueCategories,
  EMIRATES, STATUS_TONE,
  type Facility, type FacilitySummary, type CatalogueCategory, type OperatingStatus,
} from "@/lib/dashboard/facilities-api";
import { FacilityFormDialog } from "./FacilityFormDialog";

const STATUSES: OperatingStatus[] = ["open", "busy", "paused", "closed"];
const selectCls =
  "h-9 rounded-lg border border-border bg-canvas px-3 text-sm text-ink focus:border-rose focus-visible:outline-none";

function fmtUnit(u?: string | null): string {
  if (u === "kg_per_day") return "kg/day";
  if (u === "pieces_per_day") return "pcs/day";
  return "orders/day";
}

export function FacilitiesDirectory() {
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [summary, setSummary] = useState<FacilitySummary | null>(null);
  const [categories, setCategories] = useState<CatalogueCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [emirate, setEmirate] = useState("");
  const [service, setService] = useState("");

  const [dialog, setDialog] = useState<{ mode: "create" } | { mode: "edit"; facility: Facility } | null>(null);

  const catName = useMemo(() => {
    const m: Record<string, string> = {};
    categories.forEach((c) => { m[c.code] = c.name; });
    return m;
  }, [categories]);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const res = await listFacilities({ search, status, emirate, service });
      setFacilities(res.facilities);
      setSummary(res.summary);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load facilities.");
    } finally {
      setLoading(false);
    }
  }, [search, status, emirate, service]);

  // Debounced reload whenever a filter changes.
  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [load]);

  useEffect(() => {
    getCatalogueCategories().then(setCategories).catch(() => setCategories([]));
  }, []);

  const anyFilter = Boolean(search || status || emirate || service);
  const resetFilters = () => { setSearch(""); setStatus(""); setEmirate(""); setService(""); };

  const summaryStats: KpiStat[] = summary
    ? [
        { label: "Facilities", value: String(summary.total), tone: "rose" },
        { label: "Open", value: String(summary.open), tone: "success" },
        { label: "Busy", value: String(summary.busy), tone: "warning" },
        { label: "Paused", value: String(summary.paused), tone: "neutral" },
        { label: "Closed", value: String(summary.closed), tone: "danger" },
      ]
    : [];

  async function changeStatus(f: Facility, next: OperatingStatus) {
    // optimistic
    setFacilities((cur) => cur.map((x) => (x.id === f.id ? { ...x, operating_status: next } : x)));
    try {
      await setFacilityStatus(f.id, next);
      load();
    } catch {
      load(); // revert to server truth on failure
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="max-w-xl text-sm text-ink-muted">
          Onboard and manage partner cleaning facilities. Facilities created here or in the partner
          portal share this central directory.
        </p>
        <Button variant="primary" onClick={() => setDialog({ mode: "create" })}>
          <Plus className="h-4 w-4" /> Add facility
        </Button>
      </div>

      {summary && (
        <KpiBand label="Network status">
          <StatGrid stats={summaryStats} accent="orange" cols="auto" />
        </KpiBand>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[200px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
          <input
            className={`${selectCls} w-full pl-9`}
            placeholder="Search name, code or area…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select className={selectCls} value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status filter">
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select className={selectCls} value={emirate} onChange={(e) => setEmirate(e.target.value)} aria-label="Emirate filter">
          <option value="">All emirates</option>
          {EMIRATES.map((em) => <option key={em} value={em}>{em}</option>)}
        </select>
        <select className={selectCls} value={service} onChange={(e) => setService(e.target.value)} aria-label="Accepted-service filter">
          <option value="">All services</option>
          {categories.map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}
        </select>
        {anyFilter && (
          <Button variant="ghost" size="sm" onClick={resetFilters}>
            <RotateCcw className="h-3.5 w-3.5" /> Reset
          </Button>
        )}
      </div>

      {/* Content */}
      {loading ? (
        <LoadingState label="Loading facilities…" />
      ) : error ? (
        <EmptyState
          icon={Factory}
          title="Couldn't load facilities"
          description={error}
          action={<Button variant="secondary" size="sm" onClick={load}>Retry</Button>}
        />
      ) : facilities.length === 0 ? (
        <EmptyState
          icon={Factory}
          title={anyFilter ? "No facilities match these filters" : "No facilities onboarded yet"}
          description={anyFilter
            ? "Try clearing the filters to see the full network."
            : "Add your first partner cleaning facility to start routing orders."}
          action={anyFilter
            ? <Button variant="secondary" size="sm" onClick={resetFilters}>Clear filters</Button>
            : <Button variant="primary" size="sm" onClick={() => setDialog({ mode: "create" })}><Plus className="h-4 w-4" /> Add facility</Button>}
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {facilities.map((f) => (
            <FacilityCard
              key={f.id}
              facility={f}
              catName={catName}
              onStatus={(next) => changeStatus(f, next)}
              onEdit={() => setDialog({ mode: "edit", facility: f })}
            />
          ))}
        </div>
      )}

      {dialog && (
        <FacilityFormDialog
          facility={dialog.mode === "edit" ? dialog.facility : undefined}
          services={dialog.mode === "edit" ? dialog.facility.service_codes : undefined}
          categories={categories}
          onClose={() => setDialog(null)}
          onSaved={() => { setDialog(null); load(); }}
        />
      )}
    </div>
  );
}

function FacilityCard({
  facility: f, catName, onStatus, onEdit,
}: {
  facility: Facility;
  catName: Record<string, string>;
  onStatus: (s: OperatingStatus) => void;
  onEdit: () => void;
}) {
  const loc = [f.area, f.city, f.emirate].filter(Boolean).join(" · ") || "—";
  const services = f.service_codes ?? [];
  return (
    <div className="flex flex-col rounded-2xl border border-border bg-surface p-4 shadow-card transition-all duration-200 hover:border-border-strong hover:shadow-raised">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="truncate font-display text-sm font-semibold text-ink">{f.name}</h3>
          <p className="mt-0.5 truncate font-mono text-xxs text-ink-faint">{f.code}</p>
        </div>
        <StatusBadge tone={STATUS_TONE[f.operating_status]}>{f.operating_status}</StatusBadge>
      </div>

      <p className="mt-2 flex items-center gap-1.5 text-xs text-ink-muted">
        <MapPin className="h-3.5 w-3.5 shrink-0 text-ink-faint" /> <span className="truncate">{loc}</span>
      </p>

      <div className="mt-3 grid grid-cols-2 gap-2 text-xxs text-ink-muted">
        <span className="inline-flex items-center gap-1.5"><Layers className="h-3.5 w-3.5 text-ink-faint" />
          {f.capacity_daily != null ? `${f.capacity_daily} ${fmtUnit(f.capacity_unit)}` : "Capacity —"}</span>
        <span className="inline-flex items-center gap-1.5"><MapPin className="h-3.5 w-3.5 text-ink-faint" />
          {f.service_radius_km != null ? `${f.service_radius_km} km radius` : "Radius —"}</span>
        <span className="inline-flex items-center gap-1.5"><Clock className="h-3.5 w-3.5 text-ink-faint" />
          {f.open_days != null ? `Open ${f.open_days}/7 days` : "Hours not set"}</span>
        <span className="inline-flex items-center gap-1.5"><Gauge className="h-3.5 w-3.5 text-ink-faint" />
          {f.quality_score != null ? `Quality ${f.quality_score}` : "Not scored"}</span>
      </div>

      {services.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {services.slice(0, 4).map((code) => (
            <span key={code} className="rounded-full bg-accent-orange/12 px-2 py-0.5 text-xxs font-medium text-accent-orange">
              {catName[code] ?? code}
            </span>
          ))}
          {services.length > 4 && (
            <span className="rounded-full bg-ink/8 px-2 py-0.5 text-xxs text-ink-muted">+{services.length - 4}</span>
          )}
        </div>
      )}

      <div className="mt-3 flex items-center justify-between gap-2 border-t border-border/60 pt-3">
        <span className="text-xxs text-ink-faint">
          {f.onboarding_source === "partner_portal" ? "Partner-added" : "Admin-added"}
        </span>
        <div className="flex items-center gap-1.5">
          <select
            className="h-7 rounded-md border border-border bg-canvas px-1.5 text-xxs text-ink-muted focus:border-rose focus-visible:outline-none"
            value={f.operating_status}
            onChange={(e) => onStatus(e.target.value as OperatingStatus)}
            aria-label="Change status"
          >
            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <Button variant="ghost" size="sm" onClick={onEdit}>Edit</Button>
          <Link
            href={`/facilities/${f.id}`}
            className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-accent-orange hover:bg-accent-orange/10"
          >
            View <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </div>
    </div>
  );
}
