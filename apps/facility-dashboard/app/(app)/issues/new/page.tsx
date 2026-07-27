"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { facilityApi, type RaiseIssuePayload } from "@/lib/api-client";
import { SettingsHeader } from "@/components/settings/SettingsHeader";
import { SectionCard } from "@/components/shared/SectionCard";
import { Button } from "@/components/ui/Button";
import { LoadingState } from "@/components/ui/states";

const ISSUE_TYPES = [
  { value: "delay", label: "Delay" },
  { value: "damage", label: "Damage" },
  { value: "missing", label: "Missing item" },
  { value: "quality", label: "Quality concern" },
  { value: "other", label: "Other" },
];

const PRIORITIES = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "urgent", label: "Urgent" },
];

function NewIssueForm() {
  const router = useRouter();
  const qc = useQueryClient();
  const search = useSearchParams();
  const presetOrder = search.get("order") ?? "";

  const [form, setForm] = useState({
    issue_type: "delay",
    related_order_id: presetOrder,
    priority: "medium",
    message: "",
  });
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (payload: RaiseIssuePayload) => facilityApi.createIssue(payload),
    onSuccess: (issue) => {
      qc.invalidateQueries({ queryKey: ["facility", "issues"] });
      router.replace(issue?.id ? `/issues/${issue.id}` : "/issues");
    },
    onError: (e: unknown) => setError(e instanceof Error ? e.message : "Could not submit the issue."),
  });

  return (
    <div className="lk-enter space-y-5">
      <SettingsHeader title="Report an issue" description="Raise a concern with the operations team." />

      <SectionCard>
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-ink-muted">Issue type</span>
              <select
                value={form.issue_type}
                onChange={(e) => setForm((f) => ({ ...f, issue_type: e.target.value }))}
                className="h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink focus:border-rose focus-visible:outline-none"
              >
                {ISSUE_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-ink-muted">Priority</span>
              <select
                value={form.priority}
                onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value }))}
                className="h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink focus:border-rose focus-visible:outline-none"
              >
                {PRIORITIES.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label className="block">
            <span className="mb-1 block text-xs font-medium text-ink-muted">Related order (optional)</span>
            <input
              value={form.related_order_id}
              onChange={(e) => setForm((f) => ({ ...f, related_order_id: e.target.value }))}
              placeholder="Order ID"
              className="h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none"
            />
          </label>

          <label className="block">
            <span className="mb-1 block text-xs font-medium text-ink-muted">Message</span>
            <textarea
              value={form.message}
              onChange={(e) => setForm((f) => ({ ...f, message: e.target.value }))}
              rows={5}
              placeholder="Describe what happened…"
              className="w-full rounded-lg border border-border bg-canvas px-3 py-2.5 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none"
            />
          </label>

          {error && (
            <p className="rounded-lg border border-danger/30 bg-danger/8 px-3 py-2 text-xs font-medium text-danger">
              {error}
            </p>
          )}

          <div className="flex gap-2">
            <Button
              variant="primary"
              size="lg"
              disabled={!form.message.trim() || mutation.isPending}
              onClick={() =>
                mutation.mutate({
                  issue_type: form.issue_type,
                  message: form.message.trim(),
                  priority: form.priority,
                  related_order_id: form.related_order_id || undefined,
                })
              }
            >
              {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Submit issue
            </Button>
            <Button variant="ghost" size="lg" onClick={() => router.back()}>
              Cancel
            </Button>
          </div>
        </div>
      </SectionCard>
    </div>
  );
}

export default function NewIssuePage() {
  return (
    <Suspense fallback={<LoadingState label="Loading…" />}>
      <NewIssueForm />
    </Suspense>
  );
}
