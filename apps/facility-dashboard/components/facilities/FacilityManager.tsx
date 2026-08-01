"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Check, Loader2, MapPin, Plus } from "lucide-react";
import { SectionCard } from "@/components/shared/SectionCard";
import { BankDetailsSection } from "@/components/facilities/BankDetailsSection";
import { Button } from "@/components/ui/Button";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/states";
import { useAuth } from "@/lib/auth-context";
import { canManageFacility } from "@/lib/roles";
import { facilityApi, type FacilityManageInput, type FacilityProfile } from "@/lib/api-client";

const EMIRATES = [
  "Abu Dhabi", "Dubai", "Sharjah", "Ajman",
  "Umm Al Quwain", "Ras Al Khaimah", "Fujairah",
];
const CAPACITY_UNITS = [
  { value: "orders_per_day", label: "Orders / day" },
  { value: "kg_per_day", label: "Kilograms / day" },
  { value: "pieces_per_day", label: "Pieces / day" },
];
const STATUSES = ["open", "busy", "paused", "closed"];
const STATUS_TONE: Record<string, string> = {
  open: "bg-success/10 text-success",
  busy: "bg-warning/10 text-warning",
  paused: "bg-ink/8 text-ink-muted",
  closed: "bg-danger/10 text-danger",
};

const inputCls =
  "h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none";
const labelCls = "mb-1 block text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint";

type FormState = Record<string, string>;

function toForm(f?: FacilityProfile): FormState {
  const g = (k: string) => (f && f[k] != null ? String(f[k]) : "");
  return {
    name: (f?.name as string) ?? "",
    full_address: g("full_address"),
    area: (f?.area as string) ?? "",
    city: (f?.city as string) ?? "",
    emirate: g("emirate"),
    latitude: g("latitude"),
    longitude: g("longitude"),
    service_radius_km: g("service_radius_km"),
    capacity_daily: g("capacity_daily"),
    capacity_unit: g("capacity_unit") || "orders_per_day",
    operating_status: (f?.operating_status as string) ?? "open",
    notes: g("notes"),
  };
}

function num(v: string): number | undefined {
  const s = v.trim();
  if (s === "") return undefined;
  const n = Number(s);
  return Number.isFinite(n) ? n : undefined;
}

export function FacilityManager() {
  const { role } = useAuth();
  const canManage = canManageFacility(role);
  const qc = useQueryClient();

  const facQ = useQuery({ queryKey: ["facility", "facilities"], queryFn: () => facilityApi.facilities() });
  const catQ = useQuery({ queryKey: ["facility", "service-categories"], queryFn: () => facilityApi.serviceCategories() });

  const facility = facQ.data?.facilities?.[0];
  const categories = catQ.data?.categories ?? [];

  const [editing, setEditing] = useState(false);

  if (facQ.isLoading) return <LoadingState label="Loading your facility…" />;
  if (facQ.isError) {
    return <ErrorState description={(facQ.error as Error)?.message} onRetry={() => facQ.refetch()} />;
  }

  if (!facility && !editing) {
    return (
      <EmptyState
        icon={Building2}
        title="No facility linked yet"
        description="Add your facility so LaundryKhalas can route orders to you. You can update it anytime."
        action={canManage
          ? <Button variant="primary" size="lg" onClick={() => setEditing(true)}><Plus className="h-4 w-4" /> Add facility</Button>
          : undefined}
      />
    );
  }

  if (editing) {
    return (
      <FacilityForm
        facility={facility}
        categories={categories}
        onCancel={() => setEditing(false)}
        onSaved={() => { setEditing(false); qc.invalidateQueries({ queryKey: ["facility"] }); }}
      />
    );
  }

  const f = facility!;
  const status = String(f.operating_status ?? "open");
  const services = (f.service_codes as string[] | undefined) ?? [];
  const catName = (code: string) => categories.find((c) => c.code === code)?.name ?? code;

  return (
    <div className="space-y-5">
      <SectionCard title={String(f.name ?? "Your facility")} icon={Building2}
        action={<span className={`rounded-full px-2.5 py-0.5 text-xxs font-semibold ${STATUS_TONE[status] ?? "bg-ink/8 text-ink-muted"}`}>{status}</span>}>
        <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
          <Info label="Full address" value={f.full_address as string} />
          <Info label="Area / City" value={[f.area, f.city].filter(Boolean).join(" · ")} />
          <Info label="Emirate" value={f.emirate as string} />
          <Info label="Service radius" value={f.service_radius_km != null ? `${f.service_radius_km} km` : ""} />
          <Info label="Capacity" value={f.capacity_daily != null ? `${f.capacity_daily} ${String(f.capacity_unit ?? "").replace(/_/g, " ")}` : ""} />
          <Info label="Accepts orders" value={f.accepts_orders ? "Yes" : "No"} />
        </dl>
        {services.length > 0 && (
          <div className="mt-4">
            <p className={labelCls}>Accepted services</p>
            <div className="flex flex-wrap gap-1.5">
              {services.map((c) => (
                <span key={c} className="rounded-full bg-accent-indigo/12 px-2.5 py-1 text-xs font-medium text-accent-indigo">{catName(c)}</span>
              ))}
            </div>
          </div>
        )}
        {canManage && (
          <div className="mt-5 flex items-center gap-2">
            <Button variant="primary" onClick={() => setEditing(true)}>Edit facility</Button>
            <StatusControl facility={f} onChanged={() => qc.invalidateQueries({ queryKey: ["facility"] })} />
          </div>
        )}
        {!canManage && (
          <p className="mt-4 text-xxs text-ink-faint">Your role can view this facility but not edit it.</p>
        )}
      </SectionCard>

      <BankDetailsSection />
    </div>
  );
}

function Info({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="min-w-0">
      <dt className="text-xxs font-medium uppercase tracking-eyebrow text-ink-faint">{label}</dt>
      <dd className="mt-1 break-words text-sm font-medium text-ink">{value || "—"}</dd>
    </div>
  );
}

function StatusControl({ facility, onChanged }: { facility: FacilityProfile; onChanged: () => void }) {
  const m = useMutation({
    mutationFn: (status: string) => facilityApi.setFacilityStatus(String(facility.id), status),
    onSuccess: onChanged,
  });
  return (
    <select
      className="h-9 rounded-lg border border-border bg-canvas px-3 text-sm text-ink focus:border-rose focus-visible:outline-none"
      value={String(facility.operating_status ?? "open")}
      onChange={(e) => m.mutate(e.target.value)}
      aria-label="Change operating status"
    >
      {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
    </select>
  );
}

function FacilityForm({
  facility, categories, onCancel, onSaved,
}: {
  facility?: FacilityProfile;
  categories: { code: string; name: string }[];
  onCancel: () => void;
  onSaved: () => void;
}) {
  const editing = Boolean(facility);
  const [form, setForm] = useState<FormState>(() => toForm(facility));
  const [services, setServices] = useState<string[]>(
    () => (facility?.service_codes as string[] | undefined) ?? [],
  );
  const [saved, setSaved] = useState(false);
  const set = (k: string, v: string) => setForm((s) => ({ ...s, [k]: v }));
  const toggle = (c: string) => setServices((s) => (s.includes(c) ? s.filter((x) => x !== c) : [...s, c]));

  const mutation = useMutation({
    mutationFn: (payload: FacilityManageInput) =>
      editing ? facilityApi.updateFacility(String(facility!.id), payload) : facilityApi.createFacility(payload),
    onSuccess: () => { setSaved(true); setTimeout(onSaved, 600); },
  });

  useEffect(() => { /* keep form in sync if facility changes */ }, [facility]);

  function validate(): string | null {
    if (!form.name.trim()) return "Facility name is required.";
    const lat = num(form.latitude), lon = num(form.longitude);
    if (lat !== undefined && (lat < -90 || lat > 90)) return "Latitude must be between -90 and 90.";
    if (lon !== undefined && (lon < -180 || lon > 180)) return "Longitude must be between -180 and 180.";
    const r = num(form.service_radius_km);
    if (r !== undefined && r <= 0) return "Service radius must be positive.";
    const cap = num(form.capacity_daily);
    if (cap !== undefined && cap <= 0) return "Capacity must be a positive number.";
    return null;
  }

  const [clientErr, setClientErr] = useState<string | null>(null);
  function submit(e: React.FormEvent) {
    e.preventDefault();
    const v = validate();
    if (v) { setClientErr(v); return; }
    setClientErr(null);
    mutation.mutate({
      name: form.name.trim(),
      full_address: form.full_address.trim() || null,
      area: form.area.trim() || null,
      city: form.city.trim() || null,
      emirate: form.emirate || null,
      latitude: num(form.latitude) ?? null,
      longitude: num(form.longitude) ?? null,
      service_radius_km: num(form.service_radius_km) ?? null,
      capacity_daily: num(form.capacity_daily) ?? null,
      capacity_unit: form.capacity_unit,
      operating_status: form.operating_status,
      notes: form.notes.trim() || null,
      services,
    });
  }

  const err = clientErr ?? (mutation.isError ? (mutation.error as Error).message : null);

  return (
    <SectionCard title={editing ? "Edit facility" : "Add facility"} icon={Building2}>
      <form onSubmit={submit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className={labelCls}>Facility name <span className="text-rose">*</span></label>
            <input className={inputCls} value={form.name} onChange={(e) => set("name", e.target.value)} required />
          </div>
          <div className="sm:col-span-2">
            <label className={labelCls}>Full address</label>
            <input className={inputCls} value={form.full_address} onChange={(e) => set("full_address", e.target.value)} />
          </div>
          <div><label className={labelCls}>Area</label><input className={inputCls} value={form.area} onChange={(e) => set("area", e.target.value)} /></div>
          <div><label className={labelCls}>City</label><input className={inputCls} value={form.city} onChange={(e) => set("city", e.target.value)} /></div>
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
          <div><label className={labelCls}>Latitude</label><input className={inputCls} inputMode="decimal" value={form.latitude} onChange={(e) => set("latitude", e.target.value)} placeholder="-90 to 90" /></div>
          <div><label className={labelCls}>Longitude</label><input className={inputCls} inputMode="decimal" value={form.longitude} onChange={(e) => set("longitude", e.target.value)} placeholder="-180 to 180" /></div>
          <div><label className={labelCls}>Service radius (km)</label><input className={inputCls} inputMode="decimal" value={form.service_radius_km} onChange={(e) => set("service_radius_km", e.target.value)} /></div>
          <div className="grid grid-cols-2 gap-2">
            <div><label className={labelCls}>Capacity</label><input className={inputCls} inputMode="numeric" value={form.capacity_daily} onChange={(e) => set("capacity_daily", e.target.value)} /></div>
            <div>
              <label className={labelCls}>Unit</label>
              <select className={inputCls} value={form.capacity_unit} onChange={(e) => set("capacity_unit", e.target.value)}>
                {CAPACITY_UNITS.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
              </select>
            </div>
          </div>
          <div className="sm:col-span-2">
            <label className={labelCls}>Accepted services</label>
            <div className="flex flex-wrap gap-2 rounded-lg border border-border bg-canvas p-2.5">
              {categories.length === 0 && <span className="text-xs text-ink-faint">No service categories available.</span>}
              {categories.map((c) => {
                const on = services.includes(c.code);
                return (
                  <button type="button" key={c.code} onClick={() => toggle(c.code)}
                    className={`rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${
                      on ? "border-accent-indigo bg-accent-indigo/12 text-accent-indigo" : "border-border text-ink-muted hover:border-border-strong"}`}>
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

        {err && <p className="text-xs font-medium text-danger">{err}</p>}

        <div className="flex items-center gap-2">
          <Button type="submit" variant="primary" size="lg" disabled={mutation.isPending}>
            {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            {saved && <Check className="h-4 w-4" />}
            {editing ? "Save changes" : "Create facility"}
          </Button>
          <Button type="button" variant="ghost" onClick={onCancel} disabled={mutation.isPending}>Cancel</Button>
        </div>
        <p className="flex items-center gap-1.5 text-xxs text-ink-faint">
          <MapPin className="h-3 w-3" /> Internal rates and quality scores are managed by LaundryKhalas and are not shown here.
        </p>
      </form>
    </SectionCard>
  );
}
