"use client";

import { useQuery } from "@tanstack/react-query";
import { Wallet } from "lucide-react";
import { facilityApi } from "@/lib/api-client";
import { formatCurrency, formatDate } from "@/lib/formatters";
import { MobilePageHeader } from "@/components/shared/MobilePageHeader";
import { FinanceNav } from "@/components/finance/FinanceNav";
import { MinimalKpiStrip } from "@/components/minimal/MinimalKpiStrip";
import { SectionCard } from "@/components/shared/SectionCard";
import { StatusBadge } from "@/components/ui/primitives";
import { issueStatusTone, issueStatusLabel } from "@/lib/status";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/states";

export default function PayoutsPage() {
  const summary = useQuery({
    queryKey: ["facility", "finance", "summary"],
    queryFn: () => facilityApi.financeSummary(),
  });
  const payouts = useQuery({
    queryKey: ["facility", "finance", "payouts"],
    queryFn: () => facilityApi.financePayouts(),
  });

  const currency = summary.data?.currency ?? payouts.data?.currency ?? "AED";
  const pendingPayout = payouts.data?.payout_amount ?? summary.data?.pending_payout ?? null;
  const payoutNote = payouts.data?.note ?? summary.data?.pending_payout_note ?? null;
  const history = payouts.data?.payouts ?? [];
  const pendingLabel =
    pendingPayout == null
      ? "Pending"
      : formatCurrency(pendingPayout, currency);

  return (
    <div className="lk-enter space-y-5">
      <MobilePageHeader title="Payouts" description="Completed value and pending payouts." />
      <FinanceNav />

      {summary.isLoading ? (
        <LoadingState label="Loading payouts…" />
      ) : summary.isError ? (
        <ErrorState description="Could not load payout data." onRetry={() => summary.refetch()} />
      ) : (
        <>
          <MinimalKpiStrip
            kpis={[
              {
                label: "Service Value",
                value:
                  summary.data?.revenue_total_display ??
                  formatCurrency(summary.data?.revenue_total ?? 0, currency),
              },
              { label: "Orders", value: String(summary.data?.order_count ?? 0) },
              {
                label: "Avg Order Value",
                value:
                  summary.data?.average_order_value_display ??
                  formatCurrency(summary.data?.average_order_value ?? 0, currency),
              },
              { label: "Pending Payout", value: pendingLabel, tone: pendingPayout == null ? "neutral" : "success" },
            ]}
          />

          <SectionCard title="Payout history" icon={Wallet}>
            {payouts.isLoading ? (
              <LoadingState label="Loading history…" />
            ) : payouts.isError ? (
              <ErrorState description="Could not load payout history." onRetry={() => payouts.refetch()} />
            ) : history.length === 0 ? (
              <EmptyState
                icon={Wallet}
                title="Payout pending"
                description={payoutNote ?? "Payout records will appear once rates are configured and orders are completed."}
              />
            ) : (
              <ul className="divide-y divide-border/60">
                {history.map((p, i) => (
                  <li key={p.id ?? i} className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-ink">{p.period ?? "Period"}</p>
                      {p.note && <p className="truncate text-xxs text-ink-muted">{p.note}</p>}
                      {p.period && <p className="text-xxs text-ink-faint">{formatDate(p.period)}</p>}
                    </div>
                    <div className="flex shrink-0 items-center gap-3">
                      <span className="font-mono text-sm text-ink tnum">
                        {p.amount != null ? formatCurrency(p.amount, currency) : "—"}
                      </span>
                      {p.status && (
                        <StatusBadge tone={issueStatusTone(p.status)} dot={false}>
                          {issueStatusLabel(p.status)}
                        </StatusBadge>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>
        </>
      )}
    </div>
  );
}
