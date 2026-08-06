"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, BadgeDollarSign } from "lucide-react";
import {
  facilityApi,
  type QuoteRevision,
  type FacilityViewItem,
} from "@/lib/api-client";
import { DetailSectionCard } from "@/components/minimal/DetailSectionCard";
import { StatusBadge } from "@/components/ui/primitives";
import { Button } from "@/components/ui/Button";
import type { Tone } from "@/lib/types";

const STATUS: Record<string, { label: string; tone: Tone }> = {
  pending_ops_review: { label: "Awaiting operations review", tone: "warning" },
  ops_approved: { label: "Approved by operations", tone: "info" },
  customer_pending: { label: "Awaiting customer approval", tone: "warning" },
  customer_approved: { label: "Customer approved", tone: "success" },
  ops_rejected: { label: "Rejected by operations", tone: "danger" },
  customer_rejected: { label: "Customer declined", tone: "danger" },
};

function money(v?: number | null, ccy = "AED") {
  return v == null ? "—" : `${ccy} ${Number(v).toFixed(2)}`;
}

export function QuoteRevisionPanel({
  orderId,
  revisions,
  items,
}: {
  orderId: string;
  revisions: QuoteRevision[];
  items: FacilityViewItem[];
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [itemId, setItemId] = useState("");
  const [fee, setFee] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = useMutation({
    mutationFn: () =>
      facilityApi.submitQuoteRevision(orderId, {
        facility_fee: Number(fee),
        order_item_id: itemId || null,
        reason: reason.trim() || undefined,
      }),
    onSuccess: () => {
      setError(null);
      setOpen(false);
      setFee("");
      setReason("");
      qc.invalidateQueries({ queryKey: ["facility", "order", orderId] });
    },
    onError: (e: unknown) => setError(e instanceof Error ? e.message : "Could not submit the revised quote."),
  });

  const canSubmit = Number(fee) > 0 && !submit.isPending;

  return (
    <DetailSectionCard title="Revised Quote" icon={BadgeDollarSign}>
      {revisions.length > 0 && (
        <ul className="mb-3 space-y-2">
          {revisions.map((r) => {
            const s = STATUS[r.status] ?? { label: r.status, tone: "neutral" as Tone };
            return (
              <li key={r.id} className="rounded-lg border border-border/60 bg-surface-2 px-3 py-2.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-sm text-ink">{money(r.facility_fee, r.currency ?? "AED")}</span>
                  <StatusBadge tone={s.tone} dot={false}>{s.label}</StatusBadge>
                </div>
                {r.customer_price != null && (
                  <p className="mt-1 text-xxs text-ink-muted">Customer price: {money(r.customer_price, r.currency ?? "AED")}</p>
                )}
                {r.reason && <p className="mt-1 text-xxs text-ink-faint">{r.reason}</p>}
              </li>
            );
          })}
        </ul>
      )}

      {open ? (
        <div className="space-y-2.5">
          {items.length > 0 && (
            <select
              value={itemId}
              onChange={(e) => setItemId(e.target.value)}
              className="h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink focus:border-rose focus-visible:outline-none"
            >
              <option value="">Whole order</option>
              {items.map((it) => (
                <option key={it.id} value={it.id}>
                  {it.name}
                </option>
              ))}
            </select>
          )}
          <input
            type="number"
            min="0"
            step="0.01"
            value={fee}
            onChange={(e) => setFee(e.target.value)}
            placeholder="Your revised fee (AED)"
            className="h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none"
          />
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={2}
            placeholder="Why the standard price doesn't apply…"
            className="w-full rounded-lg border border-border bg-canvas px-3 py-2.5 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none"
          />
          <p className="text-xxs text-ink-faint">
            Operations reviews your fee and sets the customer price. The customer must approve before the extra work continues.
          </p>
          {error && <p className="text-xxs font-medium text-danger">{error}</p>}
          <div className="flex gap-2">
            <Button variant="primary" size="md" className="flex-1" disabled={!canSubmit} onClick={() => submit.mutate()}>
              {submit.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Submit
            </Button>
            <Button variant="ghost" size="md" onClick={() => setOpen(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <Button variant="secondary" size="md" className="w-full" onClick={() => setOpen(true)}>
          <BadgeDollarSign className="h-4 w-4" /> Submit a revised quote
        </Button>
      )}
    </DetailSectionCard>
  );
}
