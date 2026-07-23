"use client";

import {
  CreditCard, ReceiptText, ShieldCheck, RefreshCw, BadgeCheck, FileText,
  AlertTriangle, StickyNote, MapPin, Wallet,
} from "lucide-react";
import {
  DetailPageShell, DetailColumns, DetailSectionCard, Field, FieldGrid, Chip,
  ActionMenu, StatusBadge, type MenuItem,
} from "@/components/dashboard/minimal";
import {
  paymentStatusTone, chargeStatusTone, type PaymentRecord,
} from "@/lib/dashboard/operations-data";
import { formatCurrency, formatRelativeTime } from "@/lib/dashboard/formatters";

const ACTIONS = (p: PaymentRecord): MenuItem[] => [
  { label: "Mark as paid", icon: BadgeCheck, disabled: p.status === "Paid" },
  { label: "Retry charge", icon: RefreshCw, disabled: p.status !== "Failed" },
  { label: "Send invoice", icon: FileText, disabled: p.method !== "Invoice" },
  { label: "Request refund", icon: ReceiptText, approval: true, disabled: p.status !== "Paid" },
  { label: "Flag payment issue", icon: AlertTriangle, tone: "danger" },
  { label: "Add note", icon: StickyNote },
];

export function PaymentDetailPage({ payment, backHref }: { payment: PaymentRecord; backHref: string }) {
  return (
    <DetailPageShell
      backHref={backHref}
      backLabel="Customer Payments"
      eyebrow="Customer payment"
      title={<span className="font-mono">{payment.orderId}</span>}
      status={
        <>
          <StatusBadge tone={paymentStatusTone[payment.status] ?? "neutral"} dot={false}>{payment.status}</StatusBadge>
          <StatusBadge tone={chargeStatusTone[payment.chargeStatus] ?? "neutral"} dot={false}>{payment.chargeStatus}</StatusBadge>
        </>
      }
      actions={<ActionMenu items={ACTIONS(payment)} />}
    >
      <DetailColumns
        main={
          <DetailSectionCard title="Payment" icon={CreditCard}>
            <FieldGrid>
              <Field label="Order" value={payment.orderId} mono />
              <Field label="Customer" value={payment.customer} />
              <Field label="Service" value={payment.service} />
              <Field label="Amount" value={formatCurrency(payment.amount)} mono />
              <Field label="Method" value={payment.method} />
              <Field label="Charge status" value={<Chip tone={chargeStatusTone[payment.chargeStatus] ?? "neutral"}>{payment.chargeStatus}</Chip>} />
              <Field label="Channel" value={payment.channel} />
              <Field label="Created" value={formatRelativeTime(payment.createdAt)} />
              <Field
                label="Area / City"
                value={<span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3 text-ink-faint" />{payment.area}</span>}
              />
            </FieldGrid>
          </DetailSectionCard>
        }
        sidebar={
          <>
            <DetailSectionCard title="Amount" icon={Wallet}>
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-xs text-ink-muted">Total</span>
                <span className="font-mono text-2xl font-semibold tracking-tight text-ink tnum">{formatCurrency(payment.amount)}</span>
              </div>
              <div className="mt-3 flex items-center justify-between">
                <span className="text-sm text-ink-muted">Status</span>
                <Chip tone={paymentStatusTone[payment.status] ?? "neutral"}>{payment.status}</Chip>
              </div>
            </DetailSectionCard>
            <DetailSectionCard title="Privacy" icon={ShieldCheck}>
              <p className="text-xs leading-relaxed text-ink-muted">
                Amount, method and status only. No card numbers, CVV or bank details are stored or shown. Refunds route through approval before any money moves.
              </p>
            </DetailSectionCard>
          </>
        }
      />
    </DetailPageShell>
  );
}
