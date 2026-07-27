"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Check } from "lucide-react";
import { facilityApi, type FacilityProfile } from "@/lib/api-client";
import { SettingsHeader } from "@/components/settings/SettingsHeader";
import { SectionCard } from "@/components/shared/SectionCard";
import { Button } from "@/components/ui/Button";
import { LoadingState, ErrorState } from "@/components/ui/states";

export default function ProfileSettingsPage() {
  const qc = useQueryClient();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["facility", "settings", "profile"],
    queryFn: () => facilityApi.getProfileSettings(),
  });

  const [form, setForm] = useState<Partial<FacilityProfile>>({});
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data) setForm({ name: data.name, area: data.area, city: data.city });
  }, [data]);

  const mutation = useMutation({
    mutationFn: (patch: Partial<FacilityProfile>) => facilityApi.updateProfileSettings(patch),
    onSuccess: () => {
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      qc.invalidateQueries({ queryKey: ["facility"] });
    },
  });

  return (
    <div className="lk-enter space-y-5">
      <SettingsHeader title="Facility Profile" description="Your facility's basic details." />

      {isLoading ? (
        <LoadingState label="Loading profile…" />
      ) : isError ? (
        <ErrorState description="Could not load your profile." onRetry={() => refetch()} />
      ) : (
        <SectionCard>
          <div className="space-y-4">
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-ink-muted">Facility name</span>
              <input
                value={form.name ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                className="h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink focus:border-rose focus-visible:outline-none"
              />
            </label>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="mb-1 block text-xs font-medium text-ink-muted">Area</span>
                <input
                  value={form.area ?? ""}
                  onChange={(e) => setForm((f) => ({ ...f, area: e.target.value }))}
                  className="h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink focus:border-rose focus-visible:outline-none"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-xs font-medium text-ink-muted">City</span>
                <input
                  value={form.city ?? ""}
                  onChange={(e) => setForm((f) => ({ ...f, city: e.target.value }))}
                  className="h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink focus:border-rose focus-visible:outline-none"
                />
              </label>
            </div>

            <div className="flex items-center gap-3 pt-1">
              <Button
                variant="primary"
                size="lg"
                disabled={mutation.isPending}
                onClick={() => mutation.mutate(form)}
              >
                {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Save changes
              </Button>
              {saved && (
                <span className="inline-flex items-center gap-1 text-xs font-medium text-success">
                  <Check className="h-3.5 w-3.5" /> Saved
                </span>
              )}
            </div>
          </div>
        </SectionCard>
      )}
    </div>
  );
}
