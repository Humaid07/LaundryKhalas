"use client";

import { Suspense, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ClipboardList } from "lucide-react";
import { facilityApi, type FacilityOrder } from "@/lib/api-client";
import { formatDate } from "@/lib/formatters";
import { MobilePageHeader } from "@/components/shared/MobilePageHeader";
import { DateRangeFilter, type DateRange } from "@/components/shared/DateRangeFilter";
import { WorkflowTabs } from "@/components/ui/Tabs";
import { OrderCard } from "@/components/orders/OrderCard";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";

const BUCKETS = [
  { id: "in", label: "Orders In" },
  { id: "out", label: "Orders Out" },
  { id: "upcoming", label: "Upcoming" },
  { id: "attention", label: "Needs Attention" },
  { id: "completed", label: "Completed" },
] as const;

type Bucket = (typeof BUCKETS)[number]["id"];

function OrdersView() {
  const search = useSearchParams();
  const initialBucket = (search.get("bucket") as Bucket) ?? "in";
  const [bucket, setBucket] = useState<Bucket>(
    BUCKETS.some((b) => b.id === initialBucket) ? initialBucket : "in",
  );
  const [range, setRange] = useState<DateRange>("today");
  const [custom, setCustom] = useState<{ from: string; to: string }>({ from: "", to: "" });

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["facility", "orders", bucket, range, custom],
    queryFn: () =>
      facilityApi.orders({
        bucket,
        range: range === "custom" ? undefined : range,
        from: range === "custom" ? custom.from || undefined : undefined,
        to: range === "custom" ? custom.to || undefined : undefined,
      }),
  });

  const orders = data ?? [];

  // For the "Upcoming" bucket, group by day for a scannable schedule.
  const grouped = useMemo(() => {
    if (bucket !== "upcoming") return null;
    const map = new Map<string, FacilityOrder[]>();
    for (const o of orders) {
      const key = o.expected_at ? formatDate(o.expected_at) : "Unscheduled";
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(o);
    }
    return Array.from(map.entries());
  }, [bucket, orders]);

  const tabs = BUCKETS.map((b) => ({ id: b.id, label: b.label }));

  return (
    <div className="lk-enter space-y-5">
      <MobilePageHeader title="Orders" description="Everything moving through your facility." />

      {/* Sticky filter row */}
      <div className="sticky top-14 z-20 -mx-4 space-y-3 border-b border-border/60 bg-canvas/90 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6">
        <WorkflowTabs
          tabs={tabs}
          value={bucket}
          onChange={(id) => setBucket(id as Bucket)}
        />
        <DateRangeFilter
          value={range}
          onChange={setRange}
          from={custom.from}
          to={custom.to}
          onCustomChange={(from, to) => setCustom({ from, to })}
        />
      </div>

      {isLoading ? (
        <LoadingState label="Loading orders…" />
      ) : isError ? (
        <ErrorState description="Could not load orders." onRetry={() => refetch()} />
      ) : orders.length === 0 ? (
        <EmptyState
          icon={ClipboardList}
          title="No orders here"
          description="Nothing matches this view for the selected dates."
        />
      ) : grouped ? (
        <div className="space-y-6">
          {grouped.map(([day, dayOrders]) => (
            <section key={day}>
              <h2 className="mb-2 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">{day}</h2>
              <div className="space-y-3">
                {dayOrders.map((o) => (
                  <OrderCard key={o.id} order={o} />
                ))}
              </div>
            </section>
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {orders.map((o) => (
            <OrderCard key={o.id} order={o} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function OrdersPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading orders…" />}>
      <OrdersView />
    </Suspense>
  );
}
