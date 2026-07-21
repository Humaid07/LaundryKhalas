"use client";

import { SearchX, ShieldCheck, Check, X, MapPin } from "lucide-react";
import { StatGrid } from "@/components/dashboard/ui/StatCard";
import { SectionTitle } from "@/components/dashboard/shell/PageHeader";
import { ChartCard } from "@/components/dashboard/ui/ChartCard";
import { Panel, PanelHeader, StatusBadge, DeltaChip } from "@/components/dashboard/ui/primitives";
import { Button } from "@/components/dashboard/ui/Button";
import { DataTable, type Column } from "@/components/dashboard/ui/DataTable";
import { EmptyState, SnapshotBadge } from "@/components/dashboard/ui/states";
import { AreaTrend, BarSeries, DonutChart, GroupedBars } from "@/components/dashboard/charts";
import { FinanceBreakdownCard, ActivityTimeline } from "@/components/dashboard/widgets";
import { toneDot } from "@/components/dashboard/ui/tones";
import { CHART } from "@/lib/dashboard/chart-theme";
import { formatCurrency, formatRelativeTime } from "@/lib/dashboard/formatters";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import { filterCategory, applyGlobalFilters, activeFilterCount, CITY_MARKET } from "@/lib/dashboard/filters";
import {
  financeKpis,
  revenueVsCost,
  profitTrend,
  revenueByMarketFin,
  profitByCity,
} from "@/lib/dashboard/mock-data";
import {
  driverCostKpi,
  complianceKpis,
  extendedCostBreakdown,
  paymentStatusRows,
  refundsAdjustments,
  approvalTone,
  facilityCompliance,
  complianceRiskTone,
  driverCompliance,
  documents,
  docStatusTone,
  auditTrail,
  riskFlags,
  riskSeverityTone,
  riskStatusTone,
  complianceStatusChart,
  financeActivity,
  type PaymentStatusRow,
  type RefundAdjustment,
  type FacilityCompliance,
  type DriverCompliance,
  type DocumentRow,
  type AuditRow,
  type RiskFlag,
} from "@/lib/dashboard/finance-compliance-data";
import { cn } from "@/lib/utils";

const emptyChart = <EmptyState icon={SearchX} title="No data for this filter" description="Clear a filter to see the breakdown." />;
const emptyRows = <EmptyState icon={SearchX} title="No records match the selected filters" description="Try clearing a filter to see more." />;
const money = (n: number) => formatCurrency(n);
const financeKpisAll = [...financeKpis, driverCostKpi];

const donutData = extendedCostBreakdown.map((c) => ({ label: c.category, value: c.amount }));
const donutColors = [CHART.rose, CHART.plum, CHART.teal, CHART.amber, CHART.sky, CHART.slate, CHART.danger, "rgb(var(--c-plum) / 0.6)"];

/** Header row with an "Overall snapshot" badge for aggregate finance rollups
 *  (headline KPIs, revenue/cost trends, cost breakdown) not recomputed per filter. */
function SnapshotRow({ label }: { label: string }) {
  const { filters } = useFilters();
  return (
    <div className="flex items-center justify-between gap-3">
      <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">{label}</p>
      <SnapshotBadge active={activeFilterCount(filters) > 0} />
    </div>
  );
}

function PrivacyNote() {
  return (
    <div className="flex items-start gap-2.5 rounded-xl border border-info/25 bg-info/8 p-3">
      <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-info" />
      <div>
        <p className="text-xs font-semibold text-ink">Approval-gated · privacy-safe</p>
        <p className="text-xxs text-ink-muted">No card numbers, bank details or full customer PII are shown. Refunds &amp; adjustments require approval before processing.</p>
      </div>
    </div>
  );
}

/* ----------------------------- Financial overview --------------------------- */

function FinancialOverviewSection() {
  const { filters } = useFilters();
  // Cascade: a City selection narrows the market chart to its parent market.
  const effMarket = filters.market || (filters.city ? CITY_MARKET[filters.city] ?? "" : "");
  const byMarket = filterCategory(revenueByMarketFin, effMarket);
  const byCity = filterCategory(profitByCity, filters.city);
  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <div className="min-w-0 space-y-4 xl:col-span-2">
        <SnapshotRow label="Financial snapshot" />
        <StatGrid stats={financeKpisAll} cols="auto" />
        <div className="grid gap-4 lg:grid-cols-2">
          <ChartCard title="Revenue vs cost" subtitle="AED · 6 months">
            <GroupedBars data={revenueVsCost} series={[{ key: "Revenue", color: CHART.rose }, { key: "Cost", color: CHART.slate }]} height={220} />
          </ChartCard>
          <ChartCard title="Profit trend" subtitle="AED · 6 months">
            <AreaTrend data={profitTrend} currency series={[{ key: "Profit", color: CHART.teal }]} height={220} />
          </ChartCard>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <ChartCard title="Revenue by market" subtitle="AED">
            {byMarket.length ? <BarSeries data={byMarket} horizontal currency colorByIndex height={180} /> : emptyChart}
          </ChartCard>
          <ChartCard title="Profit by city" subtitle="AED">
            {byCity.length ? <BarSeries data={byCity} horizontal currency color={CHART.teal} height={180} /> : emptyChart}
          </ChartCard>
        </div>
      </div>
      <aside className="space-y-4">
        <PrivacyNote />
        <Panel>
          <PanelHeader title="Finance & compliance activity" subtitle="Latest events" />
          <ActivityTimeline events={financeActivity} />
        </Panel>
      </aside>
    </div>
  );
}

/* ------------------------------- Cost breakdown ----------------------------- */

function CostBreakdownTab() {
  return (
    <div className="space-y-4">
      <SnapshotRow label="Cost breakdown" />
      <ChartCard title="Cost breakdown" subtitle="Share of total cost">
        <div className="grid items-center gap-4 sm:grid-cols-2">
          <DonutChart data={donutData} colors={donutColors} centerValue="AED 450K" centerLabel="Total cost" height={240} />
          <FinanceBreakdownCard lines={extendedCostBreakdown.slice(0, 6)} />
        </div>
      </ChartCard>
      <Panel padded={false}>
        <PanelHeader title="Cost breakdown" subtitle="By category · vs previous period" className="p-4" />
        <div className="overflow-x-auto px-4 pb-4">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left">
                {["Category", "Amount", "% of cost", "Trend", "Notes"].map((h, i) => (
                  <th key={h} className={cn("px-3 py-2.5 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint", i === 1 && "text-right")}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {extendedCostBreakdown.map((c) => (
                <tr key={c.category} className="border-b border-border/70 last:border-0 hover:bg-surface-2">
                  <td className="px-3 py-3"><span className="flex items-center gap-2 font-medium text-ink"><span className={cn("h-2 w-2 rounded-full", toneDot[c.tone])} /> {c.category}</span></td>
                  <td className="px-3 py-3 text-right font-mono text-ink tnum">{formatCurrency(c.amount)}</td>
                  <td className="px-3 py-3 font-mono text-ink-muted tnum">{c.pctOfCost.toFixed(1)}%</td>
                  <td className="px-3 py-3"><DeltaChip delta={c.delta} /></td>
                  <td className="px-3 py-3 text-xs text-ink-muted">{c.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

/* ------------------------------ Customer payments --------------------------- */

const paymentCols: Column<PaymentStatusRow>[] = [
  { key: "status", header: "Payment Status", primary: true, cell: (p) => <StatusBadge tone={p.tone}>{p.status}</StatusBadge> },
  { key: "count", header: "Orders", align: "right", cell: (p) => <span className="font-mono text-sm text-ink tnum">{p.count.toLocaleString()}</span> },
  { key: "amount", header: "Amount", align: "right", cell: (p) => <span className="font-mono text-sm text-ink tnum">{money(p.amount)}</span> },
];

function CustomerPaymentsTab() {
  const { filters } = useFilters();
  const rows = applyGlobalFilters(paymentStatusRows, filters);
  return (
    <div className="space-y-4">
      <Panel padded={false}>
        <PanelHeader title="Customer payments" subtitle="Paid, pending, failed, refund requested, invoiced & overdue" className="p-4" />
        <div className="px-4 pb-4">
          <DataTable columns={paymentCols} rows={rows} rowKey={(p) => p.status} empty={emptyRows} />
        </div>
      </Panel>
      <ChartCard title="Payments by status" subtitle="Order count">
        {rows.length ? <BarSeries data={rows.map((p) => ({ label: p.status, value: p.count }))} colorByIndex height={200} /> : emptyChart}
      </ChartCard>
      <p className="flex items-center gap-1.5 text-xxs text-ink-faint"><ShieldCheck className="h-3 w-3" /> No card numbers, CVV or bank details are stored or shown. Aggregated status counts only.</p>
    </div>
  );
}

/* ---------------------------- Refunds & adjustments ------------------------- */

const refundCols: Column<RefundAdjustment>[] = [
  { key: "id", header: "Ref", primary: true, cell: (r) => <span className="font-mono text-xs font-semibold text-ink">{r.id}</span> },
  { key: "type", header: "Type", cell: (r) => <StatusBadge tone={r.type === "Refund" ? "plum" : "neutral"} dot={false}>{r.type}</StatusBadge> },
  { key: "order", header: "Order", cell: (r) => <span className="font-mono text-xs text-ink-muted">{r.orderRef}</span> },
  { key: "reason", header: "Reason", cell: (r) => <span className="text-xs text-ink-muted">{r.reason}</span> },
  { key: "amount", header: "Amount", align: "right", cell: (r) => <span className="font-mono text-sm text-ink tnum">{money(r.amount)}</span> },
  { key: "approval", header: "Approval", cell: (r) => <StatusBadge tone={approvalTone[r.approval]}>{r.approval}</StatusBadge> },
  { key: "reviewer", header: "Reviewer", cell: (r) => <span className="whitespace-nowrap text-xs text-ink-muted">{r.reviewer}</span> },
  { key: "actions", header: "", align: "right", cell: (r) => (
    r.approval === "Approval Required" || r.approval === "Pending Review" ? (
      <div className="flex justify-end gap-1"><Button size="sm" variant="primary"><Check className="h-3.5 w-3.5" /> Approve</Button><Button size="sm" variant="danger"><X className="h-3.5 w-3.5" /></Button></div>
    ) : <Button size="sm" variant="ghost">View</Button>
  ) },
];

function RefundsTab() {
  const { filters } = useFilters();
  const rows = applyGlobalFilters(refundsAdjustments, filters);
  return (
    <Panel padded={false}>
      <PanelHeader title="Refunds & adjustments" subtitle="Every refund/adjustment needs human approval before processing" className="p-4" action={<StatusBadge tone="rose">{rows.filter((r) => r.approval === "Approval Required").length} awaiting approval</StatusBadge>} />
      <div className="px-4 pb-4">
        <DataTable columns={refundCols} rows={rows} rowKey={(r) => r.id} onRowLabel={(r) => <StatusBadge tone={approvalTone[r.approval]}>{r.approval}</StatusBadge>} empty={emptyRows} />
      </div>
      <p className="flex items-center gap-1.5 border-t border-border px-4 py-3 text-xxs text-ink-faint"><ShieldCheck className="h-3 w-3" /> Refunds and adjustments route through approval before any money moves.</p>
    </Panel>
  );
}

/* --------------------------- Partner / facility compliance ------------------ */

const facilityCols: Column<FacilityCompliance>[] = [
  { key: "name", header: "Facility", primary: true, cell: (f) => <span className="whitespace-nowrap font-medium text-ink">{f.name}</span> },
  { key: "city", header: "City", cell: (f) => <span className="flex items-center gap-1 whitespace-nowrap text-xs text-ink-muted"><MapPin className="h-3 w-3 text-ink-faint" />{f.city}</span> },
  { key: "license", header: "License", cell: (f) => <StatusBadge tone={f.license === "Valid" ? "success" : f.license === "Expiring" ? "warning" : "danger"} dot={false}>{f.license}</StatusBadge> },
  { key: "agreement", header: "Agreement", cell: (f) => <StatusBadge tone={f.agreement === "Signed" ? "success" : f.agreement === "Pending" ? "warning" : "neutral"} dot={false}>{f.agreement}</StatusBadge> },
  { key: "quality", header: "Quality", cell: (f) => <StatusBadge tone={f.qualityChecklist === "Passed" ? "success" : f.qualityChecklist === "Partial" ? "warning" : "danger"} dot={false}>{f.qualityChecklist}</StatusBadge> },
  { key: "documents", header: "Documents", cell: (f) => <StatusBadge tone={f.documents === "Complete" ? "success" : "warning"} dot={false}>{f.documents}</StatusBadge> },
  { key: "score", header: "Score", align: "right", cell: (f) => <span className="font-mono text-sm text-ink tnum">{f.score}</span> },
  { key: "risk", header: "Risk", cell: (f) => <StatusBadge tone={complianceRiskTone[f.risk]}>{f.risk}</StatusBadge> },
];

function FacilityComplianceTab() {
  const { filters } = useFilters();
  const rows = applyGlobalFilters(facilityCompliance, filters);
  return (
    <Panel padded={false}>
      <PanelHeader title="Partner / facility compliance" subtitle="License, agreement, quality & documents — status only" className="p-4" action={<StatusBadge tone="warning">{rows.filter((f) => f.risk !== "Low").length} to review</StatusBadge>} />
      <div className="px-4 pb-4">
        <DataTable columns={facilityCols} rows={rows} rowKey={(f) => f.name} onRowLabel={(f) => <StatusBadge tone={complianceRiskTone[f.risk]}>{f.risk}</StatusBadge>} empty={emptyRows} />
      </div>
    </Panel>
  );
}

/* ------------------------------ Driver compliance --------------------------- */

const driverCols: Column<DriverCompliance>[] = [
  { key: "name", header: "Driver", primary: true, cell: (d) => <span className="whitespace-nowrap font-medium text-ink">{d.name}</span> },
  { key: "id", header: "ID / Docs", cell: (d) => <StatusBadge tone={d.idDocs === "Valid" ? "success" : d.idDocs === "Expiring" ? "warning" : "danger"} dot={false}>{d.idDocs}</StatusBadge> },
  { key: "training", header: "Training", cell: (d) => <StatusBadge tone={d.training === "Complete" ? "success" : d.training === "In Progress" ? "info" : "danger"} dot={false}>{d.training}</StatusBadge> },
  { key: "vehicle", header: "Vehicle / Docs", cell: (d) => <StatusBadge tone={d.vehicleDocs === "Valid" ? "success" : d.vehicleDocs === "Expiring" ? "warning" : "danger"} dot={false}>{d.vehicleDocs}</StatusBadge> },
  { key: "active", header: "Active", cell: (d) => <StatusBadge tone={d.active ? "success" : "neutral"} dot={false}>{d.active ? "Active" : "Suspended"}</StatusBadge> },
  { key: "risk", header: "Risk", cell: (d) => <StatusBadge tone={complianceRiskTone[d.risk]}>{d.risk}</StatusBadge> },
];

function DriverComplianceTab() {
  const { filters } = useFilters();
  const rows = applyGlobalFilters(driverCompliance, filters);
  return (
    <Panel padded={false}>
      <PanelHeader title="Driver compliance" subtitle="ID, training and vehicle documents — status only" className="p-4" action={<StatusBadge tone="warning">{rows.filter((d) => d.risk !== "Low").length} to review</StatusBadge>} />
      <div className="px-4 pb-4">
        <DataTable columns={driverCols} rows={rows} rowKey={(d) => d.name} onRowLabel={(d) => <StatusBadge tone={complianceRiskTone[d.risk]}>{d.risk}</StatusBadge>} empty={emptyRows} />
      </div>
      <p className="flex items-center gap-1.5 border-t border-border px-4 py-3 text-xxs text-ink-faint"><ShieldCheck className="h-3 w-3" /> Document states only — no ID numbers, licenses or personal contact details are shown.</p>
    </Panel>
  );
}

/* ------------------------------ Documents & expiry -------------------------- */

const docCols: Column<DocumentRow>[] = [
  { key: "document", header: "Document", primary: true, cell: (d) => <span className="whitespace-nowrap font-medium text-ink">{d.document}</span> },
  { key: "ownerType", header: "Owner Type", cell: (d) => <StatusBadge tone="neutral" dot={false}>{d.ownerType}</StatusBadge> },
  { key: "ownerName", header: "Owner", cell: (d) => <span className="whitespace-nowrap text-xs text-ink-muted">{d.ownerName}</span> },
  { key: "expiry", header: "Expiry Date", cell: (d) => <span className="whitespace-nowrap font-mono text-xs text-ink-muted tnum">{d.expiry}</span> },
  { key: "status", header: "Status", cell: (d) => <StatusBadge tone={docStatusTone[d.status]}>{d.status}</StatusBadge> },
  { key: "action", header: "Action Needed", cell: (d) => <span className="text-xs text-ink-faint">{d.action}</span> },
];

function DocumentsTab() {
  const { filters } = useFilters();
  const rows = applyGlobalFilters(documents, filters);
  return (
    <Panel padded={false}>
      <PanelHeader title="Documents & expiry" subtitle="Licenses, insurance and agreements approaching expiry" className="p-4" action={<StatusBadge tone="danger">{rows.filter((d) => d.status !== "Valid").length} need action</StatusBadge>} />
      <div className="px-4 pb-4">
        <DataTable columns={docCols} rows={rows} rowKey={(d) => `${d.document}-${d.ownerName}`} onRowLabel={(d) => <StatusBadge tone={docStatusTone[d.status]}>{d.status}</StatusBadge>} empty={emptyRows} />
      </div>
    </Panel>
  );
}

/* --------------------------------- Audit trail ------------------------------ */

const auditCols: Column<AuditRow>[] = [
  { key: "event", header: "Event", primary: true, cell: (a) => <span className="whitespace-nowrap font-medium text-ink">{a.event}</span> },
  { key: "actor", header: "Actor", cell: (a) => <span className="whitespace-nowrap text-xs text-ink-muted">{a.actor}</span> },
  { key: "module", header: "Module", cell: (a) => <StatusBadge tone="neutral" dot={false}>{a.module}</StatusBadge> },
  { key: "datetime", header: "Timestamp", cell: (a) => <span className="whitespace-nowrap text-xs text-ink-muted">{formatRelativeTime(a.datetime)}</span> },
  { key: "risk", header: "Risk", cell: (a) => <StatusBadge tone={complianceRiskTone[a.risk]} dot={false}>{a.risk}</StatusBadge> },
  { key: "notes", header: "Notes", cell: (a) => <span className="text-xs text-ink-faint">{a.notes}</span> },
];

function AuditTab() {
  const { filters } = useFilters();
  const rows = applyGlobalFilters(auditTrail, filters);
  return (
    <Panel padded={false}>
      <PanelHeader title="Audit trail" subtitle="Every finance & compliance action is logged" className="p-4" />
      <div className="px-4 pb-4">
        <DataTable columns={auditCols} rows={rows} rowKey={(a) => `${a.event}-${a.datetime}`} empty={emptyRows} />
      </div>
    </Panel>
  );
}

/* --------------------------------- Risk flags ------------------------------- */

const riskCols: Column<RiskFlag>[] = [
  { key: "id", header: "Flag", primary: true, cell: (r) => <span className="font-mono text-xs font-semibold text-ink">{r.id}</span> },
  { key: "flag", header: "Type", cell: (r) => <span className="whitespace-nowrap font-medium text-ink">{r.flag}</span> },
  { key: "severity", header: "Severity", cell: (r) => <StatusBadge tone={riskSeverityTone[r.severity]}>{r.severity}</StatusBadge> },
  { key: "detail", header: "Detail", cell: (r) => <span className="text-xs text-ink-muted">{r.detail}</span> },
  { key: "status", header: "Status", cell: (r) => <StatusBadge tone={riskStatusTone[r.status]}>{r.status}</StatusBadge> },
  { key: "actions", header: "", align: "right", cell: () => <Button size="sm" variant="secondary">Investigate</Button> },
];

function RiskFlagsSection() {
  const { filters } = useFilters();
  const rows = applyGlobalFilters(riskFlags, filters);
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <SectionTitle title="Compliance & risk KPIs" description="Reviews, documents, approvals & audit signals" className="mb-0" />
        <SnapshotBadge active={activeFilterCount(filters) > 0} />
      </div>
      <StatGrid stats={complianceKpis} cols="auto" />
      <Panel padded={false}>
        <PanelHeader title="Risk flags" subtitle="Automated finance & compliance risk signals" className="p-4" action={<StatusBadge tone="danger">{rows.filter((r) => r.status === "Open").length} open</StatusBadge>} />
        <div className="px-4 pb-4">
          <DataTable columns={riskCols} rows={rows} rowKey={(r) => r.id} onRowLabel={(r) => <StatusBadge tone={riskSeverityTone[r.severity]}>{r.severity}</StatusBadge>} empty={emptyRows} />
        </div>
      </Panel>
      <ChartCard title="Compliance status breakdown" subtitle="Across partners, facilities & drivers">
        <DonutChart data={complianceStatusChart} colors={[CHART.teal, CHART.sky, CHART.amber, CHART.danger]} centerValue="59" centerLabel="Entities" height={220} />
      </ChartCard>
    </div>
  );
}

/* --------------------------------- Router ----------------------------------- */

/** Renders one Finance & Compliance subsection by slug (see lib/dashboard/sections.ts). */
export function FinanceSubsection({ slug }: { slug: string }) {
  switch (slug) {
    case "financial-overview": return <FinancialOverviewSection />;
    case "cost-breakdown": return <CostBreakdownTab />;
    case "customer-payments": return <CustomerPaymentsTab />;
    case "refunds-adjustments": return <RefundsTab />;
    case "partner-facility-compliance": return <FacilityComplianceTab />;
    case "driver-compliance": return <DriverComplianceTab />;
    case "documents-expiry": return <DocumentsTab />;
    case "audit-trail": return <AuditTab />;
    case "risk-flags": return <RiskFlagsSection />;
    default: return <FinancialOverviewSection />;
  }
}
