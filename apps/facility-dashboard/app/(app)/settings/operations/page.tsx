"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Check } from "lucide-react";
import { facilityApi } from "@/lib/api-client";
import { SettingsHeader } from "@/components/settings/SettingsHeader";
import { SectionCard } from "@/components/shared/SectionCard";
import { Switch } from "@/components/ui/Switch";
import { Button } from "@/components/ui/Button";
import { LoadingState, ErrorState } from "@/components/ui/states";

interface OpsSettings {
  accepting_orders?: boolean;
  quality_check_enabled?: boolean;
  daily_capacity?: number | null;
  handoff_window?: string | null;
  [key: string]: unknown;
}

export default function OperationsSettingsPage() {
  const qc = useQueryClient();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["facility", "settings", "operations"],
    queryFn: () => facilityApi.getOperationsSettings() as Promise<OpsSettings>,
  });

  const [form, setForm] = useState<OpsSettings>({});
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  const mutation = useMutation({
    mutationFn: (patch: OpsSettings) => facilityApi.updateOperationsSettings(patch),
    onSuccess: () => {
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      qc.invalidateQueries({ queryKey: ["facility"] });
    },
  });

  return (
    <div className="lk-enter space-y-5">
      <SettingsHeader title="Operations" description="Control how orders flow into your facility." />

      {isLoading ? (
        <LoadingState label="Loading operations…" />
      ) : isError ? (
        <ErrorState description="Could not load operations settings." onRetry={() => refetch()} />
      ) : (
        <>
          <SectionCard>
            <div className="divide-y divide-border/60">
              <div className="flex items-center justify-between gap-4 py-3.5 first:pt-0">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-ink">Accepting orders</p>
                  <p className="text-xs text-ink-muted">Turn off to pause new pickups to your facility.</p>
                </div>
                <Switch
                  checked={!!form.accepting_orders}
                  onChange={(on) => setForm((f) => ({ ...f, accepting_orders: on }))}
                />
              </div>
              <div className="flex items-center justify-between gap-4 py-3.5">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-ink">Quality check step</p>
                  <p className="text-xs text-ink-muted">Require a QC stage before orders are marked ready.</p>
                </div>
                <Switch
                  checked={!!form.quality_check_enabled}
                  onChange={(on) => setForm((f) => ({ ...f, quality_check_enabled: on }))}
                />
              </div>
            </div>
          </SectionCard>

          <SectionCard title="Capacity & handoff">
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="mb-1 block text-xs font-medium text-ink-muted">Daily capacity (orders)</span>
                <input
                  type="number"
                  min={0}
                  value={form.daily_capacity ?? ""}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, daily_capacity: e.target.value === "" ? null : Number(e.target.value) }))
                  }
                  className="h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink focus:border-rose focus-visible:outline-none"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-xs font-medium text-ink-muted">Handoff window</span>
                <input
                  value={form.handoff_window ?? ""}
                  onChange={(e) => setForm((f) => ({ ...f, handoff_window: e.target.value }))}
                  placeholder="e.g. 18:00 – 20:00"
                  className="h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none"
                />
              </label>
            </div>
          </SectionCard>

          <div className="flex items-center gap-3">
            <Button variant="primary" size="lg" disabled={mutation.isPending} onClick={() => mutation.mutate(form)}>
              {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Save changes
            </Button>
            {saved && (
              <span className="inline-flex items-center gap-1 text-xs font-medium text-success">
                <Check className="h-3.5 w-3.5" /> Saved
              </span>
            )}
          </div>
        </>
      )}
    </div>
  );
}
