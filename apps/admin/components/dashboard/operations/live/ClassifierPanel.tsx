"use client";

import { useState } from "react";
import { Brain, Check, Pencil, RefreshCw, ShieldAlert, X } from "lucide-react";
import { StatusBadge } from "@/components/dashboard/ui/primitives";
import { Button } from "@/components/dashboard/ui/Button";
import { EmptyState, LoadingState } from "@/components/dashboard/ui/states";
import { useLiveAgentData } from "./useLiveAgentData";
import {
  agentApi,
  type ClassificationDTO,
  type ClassificationCorrectionPayload,
} from "@/lib/dashboard/whatsapp-agent-api";

// Correction option lists mirror the backend taxonomy (classifier/taxonomy.py).
// Kept intentionally short here — Operations corrects the two fields that matter
// most for routing/analytics; the backend validates against the full vocabulary.
const PRIMARY_INTENT_OPTIONS = [
  "GREETING", "GENERAL_ENQUIRY", "SERVICE_ENQUIRY", "SERVICE_SELECTION",
  "BOOKING_START", "BOOKING_CONTINUE", "PRICE_ENQUIRY", "PRICE_PUSHBACK",
  "DISCOUNT_REQUEST", "PROCESS_ENQUIRY", "ADDRESS_PROVIDED", "PICKUP_SLOT_ENQUIRY",
  "PICKUP_SLOT_SELECTION", "EXACT_PICKUP_TIME_REQUEST", "ORDER_CONFIRMATION",
  "PAYMENT_METHOD_ENQUIRY", "STRIPE_PAYMENT_QUERY", "CASH_PAYMENT_REQUEST",
  "ORDER_STATUS_ENQUIRY", "REPAIR_REQUEST", "ALTERATION_REQUEST",
  "SPECIALIST_RESTORATION_REQUEST", "COMPLAINT", "REFUND_REQUEST",
  "REPROCESSING_REQUEST", "HUMAN_AGENT_REQUEST", "B2B_ENQUIRY",
  "UNSUPPORTED_REQUEST", "UNKNOWN",
];
const SERVICE_DOMAIN_OPTIONS = [
  "WASH_AND_FOLD", "CLEAN_AND_PRESS", "PRESS_ONLY", "BEDDING_AND_HOME_TEXTILES",
  "CURTAINS", "CARPETS_AND_RUGS", "SOFA_AND_UPHOLSTERY", "SHOES",
  "BAGS_AND_ACCESSORIES", "ALTERATIONS_AND_GARMENT_REPAIR",
  "WEDDING_AND_EVENING_DRESSES", "LEATHER", "RESTORATION", "TRADITIONAL_WEAR",
  "SUITS_AND_BLAZERS", "EXPRESS", "B2B_COMMERCIAL", "MULTI_SERVICE", "UNKNOWN",
];

function pct(n: number | null | undefined): string {
  return n == null ? "—" : `${Math.round(n * 100)}%`;
}
function confTone(n: number): "success" | "warning" | "neutral" {
  if (n >= 0.8) return "success";
  if (n >= 0.55) return "warning";
  return "neutral";
}
function fmtTime(v?: string | null): string {
  if (!v) return "";
  const d = new Date(v);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleString("en-GB", { timeZone: "Asia/Dubai", dateStyle: "short", timeStyle: "short" });
}

function CorrectionEditor({
  conversationId, row, onDone,
}: {
  conversationId: string;
  row: ClassificationDTO;
  onDone: () => void;
}) {
  const [primary, setPrimary] = useState(row.corrected_primary_intent ?? row.primary_intent);
  const [service, setService] = useState(row.corrected_service_domain ?? row.service_domain);
  const [reason, setReason] = useState(row.correction_reason ?? "");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function save() {
    setSaving(true);
    setErr(null);
    const payload: ClassificationCorrectionPayload = {
      corrected_by: "Operations",
      primary_intent: primary !== row.primary_intent ? primary : null,
      service_domain: service !== row.service_domain ? service : null,
      reason: reason.trim() || null,
    };
    try {
      await agentApi.correctClassification(conversationId, row.id, payload);
      onDone();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not save the correction.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mt-2 space-y-2 rounded-lg border border-border bg-surface p-2.5">
      <div className="grid gap-2 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-xxs font-semibold text-ink-muted">
          Primary intent
          <select value={primary} onChange={(e) => setPrimary(e.target.value)}
            className="rounded-md border border-border bg-surface-2 px-2 py-1 text-xs text-ink">
            {PRIMARY_INTENT_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xxs font-semibold text-ink-muted">
          Service domain
          <select value={service} onChange={(e) => setService(e.target.value)}
            className="rounded-md border border-border bg-surface-2 px-2 py-1 text-xs text-ink">
            {SERVICE_DOMAIN_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
        </label>
      </div>
      <input value={reason} onChange={(e) => setReason(e.target.value)}
        placeholder="Reason (optional)"
        className="w-full rounded-md border border-border bg-surface-2 px-2 py-1 text-xs text-ink" />
      {err && <p className="text-xxs text-danger">{err}</p>}
      <div className="flex items-center gap-2">
        <Button size="sm" variant="primary" onClick={save} disabled={saving}>
          <Check className="h-3.5 w-3.5" /> {saving ? "Saving…" : "Save correction"}
        </Button>
        <Button size="sm" variant="ghost" onClick={onDone} disabled={saving}>
          <X className="h-3.5 w-3.5" /> Cancel
        </Button>
      </div>
    </div>
  );
}

function ClassificationRow({
  conversationId, row, onCorrected,
}: {
  conversationId: string;
  row: ClassificationDTO;
  onCorrected: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const corrected = row.corrected_primary_intent || row.corrected_service_domain;

  return (
    <li className="rounded-lg border border-border bg-surface-2/40 p-2.5">
      <div className="flex flex-wrap items-center gap-1.5">
        <StatusBadge tone="info">{row.primary_intent}</StatusBadge>
        {row.service_domain !== "UNKNOWN" && (
          <span className="text-xxs font-medium text-ink-muted">{row.service_domain}</span>
        )}
        <StatusBadge tone={confTone(row.intent_confidence)} dot>{pct(row.intent_confidence)}</StatusBadge>
        {row.requires_human && (
          <StatusBadge tone="danger"><ShieldAlert className="mr-0.5 inline h-3 w-3" />Human</StatusBadge>
        )}
        {row.needs_clarification && <StatusBadge tone="warning">Clarify</StatusBadge>}
        {row.shadow_mode && <StatusBadge tone="neutral">Shadow</StatusBadge>}
        <span className="ml-auto text-xxs text-ink-faint">{fmtTime(row.created_at)}</span>
      </div>

      <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-xxs text-ink-muted">
        {row.recommended_route && <span>route: <span className="text-ink">{row.recommended_route}</span></span>}
        <span>sentiment: <span className="text-ink">{row.sentiment}</span>{row.frustration_level > 0 ? ` (${row.frustration_level})` : ""}</span>
        {row.pricing_intent !== "NONE" && <span>pricing: <span className="text-ink">{row.pricing_intent}</span></span>}
        {row.payment_intent !== "NONE" && <span>payment: <span className="text-ink">{row.payment_intent}</span></span>}
        {row.repair_intent !== "NONE" && <span>repair: <span className="text-ink">{row.repair_intent}</span></span>}
        {row.complaint_type !== "NONE" && <span>complaint: <span className="text-ink">{row.complaint_type}</span></span>}
        {row.secondary_intents.length > 0 && <span>+ {row.secondary_intents.join(", ")}</span>}
        <span>{row.classifier_status}{row.classifier_model ? ` · ${row.classifier_model}` : ""}{row.latency_ms != null ? ` · ${Math.round(row.latency_ms)}ms` : ""}</span>
      </div>

      {corrected && (
        <p className="mt-1.5 text-xxs text-success">
          Corrected → {row.corrected_primary_intent ?? row.primary_intent}
          {row.corrected_service_domain ? ` / ${row.corrected_service_domain}` : ""}
          {row.corrected_by ? ` by ${row.corrected_by}` : ""}
        </p>
      )}

      {editing ? (
        <CorrectionEditor conversationId={conversationId} row={row}
          onDone={() => { setEditing(false); onCorrected(); }} />
      ) : (
        <button onClick={() => setEditing(true)}
          className="mt-1.5 inline-flex items-center gap-1 text-xxs font-semibold text-ink-muted hover:text-ink">
          <Pencil className="h-3 w-3" /> Correct
        </button>
      )}
    </li>
  );
}

/**
 * Per-conversation intent-classifier panel (Stage 1 shadow + Stage 2 corrections).
 * Shows each classified turn — intent, service, confidence, recommended route,
 * sentiment/human/clarify signals — and lets Operations correct the primary
 * intent / service domain (stored separately; never reverses a side effect).
 * Renders inside the Operations deep-link conversation view.
 */
export function ClassifierPanel({ conversationId }: { conversationId: string }) {
  const { data, loading, error, refresh } = useLiveAgentData<ClassificationDTO[]>(
    () => agentApi.listClassifications(conversationId),
    [conversationId],
  );

  return (
    <section className="border-t border-border p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="flex items-center gap-2 text-xs font-semibold text-ink">
          <Brain className="h-4 w-4 text-rose" /> Intent classifier
        </span>
        <button onClick={refresh} aria-label="Refresh classifications"
          className="rounded-lg p-1 text-ink-faint hover:bg-surface-2 hover:text-ink">
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </div>

      {loading ? (
        <LoadingState label="Loading classifications…" />
      ) : error ? (
        <p className="text-xxs text-ink-muted">{error}</p>
      ) : !data || data.length === 0 ? (
        <EmptyState icon={Brain} title="No classifications yet"
          description="Classifier results for this conversation will appear here once turns are processed." />
      ) : (
        <ul className="space-y-2">
          {data.map((row) => (
            <ClassificationRow key={row.id} conversationId={conversationId}
              row={row} onCorrected={refresh} />
          ))}
        </ul>
      )}
    </section>
  );
}
