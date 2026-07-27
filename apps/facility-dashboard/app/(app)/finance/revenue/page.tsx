"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { facilityApi } from "@/lib/api-client";
import { formatCurrency } from "@/lib/formatters";
import { MobilePageHeader } from "@/components/shared/MobilePageHeader";
import { FinanceNav } from "@/components/finance/FinanceNav";
import { ChartCard } from "@/components/ui/ChartCard";
import { BarSeries } from "@/components/ui/charts";
import { CHART } from "@/lib/chart-theme";
import { MinimalKpiStrip } from "@/components/minimal/MinimalKpiStrip";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/states";
import { cn } from "@/lib/utils";
import type { TimeSeriesPoint } from "@/lib/types";

const GRANULARITY = [
  { id: "day", label: "Day" },
  { id: "week", label: "Week" },
  { id: "month", label: "Month" },
] as const;

export default function RevenuePage() {
  const [granularity, setGranularity] = useState<"day" | "week" | "month">("day");

  const summary = useQuery({
    queryKey: ["facility", "finance", "summary"],
    queryFn: () => facilityApi.financeSummary(),
  });
  const revenue = useQuery({
    queryKey: ["facility", "finance", "revenue", granularity],
    queryFn: () => facilityApi.financeRevenue({ granularity }),
  });

  const currency = summary.data?.currency ?? "AED";
  const data: TimeSeriesPoint[] = (revenue.data ?? []).map((p) => ({ label: p.label, value: p.value }));
  const total = data.reduce((s, p) => s + (typeof p.value === "number" ? p.value : 0), 0);

  return (
    <div className="lk-enter space-y-5">
      <MobilePageHeader title="Revenue" description="Service value over time." />
      <FinanceNav />

      <MinimalKpiStrip
        kpis={[
          { label: "Completed Orders Value", value: formatCurrency(summary.data?.completed_orders_value ?? 0, currency) },
          { label: "Completed Orders", value: String(summary.data?.completed_orders ?? 0) },
          { label: "Range Total", value: formatCurrency(total, currency) },
          { label: "Avg Order Value", value: formatCurrency(summary.data?.avg_order_value ?? 0, currency) },
        ]}
      />

      <ChartCard
        title="Revenue"
        action={
          <div className="inline-flex gap-1 rounded-lg border border-border bg-surface-2 p-0.5">
            {GRANULARITY.map((g) => (
              <button
                key={g.id}
                type="button"
                onClick={() => setGranularity(g.id)}
                className={cn(
                  "rounded-md px-2.5 py-1 text-xs font-semibold transition-colors",
                  granularity === g.id ? "bg-surface text-rose shadow-card" : "text-ink-muted hover:text-ink",
                )}
              >
                {g.label}
              </button>
            ))}
          </div>
        }
      >
        {revenue.isLoading ? (
          <LoadingState label="Loading revenue…" />
        ) : revenue.isError ? (
          <ErrorState description="Could not load revenue." onRetry={() => revenue.refetch()} />
        ) : data.length === 0 ? (
          <EmptyState title="No revenue yet" description="Completed orders will appear here." />
        ) : (
          <BarSeries data={data} color={CHART.rose} currency height={260} />
        )}
      </ChartCard>
    </div>
  );
}
