"use client";

import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowDownToLine,
  ArrowUpFromLine,
  CalendarClock,
  AlertTriangle,
  Wallet,
  Sparkles,
  PackageCheck,
  CircleDot,
} from "lucide-react";
import { facilityApi } from "@/lib/api-client";
import { formatCurrency, formatRelativeTime } from "@/lib/formatters";
import { operatingLabel, operatingTone, issueStatusTone, issueStatusLabel } from "@/lib/status";
import { MobilePageHeader } from "@/components/shared/MobilePageHeader";
import { SectionCard } from "@/components/shared/SectionCard";
import { StatusBadge } from "@/components/ui/primitives";
import { LoadingState, ErrorState } from "@/components/ui/states";
import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

type SummaryCard = {
  label: string;
  value: string;
  icon: LucideIcon;
  hint?: string;
  href: string;
  alert?: boolean;
};

export default function OverviewPage() {
  const router = useRouter();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["facility", "overview"],
    queryFn: () => facilityApi.overview(),
  });

  // The overview endpoint carries counts + status only; service value, the top
  // service, the next arrival and the latest issue are derived from the finance,
  // orders and issues endpoints so the cards show real values (never crash).
  const finance = useQuery({
    queryKey: ["facility", "finance", "summary"],
    queryFn: () => facilityApi.financeSummary(),
  });
  const services = useQuery({
    queryKey: ["facility", "finance", "services"],
    queryFn: () => facilityApi.financeServices(),
  });
  const upcoming = useQuery({
    queryKey: ["facility", "orders", "upcoming", "overview"],
    queryFn: () => facilityApi.orders({ bucket: "upcoming" }),
  });
  const issues = useQuery({
    queryKey: ["facility", "issues", "overview"],
    queryFn: () => facilityApi.issues(),
  });

  const currency = finance.data?.currency ?? "AED";
  const upcomingCount = (data?.upcoming as number | undefined) ?? 0;
  const attentionCount = (data?.needs_attention as number | undefined) ?? 0;
  const serviceValue = finance.data?.revenue_total ?? finance.data?.completed_orders_value ?? 0;
  const topService = services.data?.[0];
  const nextArrival = upcoming.data?.[0];
  const latestIssue = (data?.open_issues as number | undefined) ? issues.data?.[0] : undefined;

  const cards: SummaryCard[] = [
    {
      label: "Orders In Today",
      value: String(data?.orders_in_today ?? 0),
      icon: ArrowDownToLine,
      href: "/orders?bucket=in",
    },
    {
      label: "Orders Out Today",
      value: String(data?.orders_out_today ?? 0),
      icon: ArrowUpFromLine,
      href: "/orders?bucket=out",
    },
    {
      label: "Upcoming",
      value: String(upcomingCount),
      icon: CalendarClock,
      href: "/orders?bucket=upcoming",
    },
    {
      label: "Needs Attention",
      value: String(attentionCount),
      icon: AlertTriangle,
      href: "/orders?bucket=attention",
      alert: attentionCount > 0,
    },
    {
      label: "Service Value",
      value: formatCurrency(serviceValue, currency),
      icon: Wallet,
      href: "/finance",
    },
    {
      label: "Top Service",
      value: topService?.service ?? "—",
      icon: Sparkles,
      hint: topService?.orders ? `${topService.orders} orders` : undefined,
      href: "/finance/services",
    },
  ];

  return (
    <div className="lk-enter space-y-6">
      <MobilePageHeader
        title="Overview"
        description="A calm snapshot of today at your facility."
      />

      {isLoading ? (
        <LoadingState label="Loading your overview…" />
      ) : isError ? (
        <ErrorState description="Could not load your overview." onRetry={() => refetch()} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
            {cards.map((c) => (
              <button
                key={c.label}
                type="button"
                onClick={() => router.push(c.href)}
                className={cn(
                  "group flex flex-col rounded-2xl border bg-surface p-4 text-left shadow-card transition-all duration-200 ease-out-quint hover:-translate-y-0.5 hover:shadow-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40",
                  c.alert ? "border-danger/30" : "border-border/70",
                )}
              >
                <span
                  className={cn(
                    "mb-3 flex h-9 w-9 items-center justify-center rounded-lg",
                    c.alert ? "bg-danger/12 text-danger" : "bg-rose/10 text-rose",
                  )}
                >
                  <c.icon className="h-[1.15rem] w-[1.15rem]" />
                </span>
                <span className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">{c.label}</span>
                <span className="mt-1 truncate font-mono text-xl font-semibold tracking-tight text-ink tnum">
                  {c.value}
                </span>
                {c.hint && <span className="mt-0.5 truncate text-xxs text-ink-muted">{c.hint}</span>}
              </button>
            ))}
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <SectionCard title="Next Expected Arrival" icon={PackageCheck}>
              {nextArrival ? (
                <button
                  type="button"
                  onClick={() => nextArrival.id && router.push(`/orders/${nextArrival.id}`)}
                  className="flex w-full items-center justify-between gap-3 text-left"
                >
                  <div className="min-w-0">
                    <p className="font-mono text-xs font-semibold text-rose">
                      {nextArrival.order_id ?? "—"}
                    </p>
                    <p className="mt-0.5 truncate text-sm font-medium text-ink">
                      {nextArrival.service ?? "Pickup"}
                    </p>
                  </div>
                  <p className="shrink-0 text-sm font-medium text-ink-muted">
                    {formatRelativeTime(nextArrival.expected_at)}
                  </p>
                </button>
              ) : (
                <p className="text-sm text-ink-muted">No arrivals scheduled right now.</p>
              )}
            </SectionCard>

            <SectionCard title="Operating Status" icon={CircleDot}>
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm text-ink-muted">Your facility is currently</p>
                <StatusBadge tone={operatingTone(data?.operating_status)}>
                  {operatingLabel(data?.operating_status)}
                </StatusBadge>
              </div>
              <button
                type="button"
                onClick={() => router.push("/settings/operations")}
                className="mt-3 text-xs font-semibold text-ink-muted transition-colors hover:text-rose"
              >
                Change in Operations settings →
              </button>
            </SectionCard>
          </div>

          <SectionCard title="Latest Issue" icon={AlertTriangle}>
            {latestIssue ? (
              <button
                type="button"
                onClick={() => latestIssue.id && router.push(`/issues/${latestIssue.id}`)}
                className="flex w-full items-center justify-between gap-3 text-left"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-ink">
                    {latestIssue.title ?? latestIssue.issue_type ?? "Reported issue"}
                  </p>
                  <p className="mt-0.5 text-xxs text-ink-faint">
                    {formatRelativeTime(latestIssue.created_at)}
                  </p>
                </div>
                <StatusBadge tone={issueStatusTone(latestIssue.status)} dot={false}>
                  {issueStatusLabel(latestIssue.status)}
                </StatusBadge>
              </button>
            ) : (
              <p className="text-sm text-ink-muted">No open issues. Everything looks clear.</p>
            )}
          </SectionCard>
        </>
      )}
    </div>
  );
}
