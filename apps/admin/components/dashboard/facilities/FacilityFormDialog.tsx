"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, X } from "lucide-react";
import { Button } from "@/components/dashboard/ui/Button";
import {
  createFacility, updateFacility,
  EMIRATES, CAPACITY_UNITS,
  type Facility, type FacilityInput, type CatalogueCategory,
  type OperatingStatus, type CapacityUnit,
} from "@/lib/dashboard/facilities-api";

const STATUSES: OperatingStatus[] = ["open", "busy", "paused", "closed"];

const inputCls =
  "h-9 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none";
const labelCls = "mb-1 block text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint";

type FormState = Record<string, string>;

function toForm(f?: Facility): FormState {
  return {
    name: f?.name ?? "",
    full_address: f?.full_address ?? "",
    area: f?.area ?? "",
    city: f?.city ?? "",
    emirate: f?.emirate ?? "",
    latitude: f?.latitude != null ? String(f.latitude) : "",
    longitude: f?.longitude != null ? String(f.longitude) : "",
    service_radius_km: f?.service_radius_km != null ? String(f.service_radius_km) : "",
    capacity_daily: f?.capacity_daily != null ? String(f.capacity_daily) : "",
    capacity_unit: (f?.capacity_unit ?? "orders_per_day") as string,
    operating_status: (f?.operating_status ?? "open") as string,
    quality_score: f?.quality_score != null ? String(f.quality_score) : "",
    notes: f?.notes ?? "",
  };
}

function num(v: string): number | undefined {
  const s = v.trim();
  if (s === "") return undefined;
  const n = Number(s);
  return Number.isFinite(n) ? n : undefined;
}

/**
 * Create / edit facility dialog (internal admin). Includes quality_score +
 * accepted services. Client-side validation mirrors the backend
 * (services.facility_admin) so bad input is caught before the request, but the
 * backend remains the authority.
 */
export function FacilityFormDialog({
  facility,
  services,
  categories,
  onClose,
  onSaved,
}: {
  facility?: Facility;              // present → edit mode
  services?: string[];             // current accepted services (edit)
  categories: CatalogueCategory[];
  onClose: () => void;
  onSaved: (f: Facility) => void;
}) {
  const editing = Boolean(facility);
  const [form, setForm] = useState<FormState>(() => toForm(facility));
  const [selectedServices, setSelectedServices] = useState<string[]>(
    () => services ?? facility?.service_codes ?? [],
  );
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));
  const toggleService = (code: string) =>
    setSelectedServices((s) => (s.includes(code) ? s.filter((c) => c !== code) : [...s, code]));

  function validate(): string | null {
    if (!form.name.trim()) return "Facility name is required.";
    const lat = num(form.latitude), lon = num(form.longitude);
    if (lat !== undefined && (lat < -90 || lat > 90)) return "Latitude must be between -90 and 90.";
    if (lon !== undefined && (lon < -180 || lon > 180)) return "Longitude must be between -180 and 180.";
    const radius = num(form.service_radius_km);
    if (radius !== undefined && radius <= 0) return "Service radius must be positive.";
    const cap = num(form.capacity_daily);
    if (cap !== undefined && cap <= 0) return "Capacity must be a positive number.";
    const q = num(form.quality_score);
    if (q !== undefined && (q < 0 || q > 100)) return "Quality score must be between 0 and 100.";
    return null;
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const v = validate();
    if (v) { setErr(v); return; }
    setBusy(true); setErr(null);
    const payload: FacilityInput = {
      name: form.name.trim(),
      full_address: form.full_address.trim() || null,
      area: form.area.trim() || null,
      city: form.city.trim() || null,
      emirate: form.emirate || null,
      latitude: num(form.latitude) ?? null,
      longitude: num(form.longitude) ?? null,
      service_radius_km: num(form.service_radius_km) ?? null,
      capacity_daily: num(form.capacity_daily) ?? null,
      capacity_unit: form.capacity_unit as CapacityUnit,
      operating_status: form.operating_status as OperatingStatus,
      quality_score: num(form.quality_score) ?? null,
      notes: form.notes.trim() || null,
      services: selectedServices,
    };
    try {
      const saved = editing
        ? await updateFacility(facility!.id, payload)
        : await createFacility(payload);
      onSaved(saved);
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Could not save the facility.");
      setBusy(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink/40 p-4 backdrop-blur-sm"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={editing ? "Edit facility" : "Add facility"}
        className="my-8 w-full max-w-2xl rounded-2xl border border-border bg-surface shadow-raised"
      >
        <header className="flex items-center justify-between border-b border-border px-5 py-3.5">
          <h2 className="font-display text-base font-semibold text-ink">
            {editing ? "Edit facility" : "Add facility"}
          </h2>
          <button onClick={onClose} className="rounded-lg p-1 text-ink-muted hover:bg-surface-2 hover:text-ink" aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </header>

        <form onSubmit={submit} className="max-h-[70vh] overflow-y-auto px-5 py-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <label className={labelCls}>Facility name <span className="text-rose">*</span></label>
              <input className={inputCls} value={form.name} onChange={(e) => set("name", e.target.value)} required />
            </div>
            <div className="sm:col-span-2">
              <label className={labelCls}>Full address</label>
              <input className={inputCls} value={form.full_address} onChange={(e) => set("full_address", e.target.value)} />
            </div>
            <div>
              <label className={labelCls}>Area</label>
              <input className={inputCls} value={form.area} onChange={(e) => set("area", e.target.value)} />
            </div>
            <div>
              <label className={labelCls}>City</label>
              <input className={inputCls} value={form.city} onChange={(e) => set("city", e.target.value)} />
            </div>
            <div>
              <label className={labelCls}>Emirate</label>
              <select className={inputCls} value={form.emirate} onChange={(e) => set("emirate", e.target.value)}>
                <option value="">Select emirate…</option>
                {EMIRATES.map((em) => <option key={em} value={em}>{em}</option>)}
              </select>
            </div>
            <div>
              <label className={labelCls}>Operating status</label>
              <select className={inputCls} value={form.operating_status} onChange={(e) => set("operating_status", e.target.value)}>
                {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className={labelCls}>Latitude</label>
              <input className={inputCls} inputMode="decimal" value={form.latitude} onChange={(e) => set("latitude", e.target.value)} placeholder="-90 to 90" />
            </div>
            <div>
              <label className={labelCls}>Longitude</label>
              <input className={inputCls} inputMode="decimal" value={form.longitude} onChange={(e) => set("longitude", e.target.value)} placeholder="-180 to 180" />
            </div>
            <div>
              <label className={labelCls}>Service radius (km)</label>
              <input className={inputCls} inputMode="decimal" value={form.service_radius_km} onChange={(e) => set("service_radius_km", e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className={labelCls}>Capacity</label>
                <input className={inputCls} inputMode="numeric" value={form.capacity_daily} onChange={(e) => set("capacity_daily", e.target.value)} />
              </div>
              <div>
                <label className={labelCls}>Unit</label>
                <select className={inputCls} value={form.capacity_unit} onChange={(e) => set("capacity_unit", e.target.value)}>
                  {CAPACITY_UNITS.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
                </select>
              </div>
            </div>
            <div>
              <label className={labelCls}>Quality score (0–100) · internal</label>
              <input className={inputCls} inputMode="decimal" value={form.quality_score} onChange={(e) => set("quality_score", e.target.value)} placeholder="Not evaluated" />
            </div>
            <div className="sm:col-span-2">
              <label className={labelCls}>Accepted services</label>
              <div className="flex flex-wrap gap-2 rounded-lg border border-border bg-canvas p-2.5">
                {categories.length === 0 && <span className="text-xs text-ink-faint">No catalogue categories loaded.</span>}
                {categories.map((c) => {
                  const on = selectedServices.includes(c.code);
                  return (
                    <button
                      type="button"
                      key={c.code}
                      onClick={() => toggleService(c.code)}
                      className={`rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${
                        on ? "border-accent-orange bg-accent-orange/12 text-accent-orange"
                           : "border-border text-ink-muted hover:border-border-strong"
                      }`}
                    >
                      {c.name}
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="sm:col-span-2">
              <label className={labelCls}>Notes</label>
              <textarea className={`${inputCls} h-20 py-2`} value={form.notes} onChange={(e) => set("notes", e.target.value)} />
            </div>
          </div>

          {err && <p className="mt-3 text-xs font-medium text-danger">{err}</p>}

          <div className="mt-5 flex items-center justify-end gap-2 border-t border-border pt-4">
            <Button type="button" variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
            <Button type="submit" variant="primary" disabled={busy}>
              {busy && <Loader2 className="h-4 w-4 animate-spin" />}
              {editing ? "Save changes" : "Create facility"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
