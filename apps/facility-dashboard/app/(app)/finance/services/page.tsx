"use client";

import { useQuery } from "@tanstack/react-query";
import { facilityApi } from "@/lib/api-client";
import { formatCurrency } from "@/lib/formatters";
import { MobilePageHeader } from "@/components/shared/MobilePageHeader";
import { FinanceNav } from "@/components/finance/FinanceNav";
import { ChartCard } from "@/components/ui/ChartCard";
import { DonutChart } from "@/components/ui/charts";
import { CATEGORICAL } from "@/lib/chart-theme";
import { SectionCard } from "@/components/shared/SectionCard";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/states";
import type { TimeSeriesPoint } from "@/lib/types";

export default function ServicesPage() {
  const summary = useQuery({
    queryKey: ["facility", "finance", "summary"],
    queryFn: () => facilityApi.financeSummary(),
  });
  const services = useQuery({
    queryKey: ["facility", "finance", "services"],
    queryFn: () => facilityApi.financeServices(),
  });

  const currency = summary.data?.currency ?? "AED";
  const rows = services.data ?? [];
  const donut: TimeSeriesPoint[] = rows.map((r) => ({ label: r.service, value: r.value }));
  const total = rows.reduce((s, r) => s + (r.value ?? 0), 0);
  const ranked = [...rows].sort((a, b) => (b.value ?? 0) - (a.value ?? 0));

  return (
    <div className="lk-enter space-y-5">
      <MobilePageHeader title="Services" description="How your service value breaks down." />
      <FinanceNav />

      {services.isLoading ? (
        <LoadingState label="Loading service mix…" />
      ) : services.isError ? (
        <ErrorState description="Could not load service mix." onRetry={() => services.refetch()} />
      ) : rows.length === 0 ? (
        <EmptyState title="No service data yet" description="Completed orders will populate this view." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          <ChartCard title="Service mix">
            <DonutChart
              data={donut}
              colors={CATEGORICAL}
              centerValue={formatCurrency(total, currency)}
              centerLabel="Total"
              height={260}
            />
          </ChartCard>

          <SectionCard title="Top services">
            <ol className="space-y-3">
              {ranked.map((r, i) => {
                const pct = total > 0 ? Math.round(((r.value ?? 0) / total) * 100) : 0;
                return (
                  <li key={r.service} className="min-w-0">
                    <div className="flex items-center justify-between gap-3">
                      <span className="flex min-w-0 items-center gap-2">
                        <span
                          className="h-2.5 w-2.5 shrink-0 rounded-full"
                          style={{ backgroundColor: CATEGORICAL[i % CATEGORICAL.length] }}
                        />
                        <span className="truncate text-sm font-medium text-ink">{r.service}</span>
                      </span>
                      <span className="shrink-0 font-mono text-sm text-ink-muted tnum">
                        {formatCurrency(r.value ?? 0, currency)}
                      </span>
                    </div>
                    <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-ink/8">
                      <div
                        className="h-full rounded-full"
                        style={{ width: `${pct}%`, backgroundColor: CATEGORICAL[i % CATEGORICAL.length] }}
                      />
                    </div>
                  </li>
                );
              })}
            </ol>
          </SectionCard>
        </div>
      )}
    </div>
  );
}
