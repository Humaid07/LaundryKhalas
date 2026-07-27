"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { facilityApi } from "@/lib/api-client";
import { formatCurrency } from "@/lib/formatters";
import { MobilePageHeader } from "@/components/shared/MobilePageHeader";
import { FinanceNav } from "@/components/finance/FinanceNav";
import { MinimalKpiStrip } from "@/components/minimal/MinimalKpiStrip";
import { ChartCard } from "@/components/ui/ChartCard";
import { AreaTrend } from "@/components/ui/charts";
import { CHART } from "@/lib/chart-theme";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/states";
import { cn } from "@/lib/utils";
import type { TimeSeriesPoint } from "@/lib/types";

const GRANULARITY = [
  { id: "day", label: "Day" },
  { id: "week", label: "Week" },
  { id: "month", label: "Month" },
] as const;

export default function FinancePage() {
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
  const revenueData: TimeSeriesPoint[] = (revenue.data ?? []).map((p) => ({
    label: p.label,
    value: p.value,
  }));

  return (
    <div className="lk-enter space-y-5">
      <MobilePageHeader title="Finance" description="Service value and payout overview for your facility." />
      <FinanceNav />

      {summary.isLoading ? (
        <LoadingState label="Loading finance…" />
      ) : summary.isError ? (
        <ErrorState description="Could not load finance data." onRetry={() => summary.refetch()} />
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
              { label: "Payout", value: "Pending", tone: "neutral" },
            ]}
          />

          <ChartCard
            title="Revenue over time"
            subtitle="Service value across the selected grain"
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
            ) : revenueData.length === 0 ? (
              <EmptyState title="No revenue yet" description="Completed orders will appear here." />
            ) : (
              <AreaTrend
                data={revenueData}
                series={[{ key: "value", color: CHART.rose, name: "Service value" }]}
                currency
                height={240}
              />
            )}
          </ChartCard>
        </>
      )}
    </div>
  );
}
