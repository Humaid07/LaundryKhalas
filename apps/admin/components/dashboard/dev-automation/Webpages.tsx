"use client";

import Link from "next/link";
import { FlaskConical, Globe2, PlugZap, Send, ArrowRight, Info } from "lucide-react";
import {
  MinimalKpiStrip, DataPreviewTable, DetailSectionCard, Field, FieldGrid,
  StatusBadge, type MinimalKpi, type PreviewColumn,
} from "@/components/dashboard/minimal";

/**
 * Webpages — Dev & Automation subsection (SCAFFOLD ONLY).
 *
 * Planned workflow: pages created on a teammate's local website machine are later
 * pulled into this dashboard through an approved API and listed here for SEO
 * review. Nothing is connected yet — every value below is a mock-safe placeholder,
 * clearly labelled, and NO external API / scraper / sync runs. Real intake is
 * deferred (see docs/build-reports/2026-07-29-webpages-section.md).
 */

type PlaceholderPage = {
  id: string;
  title: string;
  path: string;
  market: string;
  city: string;
  type: string;
  createdBy: string;
  seoStatus: string;
};

// Clearly-marked DEVELOPMENT PLACEHOLDERS — not real pulled data.
const PLACEHOLDER_PAGES: PlaceholderPage[] = [
  { id: "ph-1", title: "Sample area page (placeholder)", path: "/local/dubai-marina", market: "UAE", city: "Dubai", type: "Hyperlocal", createdBy: "—", seoStatus: "Pending review" },
  { id: "ph-2", title: "Sample service page (placeholder)", path: "/local/curtain-cleaning", market: "UAE", city: "Abu Dhabi", type: "Service", createdBy: "—", seoStatus: "Pending review" },
  { id: "ph-3", title: "Sample city page (placeholder)", path: "/local/sharjah", market: "UAE", city: "Sharjah", type: "City", createdBy: "—", seoStatus: "Needs local E-E-A-T" },
];

const KPIS: MinimalKpi[] = [
  { label: "Pages Pulled", value: "0", hint: "not connected" },
  { label: "Pending SEO Review", value: "0" },
  { label: "Needs Local E-E-A-T", value: "0" },
  { label: "Optimised", value: "0" },
];

const COLUMNS: PreviewColumn<PlaceholderPage>[] = [
  {
    key: "title",
    header: "Page",
    primary: true,
    cell: (r) => (
      <div className="flex items-center gap-2">
        <span className="font-medium text-ink">{r.title}</span>
        <StatusBadge tone="neutral" dot={false}>Placeholder</StatusBadge>
      </div>
    ),
  },
  { key: "path", header: "URL / local path", cell: (r) => <span className="font-mono text-xs text-ink-muted">{r.path}</span> },
  { key: "market", header: "Market", cell: (r) => r.market },
  { key: "city", header: "City / area", cell: (r) => r.city },
  { key: "type", header: "Page type", cell: (r) => r.type },
  { key: "seoStatus", header: "SEO status", cell: (r) => <StatusBadge tone="warning">{r.seoStatus}</StatusBadge> },
];

export function WebpagesTab() {
  return (
    <div className="space-y-6">
      {/* 1 · Page Intake Overview */}
      <DetailSectionCard title="Page Intake Overview" icon={Globe2}>
        <MinimalKpiStrip kpis={KPIS} />
        <p className="mt-3 text-xxs text-ink-faint">
          Placeholder counts — page intake is not connected yet.
        </p>
      </DetailSectionCard>

      {/* 2 · New Webpages */}
      <DetailSectionCard
        title="New Webpages"
        icon={FlaskConical}
        action={<StatusBadge tone="info">Development placeholders</StatusBadge>}
      >
        <div className="mb-3 flex items-start gap-2.5 rounded-xl border border-info/20 bg-info/[0.06] px-3.5 py-2.5">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-info" />
          <p className="text-xxs leading-relaxed text-ink-muted">
            The rows below are <span className="font-semibold text-ink">development placeholders</span>, not
            real pulled data. Once the local-machine API is connected, pulled pages will appear here with
            their real title, URL / local path, market, city / area, page type, created-by, created date,
            SEO status, local E-E-A-T status and last-pulled time.
          </p>
        </div>
        <DataPreviewTable
          columns={COLUMNS}
          rows={PLACEHOLDER_PAGES}
          rowKey={(r) => r.id}
        />
      </DetailSectionCard>

      {/* 3 · Future API Pull Status */}
      <DetailSectionCard title="Future API Pull Status" icon={PlugZap}>
        <p className="mb-4 text-sm text-ink-muted">
          Pages created on the local website machine will later be pulled through an approved API and
          listed here for SEO review.
        </p>
        <FieldGrid cols={3}>
          <Field label="API connection" value={<StatusBadge tone="danger">Not connected</StatusBadge>} />
          <Field label="Last sync" value={<span className="text-ink-muted">Not available</span>} />
          <Field label="Source" value={<StatusBadge tone="neutral">Pending integration</StatusBadge>} />
        </FieldGrid>
      </DetailSectionCard>

      {/* 4 · SEO Handoff */}
      <DetailSectionCard title="SEO Handoff" icon={Send}>
        <p className="text-sm text-ink-muted">
          Once pages are pulled, the SEO team will be notified to optimise local E-E-A-T content before
          publishing or final review.
        </p>
        <Link
          href="/seo-agents/overview"
          className="mt-4 inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-accent-steel hover:bg-accent-steel/10"
        >
          Go to SEO Agents <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </DetailSectionCard>
    </div>
  );
}
