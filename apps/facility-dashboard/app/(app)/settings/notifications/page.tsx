"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus, Bell } from "lucide-react";
import { facilityApi, type FacilityNotificationContact } from "@/lib/api-client";
import { SettingsHeader } from "@/components/settings/SettingsHeader";
import { SectionCard } from "@/components/shared/SectionCard";
import { Switch } from "@/components/ui/Switch";
import { Button } from "@/components/ui/Button";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/states";
import { cn } from "@/lib/utils";

/** The notification types a contact can subscribe to, in display order. */
const TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: "new_order_assigned", label: "New orders" },
  { value: "order_status_updated", label: "Order status updates" },
  { value: "driver_assigned", label: "Driver assigned" },
  { value: "sla_risk", label: "SLA risk" },
  { value: "issue_response", label: "Issue responses" },
  { value: "internal_issue_reply", label: "Issue replies" },
  { value: "payout_update", label: "Payout updates" },
  { value: "daily_summary", label: "Daily summary" },
];

const TYPE_LABELS: Record<string, string> = {
  // Legacy aliases kept so older payloads still render friendly.
  new_order: "New orders",
  order_update: "Order updates",
  issue: "Issues",
  payout: "Payouts",
  ...Object.fromEntries(TYPE_OPTIONS.map((t) => [t.value, t.label])),
};

const DEFAULT_TYPES = ["new_order_assigned", "sla_risk"];

export default function NotificationsSettingsPage() {
  const qc = useQueryClient();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["facility", "settings", "notifications"],
    queryFn: () => facilityApi.getNotificationSettings(),
  });

  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState<{ name: string; target: string; types: string[] }>({
    name: "",
    target: "",
    types: DEFAULT_TYPES,
  });

  const toggleType = (value: string) =>
    setForm((f) => ({
      ...f,
      types: f.types.includes(value)
        ? f.types.filter((t) => t !== value)
        : [...f.types, value],
    }));

  const addMutation = useMutation({
    mutationFn: (payload: Partial<FacilityNotificationContact>) =>
      facilityApi.addNotificationContact(payload),
    onSuccess: () => {
      setAdding(false);
      setForm({ name: "", target: "", types: DEFAULT_TYPES });
      qc.invalidateQueries({ queryKey: ["facility", "settings", "notifications"] });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      facilityApi.updateNotificationContact(id, { enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["facility", "settings", "notifications"] }),
  });

  const contacts = data ?? [];

  return (
    <div className="lk-enter space-y-5">
      <SettingsHeader
        title="Notifications"
        description="Where alerts about your facility are sent."
        action={
          <Button variant="primary" size="md" onClick={() => setAdding((v) => !v)}>
            <Plus className="h-4 w-4" /> Add contact
          </Button>
        }
      />

      {adding && (
        <SectionCard title="New contact">
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Contact name"
                className="h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none"
              />
              <input
                value={form.target}
                onChange={(e) => setForm((f) => ({ ...f, target: e.target.value }))}
                placeholder="Mobile number"
                className="h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none"
              />
            </div>
            <div>
              <p className="mb-2 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">
                Alert types
              </p>
              <div className="flex flex-wrap gap-2">
                {TYPE_OPTIONS.map((t) => {
                  const on = form.types.includes(t.value);
                  return (
                    <button
                      key={t.value}
                      type="button"
                      aria-pressed={on}
                      onClick={() => toggleType(t.value)}
                      className={cn(
                        "rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors",
                        on
                          ? "border-rose/30 bg-rose/12 text-rose"
                          : "border-border bg-surface text-ink-muted hover:border-border-strong hover:text-ink",
                      )}
                    >
                      {t.label}
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                variant="primary"
                size="md"
                disabled={!form.name.trim() || addMutation.isPending}
                onClick={() =>
                  addMutation.mutate({
                    name: form.name.trim(),
                    channel: "whatsapp",
                    masked_target: form.target,
                    types: form.types,
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
          </div>
        </SectionCard>
      )}

      {isLoading ? (
        <LoadingState label="Loading contacts…" />
      ) : isError ? (
        <ErrorState description="Could not load notification settings." onRetry={() => refetch()} />
      ) : contacts.length === 0 ? (
        <EmptyState icon={Bell} title="No contacts yet" description="Add a mobile contact to receive alerts." />
      ) : (
        <SectionCard>
          <ul className="divide-y divide-border/60">
            {contacts.map((c, i) => (
              <li key={c.id ?? i} className="flex items-center justify-between gap-3 py-3.5 first:pt-0 last:pb-0">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-ink">{c.name ?? "Contact"}</p>
                  <p className="truncate text-xs text-ink-muted">
                    {c.masked_target ?? "—"}
                    {c.types && c.types.length > 0
                      ? ` · ${c.types.map((t) => TYPE_LABELS[t] ?? t).join(", ")}`
                      : ""}
                  </p>
                </div>
                {c.id && (
                  <Switch
                    checked={c.enabled !== false}
                    onChange={(on) => toggleMutation.mutate({ id: c.id!, enabled: on })}
                  />
                )}
              </li>
            ))}
          </ul>
        </SectionCard>
      )}
    </div>
  );
}
