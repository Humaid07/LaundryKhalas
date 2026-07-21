"use client";

import { ArrowUpRight, SearchX } from "lucide-react";
import { StatGrid } from "@/components/dashboard/ui/StatCard";
import { ChartCard } from "@/components/dashboard/ui/ChartCard";
import { Panel, PanelHeader, StatusBadge, DeltaChip } from "@/components/dashboard/ui/primitives";
import { Button } from "@/components/dashboard/ui/Button";
import { DataTable, type Column } from "@/components/dashboard/ui/DataTable";
import { EmptyState, FilteredEmptyState, SnapshotBadge } from "@/components/dashboard/ui/states";
import { AreaTrend, BarSeries, DonutChart } from "@/components/dashboard/charts";
import { CHART } from "@/lib/dashboard/chart-theme";
import { formatCurrency, formatNumber } from "@/lib/dashboard/formatters";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import {
  filterCategory,
  applyGlobalFilters,
  activeFilterCount,
  filterContextLabel,
  CITY_MARKET,
  MARKET_REGION,
  type Filters,
} from "@/lib/dashboard/filters";
import {
  salesKpis,
  salesByRegion,
  salesByMarket,
  salesByChannel,
  revenueByService,
  acquisitionTrend,
  b2bVsB2c,
  topCities,
  topServices,
  topCustomers,
} from "@/lib/dashboard/mock-data";
import {
  conversionFunnel,
  channelConversion,
  businessAccounts,
  businessAccountStatusTone,
  type BusinessAccount,
} from "@/lib/dashboard/sales-data";
import { cn } from "@/lib/utils";

const emptyChart = <EmptyState icon={SearchX} title="No data for this filter" description="Clear a filter to see the breakdown." />;

/** Effective market/region from the geo cascade (city → market → region), so a
 *  City selection narrows the market/region breakdown charts to its parent. */
function effectiveGeo(f: Filters) {
  const market = f.market || (f.city ? CITY_MARKET[f.city] ?? "" : "");
  const region = f.region || (market ? MARKET_REGION[market] ?? "" : "");
  return { market, region };
}

/** Header row with an "Overall snapshot" badge for aggregate-only subsections
 *  (headline KPIs / trend charts that are not recomputed per filter). */
function SnapshotRow({ label }: { label: string }) {
  const { filters } = useFilters();
  return (
    <div className="flex items-center justify-between gap-3">
      <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">{label}</p>
      <SnapshotBadge active={activeFilterCount(filters) > 0} />
    </div>
  );
}

/* -------------------------------- Overview ---------------------------------- */

function OverviewSection() {
  return (
    <div className="space-y-6">
      <SnapshotRow label="Sales snapshot" />
      <StatGrid stats={salesKpis} cols="auto" />
      <div className="grid gap-4 xl:grid-cols-3">
        <ChartCard title="Customer acquisition" subtitle="New vs returning · 6 months" className="xl:col-span-2">
          <AreaTrend data={acquisitionTrend} stacked series={[{ key: "Returning", color: CHART.plum }, { key: "New", color: CHART.rose }]} />
        </ChartCard>
        <ChartCard title="B2B vs B2C" subtitle="Revenue split">
          <DonutChart data={b2bVsB2c} colors={[CHART.teal, CHART.rose]} centerValue="AED 612K" centerLabel="Total" />
        </ChartCard>
      </div>
    </div>
  );
}

/* --------------------------------- Markets ---------------------------------- */

function MarketsSection() {
  const { filters } = useFilters();
  const { market: effMarket, region: effRegion } = effectiveGeo(filters);
  const byMarket = filterCategory(salesByMarket, effMarket);
  const byRegion = filterCategory(salesByRegion, effRegion);
  const cities = topCities.filter((c) => !filters.city || c.city === filters.city);
  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Sales by market" subtitle="AED">
          {byMarket.length ? <BarSeries data={byMarket} horizontal currency colorByIndex height={240} /> : emptyChart}
        </ChartCard>
        <ChartCard title="Sales by region" subtitle="AED">
          {byRegion.length ? <BarSeries data={byRegion} currency color={CHART.plum} height={240} /> : emptyChart}
        </ChartCard>
      </div>
      <Panel>
        <PanelHeader title="Top performing cities" action={<Button variant="ghost" size="sm">All <ArrowUpRight className="h-3.5 w-3.5" /></Button>} />
        {cities.length === 0 && emptyChart}
        <ul className="space-y-1">
          {cities.map((c, i) => (
            <li key={c.city} className="flex items-center gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-surface-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-md bg-rose/10 font-mono text-xs font-semibold text-rose tnum">{i + 1}</span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-ink">{c.city}</p>
                <p className="text-xxs text-ink-faint">{formatNumber(c.orders)} orders</p>
              </div>
              <span className="font-mono text-sm text-ink tnum">{formatCurrency(c.revenue, "AED", true)}</span>
              <DeltaChip delta={c.growth} />
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}

/* --------------------------------- Channels --------------------------------- */

function ChannelsSection() {
  const { filters } = useFilters();
  const byChannel = filterCategory(salesByChannel, filters.channel);
  const byConversion = filterCategory(channelConversion, filters.channel);
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <ChartCard title="Sales by channel" subtitle="AED">
        {byChannel.length ? <BarSeries data={byChannel} horizontal currency color={CHART.rose} height={260} /> : emptyChart}
      </ChartCard>
      <ChartCard title="Channel conversion" subtitle="Lead → order %">
        {byConversion.length ? <BarSeries data={byConversion} colorByIndex height={260} /> : emptyChart}
      </ChartCard>
    </div>
  );
}

/* --------------------------------- Services --------------------------------- */

function ServicesSection() {
  const { filters } = useFilters();
  const byService = filterCategory(revenueByService, filters.service);
  const services = topServices.filter((s) => !filters.service || s.service === filters.service);
  return (
    <div className="space-y-4">
      <ChartCard title="Revenue by service type" subtitle="AED · last 30 days">
        {byService.length ? <BarSeries data={byService} horizontal currency colorByIndex height={260} /> : emptyChart}
      </ChartCard>
      <Panel>
        <PanelHeader title="Top services" subtitle="By revenue share" />
        {services.length === 0 && emptyChart}
        <ul className="space-y-2.5">
          {services.map((s) => (
            <li key={s.service}>
              <div className="mb-1 flex items-center justify-between text-sm">
                <span className="font-medium text-ink">{s.service}</span>
                <span className="font-mono text-ink-muted tnum">{formatCurrency(s.revenue, "AED", true)}</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-ink/6">
                <div className="h-full rounded-full bg-rose" style={{ width: `${s.share * 2.4}%` }} />
              </div>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}

/* --------------------------------- B2B / B2C -------------------------------- */

const accountCols: Column<BusinessAccount>[] = [
  { key: "name", header: "Account", primary: true, cell: (a) => <span className="whitespace-nowrap font-medium text-ink">{a.name}</span> },
  { key: "type", header: "Type", cell: (a) => <StatusBadge tone="neutral" dot={false}>{a.type}</StatusBadge> },
  { key: "city", header: "City", cell: (a) => <span className="text-xs text-ink-muted">{a.city}</span> },
  { key: "revenue", header: "Monthly Revenue", align: "right", cell: (a) => <span className="font-mono text-sm text-ink tnum">{formatCurrency(a.monthlyRevenue, "AED", true)}</span> },
  { key: "orders", header: "Orders", align: "right", cell: (a) => <span className="font-mono text-sm text-ink-muted tnum">{a.orders}</span> },
  { key: "status", header: "Status", cell: (a) => <StatusBadge tone={businessAccountStatusTone[a.status]}>{a.status}</StatusBadge> },
];

function B2bB2cSection() {
  const { filters, clearAll } = useFilters();
  const accounts = applyGlobalFilters(businessAccounts, filters);
  return (
    <div className="space-y-4">
      <SnapshotRow label="B2B / B2C snapshot" />
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="B2B vs B2C" subtitle="Revenue split">
          <DonutChart data={b2bVsB2c} colors={[CHART.teal, CHART.rose]} centerValue="AED 612K" centerLabel="Total" height={240} />
        </ChartCard>
        <div className="grid grid-cols-2 gap-3 content-start">
          {[
            { label: "B2B revenue", value: "AED 208K", tone: "text-[rgb(var(--c-teal))]" },
            { label: "B2C revenue", value: "AED 404K", tone: "text-rose" },
            { label: "B2B accounts", value: "8", tone: "text-ink" },
            { label: "B2B share", value: "34%", tone: "text-ink" },
          ].map((s) => (
            <div key={s.label} className="rounded-2xl border border-border bg-surface p-4 shadow-card">
              <p className="text-xxs uppercase tracking-eyebrow text-ink-faint">{s.label}</p>
              <p className={cn("mt-1 font-mono text-xl font-semibold tnum", s.tone)}>{s.value}</p>
            </div>
          ))}
        </div>
      </div>
      <Panel padded={false}>
        <PanelHeader title="Business accounts" subtitle={`${accounts.length} of ${businessAccounts.length} · corporate, hotel and building customers`} className="p-4" />
        <div className="px-4 pb-4">
          <DataTable columns={accountCols} rows={accounts} rowKey={(a) => a.name} empty={<FilteredEmptyState entity="accounts" context={filterContextLabel(filters)} onClear={clearAll} />} onRowLabel={(a) => <StatusBadge tone={businessAccountStatusTone[a.status]}>{a.status}</StatusBadge>} />
        </div>
      </Panel>
    </div>
  );
}

/* ------------------------------- Top customers ------------------------------ */

function TopCustomersSection() {
  return (
    <div className="space-y-4">
      <SnapshotRow label="Top customers" />
      <Panel>
      <PanelHeader title="Top customers & business accounts" subtitle="Highest revenue this period" />
      <ul className="divide-y divide-border">
        {topCustomers.map((c) => (
          <li key={c.name} className="flex items-center justify-between gap-3 py-2.5">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-rose/12 font-display text-xs font-bold text-rose">
                {c.name.split(" ").map((n) => n[0]).join("").slice(0, 2)}
              </span>
              <div>
                <p className="text-sm font-medium text-ink">{c.name}</p>
                <p className="text-xxs text-ink-faint">{formatNumber(c.orders)} orders</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <StatusBadge tone={c.type === "B2B" ? "plum" : "info"} dot={false}>{c.type}</StatusBadge>
              <span className="w-24 text-right font-mono text-sm text-ink tnum">{formatCurrency(c.revenue, "AED", true)}</span>
            </div>
          </li>
        ))}
      </ul>
    </Panel>
    </div>
  );
}

/* ----------------------------- Conversion funnel ---------------------------- */

function ConversionFunnelSection() {
  const max = conversionFunnel[0].count;
  return (
    <div className="space-y-4">
      <SnapshotRow label="Conversion funnel" />
      <Panel>
        <PanelHeader title="Conversion funnel" subtitle="Leads → inquiries → bookings → completed" />
        <div className="space-y-3">
          {conversionFunnel.map((f) => (
            <div key={f.stage}>
              <div className="mb-1 flex items-center justify-between text-sm">
                <span className="font-medium text-ink">{f.stage}</span>
                <span className="font-mono text-ink-muted tnum">{formatNumber(f.count)} · {f.pctOfTop}%</span>
              </div>
              <div className="h-2.5 overflow-hidden rounded-full bg-ink/6">
                <div className="h-full rounded-full" style={{ width: `${(f.count / max) * 100}%`, backgroundColor: `rgb(var(--${f.tone === "info" ? "c-sky" : f.tone === "plum" ? "c-plum" : f.tone === "rose" ? "c-rose" : f.tone === "success" ? "success" : "danger"}))` }} />
              </div>
            </div>
          ))}
        </div>
      </Panel>
      <ChartCard title="Funnel by stage" subtitle="Volume">
        <BarSeries data={conversionFunnel.map((f) => ({ label: f.stage, value: f.count }))} colorByIndex height={220} />
      </ChartCard>
    </div>
  );
}

/* --------------------------------- Router ----------------------------------- */

/** Renders one Sales subsection by slug (see lib/dashboard/sections.ts). */
export function SalesSubsection({ slug }: { slug: string }) {
  switch (slug) {
    case "overview": return <OverviewSection />;
    case "markets": return <MarketsSection />;
    case "channels": return <ChannelsSection />;
    case "services": return <ServicesSection />;
    case "b2b-b2c": return <B2bB2cSection />;
    case "top-customers": return <TopCustomersSection />;
    case "conversion-funnel": return <ConversionFunnelSection />;
    default: return <OverviewSection />;
  }
}
