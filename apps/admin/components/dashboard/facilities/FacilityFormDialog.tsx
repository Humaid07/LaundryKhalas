"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { Loader2, X } from "lucide-react";
import { Button } from "@/components/dashboard/ui/Button";
import {
  createFacility, updateFacility,
  EMIRATES, CAPACITY_UNITS,
  type Facility, type FacilityInput, type CatalogueCategory,
  type OperatingStatus, type CapacityUnit,
} from "@/lib/dashboard/facilities-api";

const STATUSES: OperatingStatus[] = ["open", "busy", "paused", "closed"];

const labelCls = "mb-1.5 block text-xxs font-semibold uppercase tracking-eyebrow text-ink-muted";
const baseInput =
  "h-11 w-full rounded-xl border bg-canvas px-3.5 text-sm text-ink placeholder:text-ink-faint transition-colors focus-visible:outline-none focus-visible:ring-2";
const inputOk =
  "border-border focus:border-accent-orange focus-visible:ring-accent-orange/25";
const inputBad =
  "border-danger/60 focus:border-danger focus-visible:ring-danger/25";

type FormState = Record<string, string>;
type FieldErrors = Record<string, string>;

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

/** A titled group of fields, so the form reads as sections instead of one long grid. */
function Section({ step, title, hint, children }: { step: number; title: string; hint?: string; children: ReactNode }) {
  return (
    <section className="border-t border-border/70 pt-5 first:border-0 first:pt-0">
      <div className="mb-3.5">
        <div className="flex items-center gap-2.5">
          <span className="flex h-5 w-5 items-center justify-center rounded-md bg-accent-orange/15 text-xxs font-bold text-accent-orange">
            {step}
          </span>
          <h3 className="font-display text-sm font-semibold text-ink">{title}</h3>
        </div>
        {hint && <p className="mt-1 pl-[1.9rem] text-xs text-ink-faint">{hint}</p>}
      </div>
      <div className="grid gap-x-4 gap-y-3.5 sm:grid-cols-2">{children}</div>
    </section>
  );
}

/**
 * Create / edit facility dialog (internal admin). Includes quality_score +
 * accepted services. Client-side validation mirrors the backend
 * (services.facility_admin) so bad input is caught before the request, but the
 * backend remains the authority.
 *
 * Bank details and operating hours are intentionally NOT in the create form —
 * they are managed post-create on the facility detail page via their own
 * (admin-scoped) flows, so this modal never fake-saves unsupported fields.
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
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const set = (k: string, v: string) =>
    setForm((f) => ({ ...f, [k]: v }));
  const clearFieldError = (k: string) =>
    setFieldErrors((fe) => (fe[k] ? { ...fe, [k]: "" } : fe));
  const toggleService = (code: string) =>
    setSelectedServices((s) => (s.includes(code) ? s.filter((c) => c !== code) : [...s, code]));

  function validate(): FieldErrors {
    const fe: FieldErrors = {};
    if (!form.name.trim()) fe.name = "Facility name is required.";
    const lat = num(form.latitude), lon = num(form.longitude);
    if (lat !== undefined && (lat < -90 || lat > 90)) fe.latitude = "Must be between -90 and 90.";
    if (lon !== undefined && (lon < -180 || lon > 180)) fe.longitude = "Must be between -180 and 180.";
    const radius = num(form.service_radius_km);
    if (radius !== undefined && radius <= 0) fe.service_radius_km = "Must be a positive number.";
    const cap = num(form.capacity_daily);
    if (cap !== undefined && cap <= 0) fe.capacity_daily = "Must be a positive number.";
    const q = num(form.quality_score);
    if (q !== undefined && (q < 0 || q > 100)) fe.quality_score = "Must be between 0 and 100.";
    return fe;
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const fe = validate();
    if (Object.keys(fe).length > 0) {
      setFieldErrors(fe);
      setErr("Please fix the highlighted fields.");
      return;
    }
    setBusy(true); setErr(null); setFieldErrors({});
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

  // input className + optional inline error for a field
  const inp = (field: string) => `${baseInput} ${fieldErrors[field] ? inputBad : inputOk}`;
  const FieldError = ({ field }: { field: string }) =>
    fieldErrors[field] ? <p className="mt-1 text-xs font-medium text-danger">{fieldErrors[field]}</p> : null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink/75 p-4 backdrop-blur-md sm:items-center"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={editing ? "Edit facility" : "Add facility"}
        className="my-6 flex max-h-[88vh] w-full flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-pop ring-1 ring-black/10 sm:max-w-[960px]"
      >
        {/* Header */}
        <header className="flex shrink-0 items-start justify-between gap-4 border-b border-border px-6 py-4">
          <div>
            <h2 className="font-display text-lg font-semibold text-ink">
              {editing ? "Edit facility" : "Add facility"}
            </h2>
            <p className="mt-0.5 text-sm text-ink-muted">
              {editing
                ? "Update this partner facility’s details, coverage, capacity and services."
                : "Register a partner facility, define its service area, capacity and operating details."}
            </p>
          </div>
          <button
            onClick={onClose}
            className="-mr-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-ink-muted transition-colors hover:bg-surface-2 hover:text-ink"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        {/* Body (scrolls) */}
        <form id="facility-form" onSubmit={submit} className="flex-1 space-y-6 overflow-y-auto px-6 py-5">
          <Section step={1} title="Basic details">
            <div className="sm:col-span-2">
              <label className={labelCls}>Facility name <span className="text-danger">*</span></label>
              <input className={inp("name")} value={form.name}
                onChange={(e) => { set("name", e.target.value); clearFieldError("name"); }} required />
              <FieldError field="name" />
            </div>
            <div className="sm:col-span-2">
              <label className={labelCls}>Full address</label>
              <input className={inp("full_address")} value={form.full_address}
                onChange={(e) => set("full_address", e.target.value)}
                placeholder="Building, street, landmark…" />
            </div>
            <div>
              <label className={labelCls}>Area</label>
              <input className={inp("area")} value={form.area} onChange={(e) => set("area", e.target.value)} placeholder="e.g. Al Barsha" />
            </div>
            <div>
              <label className={labelCls}>City</label>
              <input className={inp("city")} value={form.city} onChange={(e) => set("city", e.target.value)} placeholder="e.g. Dubai" />
            </div>
            <div>
              <label className={labelCls}>Emirate</label>
              <select className={inp("emirate")} value={form.emirate} onChange={(e) => set("emirate", e.target.value)}>
                <option value="">Select emirate…</option>
                {EMIRATES.map((em) => <option key={em} value={em}>{em}</option>)}
              </select>
            </div>
            <div>
              <label className={labelCls}>Operating status</label>
              <select className={inp("operating_status")} value={form.operating_status} onChange={(e) => set("operating_status", e.target.value)}>
                {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </Section>

          <Section step={2} title="Location & coverage" hint="Used to route pickups to the nearest facility within its service radius.">
            <div>
              <label className={labelCls}>Latitude</label>
              <input className={inp("latitude")} inputMode="decimal" value={form.latitude}
                onChange={(e) => { set("latitude", e.target.value); clearFieldError("latitude"); }} placeholder="-90 to 90" />
              <FieldError field="latitude" />
            </div>
            <div>
              <label className={labelCls}>Longitude</label>
              <input className={inp("longitude")} inputMode="decimal" value={form.longitude}
                onChange={(e) => { set("longitude", e.target.value); clearFieldError("longitude"); }} placeholder="-180 to 180" />
              <FieldError field="longitude" />
            </div>
            <div>
              <label className={labelCls}>Service radius (km)</label>
              <input className={inp("service_radius_km")} inputMode="decimal" value={form.service_radius_km}
                onChange={(e) => { set("service_radius_km", e.target.value); clearFieldError("service_radius_km"); }} placeholder="e.g. 10" />
              <FieldError field="service_radius_km" />
            </div>
          </Section>

          <Section step={3} title="Operations">
            <div>
              <label className={labelCls}>Daily capacity</label>
              <input className={inp("capacity_daily")} inputMode="numeric" value={form.capacity_daily}
                onChange={(e) => { set("capacity_daily", e.target.value); clearFieldError("capacity_daily"); }} placeholder="e.g. 120" />
              <FieldError field="capacity_daily" />
            </div>
            <div>
              <label className={labelCls}>Capacity unit</label>
              <select className={inp("capacity_unit")} value={form.capacity_unit} onChange={(e) => set("capacity_unit", e.target.value)}>
                {CAPACITY_UNITS.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
              </select>
            </div>
            <div className="sm:col-span-2">
              <label className={labelCls}>Quality score (0–100) · internal</label>
              <input className={`${inp("quality_score")} sm:max-w-[240px]`} inputMode="decimal" value={form.quality_score}
                onChange={(e) => { set("quality_score", e.target.value); clearFieldError("quality_score"); }} placeholder="Not evaluated" />
              <FieldError field="quality_score" />
            </div>
          </Section>

          <Section step={4} title="Accepted services" hint="Which catalogue categories this facility can fulfil.">
            <div className="sm:col-span-2">
              <div className="flex flex-wrap gap-2 rounded-xl border border-border bg-canvas p-3">
                {categories.length === 0 && <span className="text-xs text-ink-faint">No catalogue categories loaded.</span>}
                {categories.map((c) => {
                  const on = selectedServices.includes(c.code);
                  return (
                    <button
                      type="button"
                      key={c.code}
                      onClick={() => toggleService(c.code)}
                      aria-pressed={on}
                      className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                        on ? "border-accent-orange bg-accent-orange/15 text-accent-orange"
                           : "border-border text-ink-muted hover:border-border-strong hover:text-ink"
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
              <textarea className={`${baseInput} ${inputOk} h-24 py-2.5`} value={form.notes}
                onChange={(e) => set("notes", e.target.value)} placeholder="Internal notes (optional)" />
            </div>
          </Section>
        </form>

        {/* Footer (pinned) */}
        <div className="flex shrink-0 items-center justify-between gap-3 border-t border-border bg-surface-2/40 px-6 py-4">
          <p className="text-xs font-medium text-danger">{err ?? ""}</p>
          <div className="flex items-center gap-2">
            <Button type="button" variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
            <Button
              type="submit"
              form="facility-form"
              variant="primary"
              disabled={busy}
              className="bg-accent-orange text-white hover:bg-accent-orange/90 hover:shadow-none"
            >
              {busy && <Loader2 className="h-4 w-4 animate-spin" />}
              {busy ? "Saving…" : editing ? "Save changes" : "Add facility"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
