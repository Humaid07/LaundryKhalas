"use client";

import type { Order } from "@/lib/dashboard/types";
import { itemCount } from "./data";

/**
 * Itemized service breakdown. Prices are not part of the mock order line-items,
 * so the table shows item / quantity / category and the order total as the
 * footer — no invented per-line pricing.
 */
export function OrderItemsTable({ order }: { order: Order }) {
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
