"use client";

import { useState } from "react";
import {
  ShieldCheck, MapPin, ReceiptText, FileText,
  Building2, Truck, FileWarning, ScrollText, Flag,
} from "lucide-react";
import { ChartCard } from "@/components/dashboard/ui/ChartCard";
import { AreaTrend, DonutChart, GroupedBars } from "@/components/dashboard/charts";
import { CHART } from "@/lib/dashboard/chart-theme";
import { formatCurrency, formatRelativeTime } from "@/lib/dashboard/formatters";
import { useFilters } from "@/components/dashboard/shell/FiltersProvider";
import { applyGlobalFilters, activeFilterCount } from "@/lib/dashboard/filters";
import { financeKpis, revenueVsCost, profitTrend } from "@/lib/dashboard/mock-data";
import {
  paymentRecords, invoices, paymentStatusTone, chargeStatusTone, invoiceStatusTone,
  type PaymentRecord, type Invoice,
} from "@/lib/dashboard/operations-data";
import {
  extendedCostBreakdown,
  refundsAdjustments, approvalTone,
  facilityCompliance, complianceRiskTone,
  driverCompliance,
  documents, docStatusTone,
  auditTrail,
  riskFlags, riskSeverityTone, riskStatusTone,
  type RefundAdjustment,
  type FacilityCompliance,
  type DriverCompliance,
  type DocumentRow,
  type AuditRow,
  type RiskFlag,
} from "@/lib/dashboard/finance-compliance-data";
import {
  MinimalKpiStrip, WorkflowTabs, CompactRecordCard, RecordList, DataPreviewTable,
  EmptyState, StatusBadge, SnapshotBadge, type MinimalKpi, type WorkflowTab, type PreviewColumn,
} from "@/components/dashboard/minimal";

const money = (n: number) => formatCurrency(n);
const moneyK = (n: number) => formatCurrency(n, "AED", true);

/** Small right-aligned "snapshot vs filtered" marker, shared across subsections. */
function FilterRow({ children }: { children: React.ReactNode }) {
  const { filters } = useFilters();
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      {children}
      <SnapshotBadge active={activeFilterCount(filters) > 0} />
    </div>
  );
}

/* ----------------------------- Financial overview --------------------------- */

function FinancialOverviewSection() {
  const kpis: MinimalKpi[] = financeKpis.slice(0, 4).map((k) => ({
    label: k.label,
    value: k.value,
    tone: k.tone,
  }));
  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <div className="grid gap-6 lg:grid-cols-2">
        <ChartCard title="Revenue vs cost" subtitle="AED · 6 months">
          <GroupedBars data={revenueVsCost} series={[{ key: "Revenue", color: CHART.rose }, { key: "Cost", color: CHART.slate }]} height={240} />
        </ChartCard>
        <ChartCard title="Profit trend" subtitle="AED · 6 months">
          <AreaTrend data={profitTrend} currency series={[{ key: "Profit", color: CHART.teal }]} height={240} />
        </ChartCard>
      </div>
    </div>
  );
}

/* ------------------------------- Cost breakdown ----------------------------- */

const costCols: PreviewColumn<(typeof extendedCostBreakdown)[number]>[] = [
  { key: "category", header: "Category", primary: true, cell: (c) => <span className="font-medium text-ink">{c.category}</span> },
  { key: "amount", header: "Amount", align: "right", cell: (c) => <span className="font-mono text-ink tnum">{money(c.amount)}</span> },
  { key: "pct", header: "% of cost", align: "right", cell: (c) => <span className="font-mono text-ink-muted tnum">{c.pctOfCost.toFixed(1)}%</span> },
];

function CostBreakdownSection() {
  const donutData = extendedCostBreakdown.map((c) => ({ label: c.category, value: c.amount }));
  const donutColors = [CHART.rose, CHART.plum, CHART.teal, CHART.amber, CHART.sky, CHART.slate, CHART.danger, "rgb(var(--c-plum) / 0.6)"];
  const kpis: MinimalKpi[] = [
    { label: "Total cost", value: "AED 450K" },
    { label: extendedCostBreakdown[0].category, value: moneyK(extendedCostBreakdown[0].amount) },
    { label: extendedCostBreakdown[1].category, value: moneyK(extendedCostBreakdown[1].amount) },
    { label: extendedCostBreakdown[2].category, value: moneyK(extendedCostBreakdown[2].amount) },
  ];
  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <ChartCard title="Cost breakdown" subtitle="Share of total cost">
        <DonutChart data={donutData} colors={donutColors} centerValue="AED 450K" centerLabel="Total cost" height={240} />
      </ChartCard>
      <DataPreviewTable columns={costCols} rows={extendedCostBreakdown} rowKey={(c) => c.category} />
    </div>
  );
}

/* ------------------------------ Customer payments --------------------------- */

type PayTab = "all" | "paid" | "pending" | "failed" | "refund" | "invoices";

const PAY_FILTERS: Record<Exclude<PayTab, "invoices">, (p: PaymentRecord) => boolean> = {
  all: () => true,
  paid: (p) => p.status === "Paid",
  pending: (p) => p.status === "Pending",
  failed: (p) => p.status === "Failed",
  refund: (p) => p.status === "Refund Requested",
};

const invoiceCols: PreviewColumn<Invoice>[] = [
  { key: "id", header: "Invoice", primary: true, cell: (i) => <span className="font-mono text-xs font-semibold text-rose">{i.id}</span> },
  { key: "customer", header: "Business customer", cell: (i) => <span className="text-ink">{i.businessCustomer}</span> },
  { key: "period", header: "Billing period", cell: (i) => <span className="text-ink-muted">{i.billingPeriod}</span> },
  { key: "amount", header: "Amount", align: "right", cell: (i) => <span className="font-mono text-ink tnum">{money(i.amount)}</span> },
  { key: "status", header: "Status", cell: (i) => <StatusBadge tone={invoiceStatusTone[i.status] ?? "neutral"} dot={false}>{i.status}</StatusBadge> },
];

function CustomerPaymentsSection() {
  const { filters } = useFilters();
  const [tab, setTab] = useState<PayTab>("all");
  const pays = applyGlobalFilters(paymentRecords, filters);
  const invs = applyGlobalFilters(invoices, filters);

  const kpis: MinimalKpi[] = [
    { label: "Paid", value: String(pays.filter(PAY_FILTERS.paid).length), tone: "success" },
    { label: "Pending", value: String(pays.filter(PAY_FILTERS.pending).length), tone: "warning" },
    { label: "Failed", value: String(pays.filter(PAY_FILTERS.failed).length), tone: "danger" },
    { label: "Refund requested", value: String(pays.filter(PAY_FILTERS.refund).length), tone: "plum" },
  ];

  const tabs: WorkflowTab[] = [
    { id: "all", label: "All", count: pays.length },
    { id: "paid", label: "Paid", count: pays.filter(PAY_FILTERS.paid).length },
    { id: "pending", label: "Pending", count: pays.filter(PAY_FILTERS.pending).length },
    { id: "failed", label: "Failed", count: pays.filter(PAY_FILTERS.failed).length },
    { id: "refund", label: "Refund requested", count: pays.filter(PAY_FILTERS.refund).length },
    { id: "invoices", label: "Invoices", count: invs.length },
  ];

  const rows = tab === "invoices" ? [] : pays.filter(PAY_FILTERS[tab]);

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <FilterRow>
        <WorkflowTabs tabs={tabs} value={tab} onChange={(id) => setTab(id as PayTab)} />
      </FilterRow>

      {tab === "invoices" ? (
        <DataPreviewTable
          columns={invoiceCols}
          rows={invs}
          rowKey={(i) => i.id}
          empty={<EmptyState icon={FileText} title="No invoices in this view" description="B2B invoices matching the active filters appear here." />}
        />
      ) : rows.length === 0 ? (
        <EmptyState icon={ReceiptText} title="No payments in this view" description="No payment records match this status and the active filters." />
      ) : (
        <RecordList>
          {rows.map((p) => (
            <CompactRecordCard
              key={p.orderId}
              id={p.orderId}
              title={p.customer}
              status={{ label: p.status, tone: paymentStatusTone[p.status] ?? "neutral" }}
              fields={[
                { label: "Amount", value: money(p.amount) },
                { label: "Method", value: p.method },
                { label: "Area", value: <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3 text-ink-faint" />{p.area}</span> },
              ]}
              meta={<StatusBadge tone={chargeStatusTone[p.chargeStatus] ?? "neutral"} dot={false}>{p.chargeStatus}</StatusBadge>}
              href={`/finance-compliance/customer-payments/${p.orderId}?tab=${tab}`}
            />
          ))}
        </RecordList>
      )}

      <p className="flex items-center gap-1.5 text-xxs text-ink-faint">
        <ShieldCheck className="h-3 w-3" /> Amount, method &amp; status only — no card numbers, CVV or bank details are stored or shown.
      </p>
    </div>
  );
}

/* ---------------------------- Refunds & adjustments ------------------------- */

type RefTab = "all" | "required" | "review" | "approved" | "declined";

const REF_FILTERS: Record<RefTab, (r: RefundAdjustment) => boolean> = {
  all: () => true,
  required: (r) => r.approval === "Approval Required",
  review: (r) => r.approval === "Pending Review",
  approved: (r) => r.approval === "Approved",
  declined: (r) => r.approval === "Declined",
};

function RefundsSection() {
  const { filters } = useFilters();
  const [tab, setTab] = useState<RefTab>("all");
  const base = applyGlobalFilters(refundsAdjustments, filters);
  const rows = base.filter(REF_FILTERS[tab]);

  const kpis: MinimalKpi[] = [
    { label: "Awaiting approval", value: String(base.filter(REF_FILTERS.required).length), tone: "rose" },
    { label: "Pending review", value: String(base.filter(REF_FILTERS.review).length), tone: "warning" },
    { label: "Approved", value: String(base.filter(REF_FILTERS.approved).length), tone: "success" },
    { label: "Declined", value: String(base.filter(REF_FILTERS.declined).length) },
  ];

  const tabs: WorkflowTab[] = [
    { id: "all", label: "All", count: base.length },
    { id: "required", label: "Approval required", count: base.filter(REF_FILTERS.required).length },
    { id: "review", label: "Pending review", count: base.filter(REF_FILTERS.review).length },
    { id: "approved", label: "Approved", count: base.filter(REF_FILTERS.approved).length },
    { id: "declined", label: "Declined", count: base.filter(REF_FILTERS.declined).length },
  ];

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <FilterRow>
        <WorkflowTabs tabs={tabs} value={tab} onChange={(id) => setTab(id as RefTab)} />
      </FilterRow>

      {rows.length === 0 ? (
        <EmptyState icon={ReceiptText} title="No requests in this view" description="No refunds or adjustments match this status and the active filters." />
      ) : (
        <RecordList>
          {rows.map((r) => (
            <CompactRecordCard
              key={r.id}
              id={r.id}
              title={r.reason}
              status={{ label: r.approval, tone: approvalTone[r.approval] }}
              fields={[
                { label: "Type", value: r.type },
                { label: "Order", value: <span className="font-mono">{r.orderRef}</span> },
                { label: "Amount", value: money(r.amount) },
              ]}
              meta={<span className="text-xs text-ink-muted">{r.city}</span>}
              href={`/finance-compliance/refunds-adjustments/${r.id}?tab=${tab}`}
            />
          ))}
        </RecordList>
      )}

      <p className="flex items-center gap-1.5 text-xxs text-ink-faint">
        <ShieldCheck className="h-3 w-3" /> Every refund &amp; adjustment routes through human approval before any money moves.
      </p>
    </div>
  );
}

/* --------------------------- Partner / facility compliance ------------------ */

type RiskTab = "all" | "low" | "medium" | "high";
const RISK_LABELS: { id: RiskTab; label: string }[] = [
  { id: "all", label: "All" },
  { id: "high", label: "High" },
  { id: "medium", label: "Medium" },
  { id: "low", label: "Low" },
];
const riskMatch = (r: "Low" | "Medium" | "High", tab: RiskTab) => tab === "all" || r.toLowerCase() === tab;

function FacilityComplianceSection() {
  const { filters } = useFilters();
  const [tab, setTab] = useState<RiskTab>("all");
  const base = applyGlobalFilters(facilityCompliance, filters);
  const rows = base.filter((f) => riskMatch(f.risk, tab));

  const avg = base.length ? Math.round(base.reduce((s, f) => s + f.score, 0) / base.length) : 0;
  const kpis: MinimalKpi[] = [
    { label: "Facilities", value: String(base.length) },
    { label: "Needs review", value: String(base.filter((f) => f.risk !== "Low").length), tone: "warning" },
    { label: "High risk", value: String(base.filter((f) => f.risk === "High").length), tone: "danger" },
    { label: "Avg score", value: String(avg) },
  ];
  const tabs: WorkflowTab[] = RISK_LABELS.map((t) => ({ id: t.id, label: t.label, count: base.filter((f) => riskMatch(f.risk, t.id)).length }));

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <FilterRow>
        <WorkflowTabs tabs={tabs} value={tab} onChange={(id) => setTab(id as RiskTab)} />
      </FilterRow>
      {rows.length === 0 ? (
        <EmptyState icon={Building2} title="No facilities in this view" description="No facilities match this risk level and the active filters." />
      ) : (
        <RecordList>
          {rows.map((f) => (
            <CompactRecordCard
              key={f.name}
              title={f.name}
              status={{ label: `${f.risk} risk`, tone: complianceRiskTone[f.risk] }}
              fields={[
                { label: "City", value: <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3 text-ink-faint" />{f.city}</span> },
                { label: "License", value: f.license },
                { label: "Score", value: f.score },
              ]}
              meta={<StatusBadge tone={f.documents === "Complete" ? "success" : "warning"} dot={false}>{f.documents}</StatusBadge>}
            />
          ))}
        </RecordList>
      )}
    </div>
  );
}

/* ------------------------------ Driver compliance --------------------------- */

function DriverComplianceSection() {
  const { filters } = useFilters();
  const [tab, setTab] = useState<RiskTab>("all");
  const base = applyGlobalFilters(driverCompliance, filters);
  const rows = base.filter((d) => riskMatch(d.risk, tab));

  const kpis: MinimalKpi[] = [
    { label: "Drivers", value: String(base.length) },
    { label: "Active", value: String(base.filter((d) => d.active).length), tone: "success" },
    { label: "Needs review", value: String(base.filter((d) => d.risk !== "Low").length), tone: "warning" },
    { label: "High risk", value: String(base.filter((d) => d.risk === "High").length), tone: "danger" },
  ];
  const tabs: WorkflowTab[] = RISK_LABELS.map((t) => ({ id: t.id, label: t.label, count: base.filter((d) => riskMatch(d.risk, t.id)).length }));

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <FilterRow>
        <WorkflowTabs tabs={tabs} value={tab} onChange={(id) => setTab(id as RiskTab)} />
      </FilterRow>
      {rows.length === 0 ? (
        <EmptyState icon={Truck} title="No drivers in this view" description="No drivers match this risk level and the active filters." />
      ) : (
        <RecordList>
          {rows.map((d) => (
            <CompactRecordCard
              key={d.name}
              title={d.name}
              status={{ label: `${d.risk} risk`, tone: complianceRiskTone[d.risk] }}
              fields={[
                { label: "ID / docs", value: d.idDocs },
                { label: "Training", value: d.training },
                { label: "Vehicle", value: d.vehicleDocs },
              ]}
              meta={<StatusBadge tone={d.active ? "success" : "neutral"} dot={false}>{d.active ? "Active" : "Suspended"}</StatusBadge>}
            />
          ))}
        </RecordList>
      )}
      <p className="flex items-center gap-1.5 text-xxs text-ink-faint">
        <ShieldCheck className="h-3 w-3" /> Document states only — no ID numbers, licenses or personal contact details are shown.
      </p>
    </div>
  );
}

/* ------------------------------ Documents & expiry -------------------------- */

type DocTab = "all" | "expired" | "expiring" | "valid";
const DOC_FILTERS: Record<DocTab, (d: DocumentRow) => boolean> = {
  all: () => true,
  expired: (d) => d.status === "Expired",
  expiring: (d) => d.status === "Expiring Soon",
  valid: (d) => d.status === "Valid",
};

const docCols: PreviewColumn<DocumentRow>[] = [
  { key: "document", header: "Document", primary: true, cell: (d) => <span className="font-medium text-ink">{d.document}</span> },
  { key: "owner", header: "Owner", cell: (d) => <span className="text-ink-muted">{d.ownerName} · {d.ownerType}</span> },
  { key: "expiry", header: "Expiry", cell: (d) => <span className="font-mono text-xs text-ink-muted tnum">{d.expiry}</span> },
  { key: "status", header: "Status", cell: (d) => <StatusBadge tone={docStatusTone[d.status]} dot={false}>{d.status}</StatusBadge> },
];

function DocumentsSection() {
  const { filters } = useFilters();
  const [tab, setTab] = useState<DocTab>("all");
  const base = applyGlobalFilters(documents, filters);
  const rows = base.filter(DOC_FILTERS[tab]);

  const kpis: MinimalKpi[] = [
    { label: "Expired", value: String(base.filter(DOC_FILTERS.expired).length), tone: "danger" },
    { label: "Expiring soon", value: String(base.filter(DOC_FILTERS.expiring).length), tone: "warning" },
    { label: "Valid", value: String(base.filter(DOC_FILTERS.valid).length), tone: "success" },
    { label: "Total", value: String(base.length) },
  ];
  const tabs: WorkflowTab[] = [
    { id: "all", label: "All", count: base.length },
    { id: "expired", label: "Expired", count: base.filter(DOC_FILTERS.expired).length },
    { id: "expiring", label: "Expiring soon", count: base.filter(DOC_FILTERS.expiring).length },
    { id: "valid", label: "Valid", count: base.filter(DOC_FILTERS.valid).length },
  ];

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <FilterRow>
        <WorkflowTabs tabs={tabs} value={tab} onChange={(id) => setTab(id as DocTab)} />
      </FilterRow>
      <DataPreviewTable
        columns={docCols}
        rows={rows}
        rowKey={(d) => `${d.document}-${d.ownerName}`}
        empty={<EmptyState icon={FileWarning} title="No documents in this view" description="No documents match this status and the active filters." />}
      />
    </div>
  );
}

/* --------------------------------- Audit trail ------------------------------ */

const auditCols: PreviewColumn<AuditRow>[] = [
  { key: "event", header: "Event", primary: true, cell: (a) => <span className="font-medium text-ink">{a.event}</span> },
  { key: "actor", header: "Actor", cell: (a) => <span className="text-ink-muted">{a.actor}</span> },
  { key: "module", header: "Module", cell: (a) => <StatusBadge tone="neutral" dot={false}>{a.module}</StatusBadge> },
  { key: "when", header: "When", cell: (a) => <span className="whitespace-nowrap text-xs text-ink-muted">{formatRelativeTime(a.datetime)}</span> },
  { key: "risk", header: "Risk", align: "right", cell: (a) => <StatusBadge tone={complianceRiskTone[a.risk]} dot={false}>{a.risk}</StatusBadge> },
];

function AuditSection() {
  const { filters } = useFilters();
  const rows = applyGlobalFilters(auditTrail, filters);
  return (
    <div className="space-y-6">
      <FilterRow>
        <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Every finance &amp; compliance action is logged</p>
      </FilterRow>
      <DataPreviewTable
        columns={auditCols}
        rows={rows}
        rowKey={(a) => `${a.event}-${a.datetime}`}
        empty={<EmptyState icon={ScrollText} title="No audit events" description="No logged actions match the active filters." />}
      />
    </div>
  );
}

/* --------------------------------- Risk flags ------------------------------- */

type FlagTab = "all" | "open" | "investigating" | "resolved";
const FLAG_FILTERS: Record<FlagTab, (r: RiskFlag) => boolean> = {
  all: () => true,
  open: (r) => r.status === "Open",
  investigating: (r) => r.status === "Investigating",
  resolved: (r) => r.status === "Resolved",
};

function RiskFlagsSection() {
  const { filters } = useFilters();
  const [tab, setTab] = useState<FlagTab>("all");
  const base = applyGlobalFilters(riskFlags, filters);
  const rows = base.filter(FLAG_FILTERS[tab]);

  const kpis: MinimalKpi[] = [
    { label: "Open", value: String(base.filter(FLAG_FILTERS.open).length), tone: "warning" },
    { label: "Investigating", value: String(base.filter(FLAG_FILTERS.investigating).length), tone: "info" },
    { label: "Resolved", value: String(base.filter(FLAG_FILTERS.resolved).length), tone: "success" },
    { label: "High severity", value: String(base.filter((r) => r.severity === "High").length), tone: "danger" },
  ];
  const tabs: WorkflowTab[] = [
    { id: "all", label: "All", count: base.length },
    { id: "open", label: "Open", count: base.filter(FLAG_FILTERS.open).length },
    { id: "investigating", label: "Investigating", count: base.filter(FLAG_FILTERS.investigating).length },
    { id: "resolved", label: "Resolved", count: base.filter(FLAG_FILTERS.resolved).length },
  ];

  return (
    <div className="space-y-6">
      <MinimalKpiStrip kpis={kpis} />
      <FilterRow>
        <WorkflowTabs tabs={tabs} value={tab} onChange={(id) => setTab(id as FlagTab)} />
      </FilterRow>
      {rows.length === 0 ? (
        <EmptyState icon={Flag} title="No risk flags in this view" description="No flags match this status and the active filters." />
      ) : (
        <RecordList>
          {rows.map((r) => (
            <CompactRecordCard
              key={r.id}
              id={r.id}
              title={r.flag}
              status={{ label: r.severity, tone: riskSeverityTone[r.severity] }}
              fields={[
                { label: "Status", value: <StatusBadge tone={riskStatusTone[r.status]} dot={false}>{r.status}</StatusBadge> },
                { label: "Detail", value: r.detail },
              ]}
            />
          ))}
        </RecordList>
      )}
    </div>
  );
}

/* --------------------------------- Router ----------------------------------- */

/** Renders one Finance & Compliance subsection by slug (see lib/dashboard/sections.ts). */
export function FinanceSubsection({ slug }: { slug: string }) {
  switch (slug) {
    case "financial-overview": return <FinancialOverviewSection />;
    case "cost-breakdown": return <CostBreakdownSection />;
    case "customer-payments": return <CustomerPaymentsSection />;
    case "refunds-adjustments": return <RefundsSection />;
    case "partner-facility-compliance": return <FacilityComplianceSection />;
    case "driver-compliance": return <DriverComplianceSection />;
    case "documents-expiry": return <DocumentsSection />;
    case "audit-trail": return <AuditSection />;
    case "risk-flags": return <RiskFlagsSection />;
    default: return <FinancialOverviewSection />;
  }
}
