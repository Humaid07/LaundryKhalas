"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, UserPlus, Users } from "lucide-react";
import { facilityApi, type FacilityTeamMember } from "@/lib/api-client";
import { SettingsHeader } from "@/components/settings/SettingsHeader";
import { SectionCard } from "@/components/shared/SectionCard";
import { Button } from "@/components/ui/Button";
import { StatusBadge } from "@/components/ui/primitives";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/states";

const ROLE_OPTIONS = [
  { value: "facility_manager", label: "Manager" },
  { value: "facility_staff", label: "Staff" },
  { value: "facility_driver", label: "Driver / Runner" },
];

function roleLabel(role?: string) {
  return ROLE_OPTIONS.find((r) => r.value === role)?.label ?? (role ?? "Member");
}

export default function TeamsSettingsPage() {
  const qc = useQueryClient();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["facility", "settings", "team"],
    queryFn: () => facilityApi.getTeam(),
  });

  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState<{ name: string; role: string; phone: string }>({
    name: "",
    role: "facility_staff",
    phone: "",
  });

  const addMutation = useMutation({
    mutationFn: (payload: Partial<FacilityTeamMember>) => facilityApi.addTeamMember(payload),
    onSuccess: () => {
      setAdding(false);
      setForm({ name: "", role: "facility_staff", phone: "" });
      qc.invalidateQueries({ queryKey: ["facility", "settings", "team"] });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      facilityApi.updateTeamMember(id, { active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["facility", "settings", "team"] }),
  });

  const members = data ?? [];

  return (
    <div className="lk-enter space-y-5">
      <SettingsHeader
        title="Team"
        description="People who work orders at your facility."
        action={
          <Button variant="primary" size="md" onClick={() => setAdding((v) => !v)}>
            <UserPlus className="h-4 w-4" /> Add member
          </Button>
        }
      />

      {adding && (
        <SectionCard title="New team member">
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-3">
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
                placeholder="Mobile number"
                className="h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none"
              />
            </div>
            <div className="flex gap-2">
              <Button
                variant="primary"
                size="md"
                disabled={!form.name.trim() || addMutation.isPending}
                onClick={() =>
                  addMutation.mutate({ name: form.name.trim(), role: form.role, masked_phone: form.phone })
                }
              >
                {addMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Add
              </Button>
              <Button variant="ghost" size="md" onClick={() => setAdding(false)}>
                Cancel
              </Button>
            </div>
          </div>
        </SectionCard>
      )}

      {isLoading ? (
        <LoadingState label="Loading team…" />
      ) : isError ? (
        <ErrorState description="Could not load your team." onRetry={() => refetch()} />
      ) : members.length === 0 ? (
        <EmptyState icon={Users} title="No team members yet" description="Add your first member to get started." />
      ) : (
        <SectionCard>
          <ul className="divide-y divide-border/60">
            {members.map((m, i) => (
              <li key={m.id ?? i} className="flex items-center justify-between gap-3 py-3.5 first:pt-0 last:pb-0">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="truncate text-sm font-medium text-ink">{m.name ?? "Member"}</p>
                    <StatusBadge tone={m.active === false ? "neutral" : "success"} dot={false}>
                      {m.active === false ? "Inactive" : "Active"}
                    </StatusBadge>
                  </div>
                  <p className="text-xs text-ink-muted">
                    {roleLabel(m.role)}
                    {m.masked_phone ? ` · ${m.masked_phone}` : ""}
                  </p>
                </div>
                {m.id && (
                  <Button
                    variant={m.active === false ? "secondary" : "danger"}
                    size="sm"
                    disabled={toggleMutation.isPending}
                    onClick={() => toggleMutation.mutate({ id: m.id!, active: m.active === false })}
                  >
                    {m.active === false ? "Reactivate" : "Deactivate"}
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </SectionCard>
      )}
    </div>
  );
}
