"use client";

import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Truck, Plus, Loader2 } from "lucide-react";
import {
  facilityApi,
  type CreateDriverPayload,
  type DriverSummary,
} from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { canManageFacility } from "@/lib/roles";
import { MobilePageHeader } from "@/components/shared/MobilePageHeader";
import { SectionCard } from "@/components/shared/SectionCard";
import { Button } from "@/components/ui/Button";
import { DriverCard } from "@/components/drivers/DriverCard";
import {
  DriverTabs,
  matchesDriverFilter,
  type DriverFilter,
} from "@/components/drivers/DriverTabs";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/states";
import { cn } from "@/lib/utils";

const ROLE_OPTIONS = [
  { value: "driver", label: "Driver" },
  { value: "runner", label: "Runner" },
  { value: "pickup_partner", label: "Pickup Partner" },
];

const SUMMARY_TILES: { key: keyof DriverSummary; label: string; tone: string }[] = [
  { key: "free", label: "Free", tone: "text-success" },
  { key: "on_job", label: "On Job", tone: "text-info" },
  { key: "issues", label: "Issues", tone: "text-danger" },
];

export default function DriversPage() {
  const qc = useQueryClient();
  const { role } = useAuth();
  const canManage = canManageFacility(role);

  const [filter, setFilter] = useState<DriverFilter>("all");
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ name: "", role: "driver", phone: "", area: "", vehicle: "" });

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["facility", "drivers"],
    queryFn: () => facilityApi.drivers(),
  });

  const addMutation = useMutation({
    mutationFn: (payload: CreateDriverPayload) => facilityApi.createDriver(payload),
    onSuccess: () => {
      setAdding(false);
      setForm({ name: "", role: "driver", phone: "", area: "", vehicle: "" });
      qc.invalidateQueries({ queryKey: ["facility", "drivers"] });
    },
  });

  const summary = data?.summary;

  const filtered = useMemo(
    () => (data?.drivers ?? []).filter((d) => matchesDriverFilter(d, filter)),
    [data, filter],
  );

  return (
    <div className="lk-enter space-y-5">
      <MobilePageHeader
        title="Drivers"
        description="Your pickup and delivery team, live."
        action={
          canManage ? (
            <Button variant="primary" size="md" onClick={() => setAdding((v) => !v)}>
              <Plus className="h-4 w-4" /> Add driver
            </Button>
          ) : undefined
        }
      />

      {/* Summary tiles */}
      <div className="grid grid-cols-3 divide-x divide-ink/5 overflow-hidden rounded-2xl border border-border/70 bg-surface shadow-card">
        {SUMMARY_TILES.map((t) => (
          <div key={t.key} className="min-w-0 px-4 py-4 text-center sm:text-left">
            <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">{t.label}</p>
            <p className={cn("mt-1.5 font-mono text-2xl font-semibold leading-none tnum", t.tone)}>
              {summary ? (summary[t.key] as number) ?? 0 : "—"}
            </p>
          </div>
        ))}
      </div>

      {canManage && adding && (
        <SectionCard title="New driver">
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Full name"
                className="h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none"
              />
              <select
                value={form.role}
                onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
                className="h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink focus:border-rose focus-visible:outline-none"
              >
                {ROLE_OPTIONS.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
              <input
                value={form.phone}
                onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
                placeholder="Mobile number (E.164)"
                className="h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none"
              />
              <input
                value={form.area}
                onChange={(e) => setForm((f) => ({ ...f, area: e.target.value }))}
                placeholder="Area (optional)"
                className="h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none"
              />
              <input
                value={form.vehicle}
                onChange={(e) => setForm((f) => ({ ...f, vehicle: e.target.value }))}
                placeholder="Vehicle type (optional)"
                className="h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none sm:col-span-2"
              />
            </div>
            <div className="flex gap-2">
              <Button
                variant="primary"
                size="md"
                disabled={!form.name.trim() || addMutation.isPending}
                onClick={() =>
                  addMutation.mutate({
                    name: form.name.trim(),
                    role: form.role,
                    phone_e164: form.phone.trim() || undefined,
                    area: form.area.trim() || undefined,
                    vehicle_type: form.vehicle.trim() || undefined,
                  })
                }
              >
                {addMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Add
              </Button>
              <Button variant="ghost" size="md" onClick={() => setAdding(false)}>
                Cancel
              </Button>
            </div>
            {addMutation.isError && (
              <p className="text-xs font-medium text-danger">
                {addMutation.error instanceof Error ? addMutation.error.message : "Could not add driver."}
              </p>
            )}
          </div>
        </SectionCard>
      )}

      {/* Sticky filter row */}
      <div className="sticky top-14 z-20 -mx-4 border-b border-border/60 bg-canvas/90 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6">
        <DriverTabs value={filter} onChange={setFilter} summary={summary} />
      </div>

      {isLoading ? (
        <LoadingState label="Loading drivers…" />
      ) : isError ? (
        <ErrorState description="Could not load drivers." onRetry={() => refetch()} />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Truck}
          title="No drivers here"
          description={filter === "all" ? "Add a driver to get started." : "Nothing matches this view right now."}
        />
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {filtered.map((d) => (
            <DriverCard key={d.id} driver={d} />
          ))}
        </div>
      )}
    </div>
  );
}
