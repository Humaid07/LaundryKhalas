"use client";

import { useCallback, useEffect, useState } from "react";
import { Factory, Clock, Coins, ShieldCheck, ScrollText, Loader2, Trash2 } from "lucide-react";
import { DetailPageShell, DetailColumns } from "@/components/dashboard/minimal/DetailPageShell";
import { DetailSectionCard, Field, FieldGrid } from "@/components/dashboard/minimal/DetailSectionCard";
import { StatusBadge } from "@/components/dashboard/ui/primitives";
import { Button } from "@/components/dashboard/ui/Button";
import { LoadingState, EmptyState } from "@/components/dashboard/ui/states";
import {
  getFacility, getFacilityRates, setFacilityRate, deleteFacilityRate,
  setFacilityTimings, setFacilityStatus, getCatalogueCategories,
  STATUS_TONE,
  type FacilityDetail, type FacilityTiming, type FacilityRate,
  type CatalogueCategory, type OperatingStatus, FacilitiesApiError,
} from "@/lib/dashboard/facilities-api";
import { FacilityFormDialog } from "./FacilityFormDialog";
import { BankDetailsCard } from "./BankDetailsCard";
import { FacilityRatingsSection, DriverRatingsSection } from "./RatingsSection";

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const STATUSES: OperatingStatus[] = ["open", "busy", "paused", "closed"];
const inputCls = "h-8 rounded-md border border-border bg-canvas px-2 text-xs text-ink focus:border-rose focus-visible:outline-none";

export function FacilityDetailPage({ facilityId }: { facilityId: string }) {
  const [detail, setDetail] = useState<FacilityDetail | null>(null);
  const [categories, setCategories] = useState<CatalogueCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      setDetail(await getFacility(facilityId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load facility.");
    } finally {
      setLoading(false);
    }
  }, [facilityId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { getCatalogueCategories().then(setCategories).catch(() => setCategories([])); }, []);

  if (loading) return <LoadingState label="Loading facility…" />;
  if (error || !detail) {
    return (
      <EmptyState icon={Factory} title="Facility not found" description={error ?? undefined}
        action={<Button variant="secondary" size="sm" onClick={load}>Retry</Button>} />
    );
  }

  const f = detail.facility;
  const catName = (code: string) => categories.find((c) => c.code === code)?.name ?? code;

  async function changeStatus(next: OperatingStatus) {
    try { await setFacilityStatus(facilityId, next); load(); } catch { /* keep */ }
  }

  return (
    <>
      <DetailPageShell
        backHref="/facilities/directory"
        backLabel="Facilities"
        eyebrow="Facility"
        title={f.name}
        status={<StatusBadge tone={STATUS_TONE[f.operating_status]}>{f.operating_status}</StatusBadge>}
        actions={
          <>
            <select className={`${inputCls} h-9`} value={f.operating_status}
              onChange={(e) => changeStatus(e.target.value as OperatingStatus)} aria-label="Change status">
              {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <Button variant="primary" onClick={() => setEditing(true)}>Edit facility</Button>
          </>
        }
      >
        <DetailColumns
          main={
            <>
              <DetailSectionCard title="Profile" icon={Factory}>
                <FieldGrid cols={3}>
                  <Field label="Code" value={f.code} mono />
                  <Field label="Emirate" value={f.emirate} />
                  <Field label="Onboarding" value={f.onboarding_source === "partner_portal" ? "Partner portal" : "Admin dashboard"} />
                  <Field label="Full address" value={f.full_address} />
                  <Field label="Area" value={f.area} />
                  <Field label="City" value={f.city} />
                  <Field label="Latitude" value={f.latitude != null ? String(f.latitude) : null} mono />
                  <Field label="Longitude" value={f.longitude != null ? String(f.longitude) : null} mono />
                  <Field label="Service radius" value={f.service_radius_km != null ? `${f.service_radius_km} km` : null} />
                  <Field label="Capacity" value={f.capacity_daily != null ? `${f.capacity_daily}` : null} />
                  <Field label="Capacity unit" value={f.capacity_unit} />
                  <Field label="Accepts orders" value={f.accepts_orders ? "Yes" : "No"} />
                </FieldGrid>
                {f.notes && <p className="mt-4 rounded-lg bg-surface-2 px-3 py-2 text-xs text-ink-muted">{f.notes}</p>}
              </DetailSectionCard>

              <DetailSectionCard title="Accepted services" icon={Factory}>
                {detail.services.length === 0 ? (
                  <p className="text-xs text-ink-muted">No services configured. Edit the facility to add accepted services.</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {detail.services.map((code) => (
                      <span key={code} className="rounded-full bg-accent-orange/12 px-2.5 py-1 text-xs font-medium text-accent-orange">
                        {catName(code)}
                      </span>
                    ))}
                  </div>
                )}
              </DetailSectionCard>

              <OperatingHoursCard facilityId={facilityId} initial={detail.timings} onSaved={load} />

              <RatesCard facilityId={facilityId} categories={categories} />

              <FacilityRatingsSection facilityId={facilityId} />

              <DriverRatingsSection facilityId={facilityId} />
            </>
          }
          sidebar={
            <>
              <DetailSectionCard title="Quality & status" icon={ShieldCheck}>
                <FieldGrid cols={2}>
                  <Field label="Quality score" value={f.quality_score != null ? `${f.quality_score} / 100` : "Not evaluated"} />
                  <Field label="Market" value={f.market} />
                </FieldGrid>
                <p className="mt-3 text-xxs text-ink-faint">
                  Quality score and internal rates are internal-only and never shown to partners.
                </p>
              </DetailSectionCard>

              <BankDetailsCard facilityId={facilityId} />

              <DetailSectionCard title="Recent activity" icon={ScrollText}>
                {detail.audit.length === 0 ? (
                  <p className="text-xs text-ink-muted">No changes recorded yet.</p>
                ) : (
                  <ul className="space-y-2.5">
                    {detail.audit.slice(0, 8).map((a) => (
                      <li key={a.id} className="flex items-center justify-between gap-2 text-xs">
                        <span className="text-ink">{a.action.replace(/_/g, " ")}</span>
                        <span className="text-xxs text-ink-faint">{a.actor_type}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </DetailSectionCard>
            </>
          }
        />
      </DetailPageShell>

      {editing && (
        <FacilityFormDialog
          facility={f}
          services={detail.services}
          categories={categories}
          onClose={() => setEditing(false)}
          onSaved={() => { setEditing(false); load(); }}
        />
      )}
    </>
  );
}

/* ------------------------------ Operating hours ----------------------------- */
function OperatingHoursCard({
  facilityId, initial, onSaved,
}: { facilityId: string; initial: FacilityTiming[]; onSaved: () => void }) {
  const seed = (): FacilityTiming[] =>
    DAYS.map((_, d) => initial.find((t) => t.day_of_week === d) ?? {
      day_of_week: d, opens_at: "", closes_at: "", is_closed: false, is_24h: false,
    });
  const [rows, setRows] = useState<FacilityTiming[]>(seed);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);

  const upd = (d: number, patch: Partial<FacilityTiming>) =>
    setRows((r) => r.map((x) => (x.day_of_week === d ? { ...x, ...patch } : x)));

  async function save() {
    setBusy(true);
    try {
      await setFacilityTimings(facilityId, rows.map((r) => ({
        day_of_week: r.day_of_week,
        opens_at: r.is_closed || r.is_24h ? null : (r.opens_at || null),
        closes_at: r.is_closed || r.is_24h ? null : (r.closes_at || null),
        is_closed: !!r.is_closed,
        is_24h: !!r.is_24h,
      })));
      setSaved(true); setTimeout(() => setSaved(false), 2000);
      onSaved();
    } finally { setBusy(false); }
  }

  return (
    <DetailSectionCard title="Operating hours" icon={Clock}
      action={<Button variant="secondary" size="sm" onClick={save} disabled={busy}>
        {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}{saved ? "Saved" : "Save hours"}
      </Button>}>
      <div className="space-y-2">
        {rows.map((r) => (
          <div key={r.day_of_week} className="flex flex-wrap items-center gap-2">
            <span className="w-10 text-xs font-medium text-ink">{DAYS[r.day_of_week]}</span>
            <input type="time" className={inputCls} value={r.opens_at ?? ""} disabled={r.is_closed || r.is_24h}
              onChange={(e) => upd(r.day_of_week, { opens_at: e.target.value })} />
            <span className="text-ink-faint">–</span>
            <input type="time" className={inputCls} value={r.closes_at ?? ""} disabled={r.is_closed || r.is_24h}
              onChange={(e) => upd(r.day_of_week, { closes_at: e.target.value })} />
            <label className="ml-1 inline-flex items-center gap-1 text-xxs text-ink-muted">
              <input type="checkbox" checked={!!r.is_24h} onChange={(e) => upd(r.day_of_week, { is_24h: e.target.checked })} /> 24h
            </label>
            <label className="inline-flex items-center gap-1 text-xxs text-ink-muted">
              <input type="checkbox" checked={!!r.is_closed} onChange={(e) => upd(r.day_of_week, { is_closed: e.target.checked })} /> Closed
            </label>
          </div>
        ))}
      </div>
    </DetailSectionCard>
  );
}

/* -------------------------------- Internal rates ---------------------------- */
function RatesCard({ facilityId, categories }: { facilityId: string; categories: CatalogueCategory[] }) {
  const [rates, setRates] = useState<FacilityRate[] | null>(null);
  const [adminOnly, setAdminOnly] = useState(false);
  const [svc, setSvc] = useState("");
  const [rate, setRate] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await getFacilityRates(facilityId);
      setRates(res.rates); setAdminOnly(false);
    } catch (e) {
      if (e instanceof FacilitiesApiError && e.status === 403) { setAdminOnly(true); setRates([]); }
      else setRates([]);
    }
  }, [facilityId]);

  useEffect(() => { load(); }, [load]);

  async function add() {
    if (!svc || !rate) return;
    setBusy(true); setErr(null);
    try {
      await setFacilityRate(facilityId, { service_code: svc, rate: Number(rate), currency: "AED" });
      setSvc(""); setRate(""); load();
    } catch (e) { setErr(e instanceof Error ? e.message : "Could not save rate."); }
    finally { setBusy(false); }
  }
  async function remove(code: string) {
    try { await deleteFacilityRate(facilityId, code); load(); } catch { /* keep */ }
  }

  if (adminOnly) {
    return (
      <DetailSectionCard title="Internal rates" icon={Coins}>
        <p className="text-xs text-ink-muted">Internal rates are administrator-only. Ask an admin to view or edit facility rates.</p>
      </DetailSectionCard>
    );
  }

  return (
    <DetailSectionCard title="Internal rates" icon={Coins}>
      <p className="mb-3 text-xxs text-ink-faint">Internal-only. Never returned to partners or shown to customers.</p>
      {rates && rates.length > 0 && (
        <div className="mb-3 overflow-x-auto">
          <table className="w-full text-sm">
            <tbody>
              {rates.map((r) => (
                <tr key={r.service_code} className="border-b border-border/50">
                  <td className="py-1.5 text-ink">{categories.find((c) => c.code === r.service_code)?.name ?? r.service_code}</td>
                  <td className="py-1.5 text-right font-mono text-ink">{r.currency} {r.rate}</td>
                  <td className="py-1.5 pl-2 text-right">
                    <button onClick={() => remove(r.service_code)} className="text-ink-faint hover:text-danger" aria-label="Delete rate">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <select className={inputCls} value={svc} onChange={(e) => setSvc(e.target.value)}>
          <option value="">Service…</option>
          {categories.map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}
        </select>
        <input className={`${inputCls} w-24`} inputMode="decimal" placeholder="Rate (AED)" value={rate} onChange={(e) => setRate(e.target.value)} />
        <Button variant="secondary" size="sm" onClick={add} disabled={busy || !svc || !rate}>
          {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />} Set rate
        </Button>
      </div>
      {err && <p className="mt-2 text-xs text-danger">{err}</p>}
    </DetailSectionCard>
  );
}
