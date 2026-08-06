"use client";

import type { ReactNode } from "react";
import {
  ShieldAlert,
  StickyNote,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Wallet,
  ClipboardList,
  Camera,
} from "lucide-react";
import type {
  FacilityOrderView,
  FacilityViewNote,
  FacilityViewItem,
  ReviewAcknowledgement,
} from "@/lib/api-client";
import { DetailSectionCard } from "@/components/minimal/DetailSectionCard";
import { StatusBadge } from "@/components/ui/primitives";
import { Button } from "@/components/ui/Button";
import { formatDateTime } from "@/lib/formatters";
import { NOTE_SECTION_LABELS, NOTE_SECTION_ORDER, priorityTone, priorityLabel } from "@/lib/note-format";
import { cn } from "@/lib/utils";

/* --------------------------------- Required Work ------------------------- */
export function RequiredWorkList({ items, compact }: { items: string[]; compact?: boolean }) {
  if (!items || items.length === 0) {
    return <p className="text-sm text-ink-muted">Work details will appear once the order is confirmed.</p>;
  }
  const shown = compact ? items.slice(0, 3) : items;
  return (
    <ul className="space-y-1.5">
      {shown.map((line, i) => (
        <li key={i} className="flex items-start gap-2 text-sm text-ink">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-rose" />
          <span className="min-w-0">{line}</span>
        </li>
      ))}
      {compact && items.length > 3 && (
        <li className="pl-6 text-xs text-ink-faint">+{items.length - 3} more</li>
      )}
    </ul>
  );
}

/* ------------------------------ Critical banner -------------------------- */
export function CriticalNotesBanner({ notes }: { notes: FacilityViewNote[] }) {
  if (!notes || notes.length === 0) return null;
  return (
    <div
      role="alert"
      className="rounded-2xl border border-danger/40 bg-danger/8 px-4 py-3"
    >
      <div className="flex items-center gap-2 text-danger">
        <ShieldAlert className="h-4 w-4 shrink-0" />
        <p className="text-xs font-semibold uppercase tracking-eyebrow">Critical — read before processing</p>
      </div>
      <ul className="mt-2 space-y-1">
        {notes.map((n) => (
          <li key={n.id} className="text-sm font-medium text-ink">• {n.text}</li>
        ))}
      </ul>
    </div>
  );
}

/* ------------------------------ Important Notes -------------------------- */
function NoteRow({ note }: { note: FacilityViewNote }) {
  const tone = priorityTone(note.priority);
  const isElevated = note.priority === "CRITICAL" || note.priority === "IMPORTANT";
  return (
    <li
      className={cn(
        "rounded-lg border px-3.5 py-2.5",
        note.priority === "CRITICAL"
          ? "border-danger/35 bg-danger/6"
          : note.priority === "IMPORTANT"
            ? "border-warning/35 bg-warning/6"
            : "border-border/60 bg-surface-2",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="min-w-0 text-sm text-ink">{note.text}</p>
        {isElevated && (
          <StatusBadge tone={tone} dot={false}>
            {priorityLabel(note.priority)}
          </StatusBadge>
        )}
      </div>
      {(note.is_amendment || note.source) && (
        <p className="mt-1 text-xxs text-ink-faint">
          {note.is_amendment ? "Added after confirmation" : ""}
          {note.is_amendment && note.source ? " · " : ""}
          {note.source ? note.source.replace(/_/g, " ").toLowerCase() : ""}
        </p>
      )}
    </li>
  );
}

export function ImportantNotes({ notes }: { notes: Record<string, FacilityViewNote[]> }) {
  const sections = NOTE_SECTION_ORDER.filter((key) => (notes[key]?.length ?? 0) > 0);
  if (sections.length === 0) {
    return (
      <DetailSectionCard title="Important Notes" icon={StickyNote}>
        <p className="text-sm text-ink-muted">No additional notes for this order.</p>
      </DetailSectionCard>
    );
  }
  return (
    <DetailSectionCard title="Important Notes" icon={StickyNote}>
      <div className="space-y-4">
        {sections.map((key) => (
          <div key={key}>
            <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">
              {NOTE_SECTION_LABELS[key] ?? key}
            </p>
            <ul className="mt-1.5 space-y-1.5">
              {notes[key].map((n) => (
                <NoteRow key={n.id} note={n} />
              ))}
            </ul>
          </div>
        ))}
      </div>
    </DetailSectionCard>
  );
}

/* ----------------------------- Review ack banner ------------------------- */
export function ReviewAckBanner({
  ack,
  onAcknowledge,
  pending,
}: {
  ack: ReviewAcknowledgement;
  onAcknowledge: () => void;
  pending: boolean;
}) {
  if (ack.up_to_date) {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-success/30 bg-success/8 px-4 py-2.5 text-sm text-success">
        <CheckCircle2 className="h-4 w-4 shrink-0" />
        <span>
          Details reviewed
          {ack.acknowledged_at ? ` · ${formatDateTime(ack.acknowledged_at)}` : ""}
        </span>
      </div>
    );
  }
  const reAck = ack.acknowledged && !ack.up_to_date;
  return (
    <div className="rounded-xl border border-warning/40 bg-warning/8 px-4 py-3">
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-ink">
            {reAck ? "The order details changed — review again before processing." : "Review the order details, notes and photos before processing."}
          </p>
          {ack.invalidation_reason && (
            <p className="mt-0.5 text-xxs text-ink-muted capitalize">{ack.invalidation_reason}</p>
          )}
        </div>
      </div>
      <Button variant="primary" size="md" className="mt-3 w-full sm:w-auto" disabled={pending} onClick={onAcknowledge}>
        {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
        I have reviewed the details, notes and photos
      </Button>
    </div>
  );
}

/* ------------------------------- Facility fee ---------------------------- */
export function FacilityFeeBlock({ finance }: { finance: FacilityOrderView["facility_finance"] }) {
  const money = (v?: number | null) =>
    v == null ? "—" : `${finance.currency ?? "AED"} ${Number(v).toFixed(2)}`;
  return (
    <DetailSectionCard title="Facility Fee" icon={Wallet}>
      <div className="flex items-baseline justify-between">
        <span className="text-sm text-ink-muted">Your fee for this order</span>
        <span className="font-mono text-lg font-semibold text-ink tnum">{money(finance.fee_total)}</span>
      </div>
      {finance.per_item.length > 0 && (
        <ul className="mt-3 divide-y divide-border/60">
          {finance.per_item.map((li, i) => (
            <li key={i} className="flex items-center justify-between gap-3 py-1.5 text-xs">
              <span className="min-w-0 truncate text-ink-muted">{li.name ?? "Item"}</span>
              <span className="shrink-0 font-mono text-ink tnum">{money(li.fee)}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 flex items-center gap-1.5 text-xxs text-ink-faint">
        Payout status: <span className="font-medium capitalize text-ink-muted">{finance.payout_status ?? "pending"}</span>
      </p>
      {!finance.complete && (
        <p className="mt-1 text-xxs text-warning">Fee finalises once any facility quote is confirmed.</p>
      )}
    </DetailSectionCard>
  );
}

/* ------------------------------- Items ----------------------------------- */
function Attr({ label, value }: { label: string; value: ReactNode }) {
  if (value == null || value === "" || value === false) return null;
  return (
    <div className="min-w-0">
      <dt className="text-[0.6rem] font-medium uppercase tracking-eyebrow text-ink-faint">{label}</dt>
      <dd className="mt-0.5 break-words text-xs font-medium text-ink">{value}</dd>
    </div>
  );
}

function Callout({ tone, label, text }: { tone: "warning" | "danger"; label: string; text: string }) {
  return (
    <div
      className={cn(
        "rounded-lg border px-2.5 py-1.5",
        tone === "danger" ? "border-danger/30 bg-danger/6" : "border-warning/30 bg-warning/6",
      )}
    >
      <span className={cn("text-[0.6rem] font-semibold uppercase tracking-eyebrow", tone === "danger" ? "text-danger" : "text-warning")}>
        {label}
      </span>
      <p className="text-xs text-ink">{text}</p>
    </div>
  );
}

function WashFoldBlock({ d }: { d: NonNullable<FacilityViewItem["wash_fold"]> }) {
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-lg bg-canvas px-2.5 py-2 sm:grid-cols-3">
      <Attr label="Bags" value={d.bags} />
      <Attr label="Est. weight" value={d.estimated_weight != null ? `${d.estimated_weight} kg` : null} />
      <Attr label="Confirmed weight" value={d.confirmed_weight != null ? `${d.confirmed_weight} kg` : null} />
      <Attr label="Pricing tier" value={d.pricing_tier} />
      <Attr label="Separation" value={d.separation_notes} />
    </dl>
  );
}

function DimensionBlock({ d }: { d: NonNullable<FacilityViewItem["dimension"]> }) {
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-lg bg-canvas px-2.5 py-2 sm:grid-cols-3">
      <Attr label="Customer estimate" value={d.estimated_measure != null ? `${d.estimated_measure} m²` : null} />
      <Attr label="Confirmed" value={d.confirmed_sqm != null ? `${d.confirmed_sqm} m²` : null} />
      <Attr label="Rate / m²" value={d.rate_per_sqm} />
      <Attr label="Minimum charge" value={d.minimum_charge} />
      <Attr label="Measurement" value={d.measurement_status} />
    </dl>
  );
}

function SpecialistBlock({ d }: { d: NonNullable<FacilityViewItem["specialist"]> }) {
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-lg bg-canvas px-2.5 py-2 sm:grid-cols-3">
      <Attr label="Material" value={d.material} />
      <Attr label="Cleaning" value={d.cleaning_requirement} />
      <Attr label="Repair" value={d.repair_requirement} />
      <Attr label="Inspection" value={d.inspection_status} />
      <Attr label="Quotation" value={d.quotation_status} />
    </dl>
  );
}

export function ItemsBreakdown({ items }: { items: FacilityViewItem[] }) {
  if (!items || items.length === 0) return null;
  return (
    <DetailSectionCard title="Items & Quantities" icon={ClipboardList}>
      <ul className="space-y-3">
        {items.map((it) => (
          <li key={it.id} className="rounded-xl border border-border/60 bg-surface-2 px-3.5 py-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-ink">
                  {it.quantity != null ? `${it.quantity}× ` : ""}
                  {it.name}
                </p>
                {it.service && <p className="text-xxs text-ink-muted">{it.service}</p>}
              </div>
              <div className="flex shrink-0 flex-wrap items-center justify-end gap-1.5">
                {it.luxury_flag && <StatusBadge tone="plum" dot={false}>Luxury</StatusBadge>}
                {it.inspection_required && <StatusBadge tone="warning" dot={false}>Inspect</StatusBadge>}
                {it.requires_quote && <StatusBadge tone="info" dot={false}>Quote</StatusBadge>}
                {(it.photo_count ?? 0) > 0 && (
                  <span className="inline-flex items-center gap-1 text-xxs text-ink-faint">
                    <Camera className="h-3 w-3" />
                    {it.photo_count}
                  </span>
                )}
              </div>
            </div>

            {/* Grounded attributes */}
            <dl className="mt-2.5 grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-4">
              <Attr label="Colour" value={it.colour} />
              <Attr label="Brand" value={it.brand_candidate} />
              <Attr label="Material" value={it.material} />
              <Attr label="Measurements" value={it.measurements} />
              <Attr label="Price type" value={it.price_type} />
              <Attr label="Turnaround" value={it.turnaround} />
              <Attr label="Facility fee" value={it.facility_fee != null ? `AED ${Number(it.facility_fee).toFixed(2)}` : null} />
            </dl>

            {it.instruction && (
              <p className="mt-2 rounded-lg bg-canvas px-2.5 py-1.5 text-xs text-ink">{it.instruction}</p>
            )}

            {/* Care callouts */}
            {(it.stains || it.existing_damage || it.special_handling) && (
              <div className="mt-2 space-y-1.5">
                {it.existing_damage && <Callout tone="danger" label="Existing damage" text={it.existing_damage} />}
                {it.stains && <Callout tone="warning" label="Stains" text={it.stains} />}
                {it.special_handling && <Callout tone="warning" label="Special handling" text={it.special_handling} />}
              </div>
            )}

            {/* Category-specific block */}
            {it.wash_fold && <div className="mt-2"><WashFoldBlock d={it.wash_fold} /></div>}
            {it.dimension && <div className="mt-2"><DimensionBlock d={it.dimension} /></div>}
            {it.specialist && <div className="mt-2"><SpecialistBlock d={it.specialist} /></div>}
          </li>
        ))}
      </ul>
    </DetailSectionCard>
  );
}
