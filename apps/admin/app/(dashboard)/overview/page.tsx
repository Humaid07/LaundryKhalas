"use client";

import Link from "next/link";
import { MessageSquarePlus, Download, ArrowUpRight, SearchX } from "lucide-react";
import { ResponsivePageHeader } from "@/components/dashboard/shell/PageHeader";
import { StatGrid } from "@/components/dashboard/ui/StatCard";
import { ChartCard } from "@/components/dashboard/ui/ChartCard";
import { Panel, PanelHeader, StatusBadge } from "@/components/dashboard/ui/primitives";
import { Button } from "@/components/dashboard/ui/Button";
import { DataTable, type Column } from "@/components/dashboard/ui/DataTable";
import { EmptyState, SnapshotBadge } from "@/components/dashboard/ui/states";
import { AreaTrend, BarSeries, DonutChart, GroupedBars } from "@/components/dashboard/charts";
import { ApprovalCard, ActivityTimeline } from "@/components/dashboard/widgets";
import { CHART } from "@/lib/dashboard/chart-theme";
import {
  overviewKpis,
  ordersOverTime,
  revenueOverTime,
  ordersByChannel,
  ordersByCity,
  ticketsByCategory,
  automationRate,
  orders,
  conversations,
  approvals,
  activityFeed,
} from "@/lib/dashboard/mock-data";
import { formatCurrency, formatNumber, formatRelativeTime, maskPhone } from "@/lib/dashboard/formatters";
import { orderStatusTone, convStatusTone } from "@/lib/dashboard/status-maps";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import { filterOrders, filterConversations, filterCategory, activeFilterCount } from "@/lib/dashboard/filters";
import type { Order } from "@/lib/dashboard/types";

const latestOrderCols: Column<Order>[] = [
  { key: "id", header: "Order", primary: true, cell: (o) => <span className="font-mono text-xs font-semibold text-ink">{o.id}</span> },
  { key: "customer", header: "Customer", cell: (o) => <span className="text-ink">{o.customer}</span> },
  { key: "service", header: "Service", cell: (o) => <span className="text-ink-muted">{o.service}</span> },
  { key: "city", header: "City", cell: (o) => <span className="text-ink-muted">{o.city}</span> },
  { key: "status", header: "Status", cell: (o) => <StatusBadge tone={orderStatusTone[o.status]}>{o.status}</StatusBadge> },
  { key: "amount", header: "Amount", align: "right", cell: (o) => <span className="font-mono text-sm text-ink tnum">{formatCurrency(o.amount)}</span> },
];

export default function OverviewPage() {
  const { filters } = useFilters();
  const filteredOrders = filterOrders(orders, filters);
  const filteredConversations = filterConversations(conversations, filters);
  const byChannel = filterCategory(ordersByChannel, filters.channel);
  const byCity = filterCategory(ordersByCity, filters.city);
  const channelTotal = byChannel.reduce((s, r) => s + (r.value as number), 0);

  return (
    <div className="lk-enter">
      <ResponsivePageHeader
        eyebrow="Operations · GCC"
        title="Command Center"
        description="A live snapshot of orders, revenue, agents and approvals across every market."
        showFilters
        actions={
          <>
            <Button variant="secondary" size="md">
              <Download className="h-4 w-4" /> Export
            </Button>
            <Button variant="primary" size="md">
              <MessageSquarePlus className="h-4 w-4" /> New Inbound
            </Button>
          </>
        }
      />

      {/* KPI grid — headline totals are period snapshots (labelled when filters are active);
          the lists/charts below (orders, conversations, by-channel, by-city) are filter-aware. */}
      <div className="mb-2 flex items-center justify-between gap-3">
        <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Headline totals</p>
        <SnapshotBadge active={activeFilterCount(filters) > 0} />
      </div>
      <StatGrid stats={overviewKpis} className="mb-6" />

      {/* Primary trend charts */}
      <div className="mb-6 grid gap-4 xl:grid-cols-3">
        <ChartCard
          title="Orders over time"
          subtitle="By channel · last 3 weeks"
          className="xl:col-span-2"
        >
          <AreaTrend
            data={ordersOverTime}
            stacked
            series={[
              { key: "WhatsApp", color: CHART.rose },
              { key: "Website", color: CHART.plum },
              { key: "App", color: CHART.teal },
            ]}
          />
        </ChartCard>
        <ChartCard title="Revenue & profit" subtitle="AED · last 3 weeks">
          <AreaTrend
            data={revenueOverTime}
            currency
            series={[
              { key: "Revenue", color: CHART.rose },
              { key: "Profit", color: CHART.teal },
            ]}
          />
        </ChartCard>
      </div>

      {/* Breakdown charts */}
      <div className="mb-6 grid gap-4 lg:grid-cols-3">
        <ChartCard title="Orders by channel" subtitle="Share of volume">
          <DonutChart data={byChannel} centerValue={formatNumber(channelTotal, true)} centerLabel="Orders" />
        </ChartCard>
        <ChartCard title="Orders by city" subtitle="Top markets">
          {byCity.length > 0 ? (
            <BarSeries data={byCity} horizontal colorByIndex height={264} />
          ) : (
            <EmptyState icon={SearchX} title="No cities match" description="Adjust or clear the filters." />
          )}
        </ChartCard>
        <ChartCard title="Automation rate" subtitle="AI vs human handling">
          <GroupedBars
            data={automationRate}
            series={[
              { key: "Automated", color: CHART.rose, name: "AI" },
              { key: "Human", color: CHART.slate, name: "Human" },
            ]}
          />
        </ChartCard>
      </div>

      {/* Latest orders + side panels */}
      <div className="grid gap-4 xl:grid-cols-3">
        <Panel className="xl:col-span-2">
          <PanelHeader
            title="Latest orders"
            subtitle={`${filteredOrders.length} of ${orders.length} orders`}
            action={
              <Link href="/operations/customer-orders">
                <Button variant="ghost" size="sm">
                  View all <ArrowUpRight className="h-3.5 w-3.5" />
                </Button>
              </Link>
            }
          />
          <DataTable
            columns={latestOrderCols}
            rows={filteredOrders.slice(0, 6)}
            rowKey={(o) => o.id}
            empty={<EmptyState icon={SearchX} title="No orders match" description="Try clearing a filter." />}
          />
        </Panel>

        <Panel>
          <PanelHeader
            title="Pending approvals"
            subtitle="Every agent action needs a human"
            action={
              <Link href="/finance-compliance/refunds-adjustments" className="inline-flex">
                <StatusBadge tone="rose">{approvals.length}</StatusBadge>
              </Link>
            }
          />
          <div className="space-y-2.5">
            {approvals.slice(0, 3).map((a) => (
              <ApprovalCard key={a.id} approval={a} compact />
            ))}
          </div>
        </Panel>
      </div>

      {/* Conversations + tickets + activity */}
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Panel>
          <PanelHeader
            title="Recent WhatsApp conversations"
            action={
              <Link href="/operations/customer-facing">
                <Button variant="ghost" size="sm">Open <ArrowUpRight className="h-3.5 w-3.5" /></Button>
              </Link>
            }
          />
          {filteredConversations.length === 0 && (
            <EmptyState icon={SearchX} title="No conversations match" description="Adjust the filters to see conversations." />
          )}
          <ul className="space-y-3">
            {filteredConversations.slice(0, 4).map((c) => (
              <li key={c.id} className="flex items-start gap-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-rose/12 font-display text-xs font-bold text-rose">
                  {c.customer.split(" ").map((n) => n[0]).join("").slice(0, 2)}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <p className="truncate text-sm font-medium text-ink">{c.customer}</p>
                    <span className="shrink-0 text-xxs text-ink-faint">{formatRelativeTime(c.updatedAt)}</span>
                  </div>
                  <p className="truncate text-xs text-ink-muted">{c.lastMessage}</p>
                  <div className="mt-1 flex items-center gap-2">
                    <StatusBadge tone={convStatusTone[c.status]}>{c.status}</StatusBadge>
                    <span className="text-xxs text-ink-faint">{maskPhone(c.phone)}</span>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel>
          <PanelHeader title="Tickets by category" subtitle="Open concerns" />
          <BarSeries data={ticketsByCategory} colorByIndex height={230} />
        </Panel>

        <Panel>
          <PanelHeader title="Activity" subtitle="Latest agent & ops events" />
          <ActivityTimeline events={activityFeed} />
        </Panel>
      </div>
    </div>
  );
}
