"use client";

import { formatCurrency } from "@/lib/dashboard/formatters";
import type { LineItemDTO } from "@/lib/dashboard/whatsapp-agent-api";
import { itemCount, type OrderWithPricing } from "./data";
import { Chip } from "./primitives";

/** Human-readable "per unit" suffix for a line's pricing basis. */
const UNIT_LABEL: Record<string, string> = {
  ITEM: "per item",
  PAIR: "per pair",
  BAG: "per bag",
  KG: "per kg",
  SQM: "per sqm",
};

function unitLabel(unit: string): string {
  return UNIT_LABEL[unit?.toUpperCase()] ?? (unit ? `per ${unit.toLowerCase()}` : "");
}

/**
 * Itemized service breakdown.
 *
 * When the order carries backend catalogue pricing (`line_items`), it renders a
 * priced table + a VAT-aware summary. Otherwise it falls back to the original
 * item / quantity / category view with no invented per-line pricing.
 */
export function OrderItemsTable({ order }: { order: OrderWithPricing }) {
  const lineItems = order.line_items;
  if (lineItems && lineItems.length > 0) {
    return <PricedItemsTable order={order} lineItems={lineItems} />;
  }
  return <PlainItemsTable order={order} />;
}

/* --------------------------- no-pricing fallback ---------------------------- */

function PlainItemsTable({ order }: { order: OrderWithPricing }) {
  const total = itemCount(order);
  return (
    <div>
      <div className="overflow-hidden rounded-xl border border-border/70">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border/60 bg-surface-2 text-left">
              <th className="px-4 py-2.5 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Item</th>
              <th className="px-4 py-2.5 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Service</th>
              <th className="px-4 py-2.5 text-right text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Qty</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/50">
            {order.items.map((it) => (
              <tr key={it.name} className="transition-colors hover:bg-surface-2/50">
                <td className="px-4 py-3 font-medium text-ink">{it.name}</td>
                <td className="px-4 py-3 text-ink-muted">{order.service}</td>
                <td className="px-4 py-3 text-right font-mono text-ink tnum">×{it.qty}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-border/60 bg-surface-2/60">
              <td className="px-4 py-2.5 text-xs font-semibold text-ink" colSpan={2}>Total items</td>
              <td className="px-4 py-2.5 text-right font-mono text-sm font-semibold text-ink tnum">{total}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}

/* ---------------------------- priced line items ----------------------------- */

function UnitPriceCell({ line, currency }: { line: LineItemDTO; currency: string }) {
  if (line.unit_price == null) {
    return <span className="text-ink-faint">On inspection</span>;
  }
  const showStrike = line.regular_price != null && line.regular_price !== line.unit_price;
  return (
    <div className="flex flex-col items-end gap-1">
      <span className="inline-flex items-baseline gap-1.5">
        {showStrike && (
          <span className="text-xxs text-ink-faint line-through">{formatCurrency(line.regular_price as number, currency)}</span>
        )}
        <span className="font-mono text-ink tnum">
          {line.is_starting_price && <span className="mr-0.5 text-ink-muted">From </span>}
          {formatCurrency(line.unit_price, currency)}
        </span>
      </span>
      <span className="text-xxs text-ink-faint">{unitLabel(line.pricing_unit)}</span>
      {line.is_starting_price && <Chip tone="neutral">Starting price</Chip>}
    </div>
  );
}

function LineTotalCell({ line, currency }: { line: LineItemDTO; currency: string }) {
  if (line.line_total != null) {
    return <span className="font-mono font-medium text-ink tnum">{formatCurrency(line.line_total, currency)}</span>;
  }
  if (line.line_kind === "pending") {
    return <span className="text-xs text-ink-faint">Pending inspection</span>;
  }
  return <span className="text-ink-faint">—</span>;
}

function SummaryRow({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4 px-4 py-2">
      <span className={strong ? "text-sm font-semibold text-ink" : "text-xs text-ink-muted"}>{label}</span>
      <span className={strong ? "font-mono text-sm font-semibold text-ink tnum" : "font-mono text-xs text-ink tnum"}>{value}</span>
    </div>
  );
}

function PricedItemsTable({ order, lineItems }: { order: OrderWithPricing; lineItems: LineItemDTO[] }) {
  const pricing = order.pricing;
  const currency = pricing?.currency ?? "AED";
  const vatPct = pricing ? Math.round(pricing.vat_rate * 100) : 5;
  const anyPending = lineItems.some((l) => l.line_kind === "pending" || l.line_total == null);
  const pendingNote = (pricing?.has_pending_inspection ?? false) || anyPending;

  const money = (v: number | null | undefined) => (v != null ? formatCurrency(v, currency) : "—");

  return (
    <div className="space-y-3">
      {order.catalogue_category && (
        <div className="flex items-center gap-2">
          <span className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Catalogue</span>
          <Chip tone="info">{order.catalogue_category}</Chip>
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-border/70">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border/60 bg-surface-2 text-left">
              <th className="px-4 py-2.5 text-right text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Qty</th>
              <th className="px-4 py-2.5 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Item</th>
              <th className="px-4 py-2.5 text-right text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Unit price</th>
              <th className="px-4 py-2.5 text-right text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Line total</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/50">
            {lineItems.map((line) => (
              <tr key={line.item_code} className="align-top transition-colors hover:bg-surface-2/50">
                <td className="px-4 py-3 text-right font-mono text-ink tnum">×{line.quantity}</td>
                <td className="px-4 py-3">
                  <span className="font-medium text-ink">{line.name}</span>
                  {line.requires_inspection && (
                    <span className="mt-1 block text-xxs text-ink-faint">Priced after inspection</span>
                  )}
                </td>
                <td className="px-4 py-3 text-right"><UnitPriceCell line={line} currency={currency} /></td>
                <td className="px-4 py-3 text-right"><LineTotalCell line={line} currency={currency} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {pricing && (
        <div className="overflow-hidden rounded-xl border border-border/70 bg-surface-2/40">
          <SummaryRow label="Subtotal (excl. VAT)" value={money(pricing.subtotal_excluding_vat)} />
          <SummaryRow label={`VAT (${vatPct}%)`} value={money(pricing.vat_amount)} />
          <div className="border-t border-border/60">
            <SummaryRow
              label={pricing.is_estimated ? "Estimated total (incl. VAT)" : "Total (incl. VAT)"}
              value={money(pricing.estimated_total_including_vat)}
              strong
            />
          </div>
        </div>
      )}

      {pendingNote && (
        <p className="text-xs text-ink-muted">Final price pending inspection</p>
      )}
      {pricing?.disclaimer && (
        <p className="text-xxs text-ink-faint">{pricing.disclaimer}</p>
      )}
    </div>
  );
}
