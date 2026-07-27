"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Loader2, Check, Tag, Info } from "lucide-react";
import { facilityApi } from "@/lib/api-client";
import { formatMoney } from "@/lib/formatters";
import { SettingsHeader } from "@/components/settings/SettingsHeader";
import { SectionCard } from "@/components/shared/SectionCard";
import { Button } from "@/components/ui/Button";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/states";
import type { FacilityPriceRow } from "@/lib/api-client";

export default function PriceSettingsPage() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["facility", "settings", "prices"],
    queryFn: () => facilityApi.getPrices(),
  });

  const [form, setForm] = useState({ item: "", requested_price: "", reason: "" });
  const [submitted, setSubmitted] = useState(false);

  const mutation = useMutation({
    mutationFn: () =>
      facilityApi.requestPriceChange({
        item: form.item || undefined,
        requested_price: form.requested_price ? Number(form.requested_price) : undefined,
        reason: form.reason.trim(),
      }),
    onSuccess: () => {
      setSubmitted(true);
      setForm({ item: "", requested_price: "", reason: "" });
      setTimeout(() => setSubmitted(false), 3000);
    },
  });

  const rows = data ?? [];
  const columns: Column<FacilityPriceRow>[] = [
    { key: "item", header: "Item", primary: true, cell: (r) => r.item ?? "—" },
    { key: "category", header: "Category", cell: (r) => r.category ?? "—" },
    { key: "unit", header: "Unit", cell: (r) => r.unit ?? "—" },
    {
      key: "price",
      header: "Rate",
      align: "right",
      cell: (r) => (r.price != null ? formatMoney(r.price, r.currency ?? "AED") : "—"),
    },
  ];

  return (
    <div className="lk-enter space-y-5">
      <SettingsHeader title="Price List" description="Catalogue rates for your facility." />

      <div className="flex items-start gap-2 rounded-xl border border-info/25 bg-info/8 px-3.5 py-3 text-xs text-ink-muted">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-info" />
        <p>
          Rates are set by LaundryKhalas and cannot be edited here. To propose a change, submit a
          request below and the operations team will review it.
        </p>
      </div>

      <SectionCard title="Catalogue rates" icon={Tag}>
        {isLoading ? (
          <LoadingState label="Loading rates…" />
        ) : isError ? (
          <ErrorState description="Could not load rates." onRetry={() => refetch()} />
        ) : rows.length === 0 ? (
          <EmptyState icon={Tag} title="No rates published yet" description="Rates will appear once configured." />
        ) : (
          <DataTable columns={columns} rows={rows} rowKey={(r, i) => `${r.item ?? "row"}-${i}`} />
        )}
      </SectionCard>

      <SectionCard title="Request a rate change">
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-ink-muted">Item (optional)</span>
              <input
                value={form.item}
                onChange={(e) => setForm((f) => ({ ...f, item: e.target.value }))}
                placeholder="e.g. Shirt — Press"
                className="h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-ink-muted">Proposed rate (optional)</span>
              <input
                type="number"
                min={0}
                step="0.5"
                value={form.requested_price}
                onChange={(e) => setForm((f) => ({ ...f, requested_price: e.target.value }))}
                placeholder="AED"
                className="h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none"
              />
            </label>
          </div>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-ink-muted">Reason</span>
            <textarea
              value={form.reason}
              onChange={(e) => setForm((f) => ({ ...f, reason: e.target.value }))}
              rows={3}
              placeholder="Explain why this rate should change…"
              className="w-full rounded-lg border border-border bg-canvas px-3 py-2.5 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none"
            />
          </label>
          <div className="flex items-center gap-3">
            <Button
              variant="primary"
              size="lg"
              disabled={!form.reason.trim() || mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Submit request
            </Button>
            {submitted && (
              <span className="inline-flex items-center gap-1 text-xs font-medium text-success">
                <Check className="h-3.5 w-3.5" /> Request submitted for review
              </span>
            )}
          </div>
        </div>
      </SectionCard>
    </div>
  );
}
