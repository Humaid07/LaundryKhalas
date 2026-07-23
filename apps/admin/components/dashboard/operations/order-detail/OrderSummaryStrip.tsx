"use client";

import {
  User, Sparkles, CalendarClock, Truck, CreditCard, Wallet, Coins, Building2, Radio,
  type LucideIcon,
} from "lucide-react";
import { formatCurrency } from "@/lib/dashboard/formatters";
import { deliverySlotLabel, type OrderWithPricing } from "./data";

/**
 * A clean, scannable row of summary pills — the at-a-glance strip below the
 * header. Wraps responsively; each pill is icon + label + value.
 */
function Pill({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-border/70 bg-surface px-3.5 py-2.5 shadow-card">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-rose/8 text-rose">
        <Icon className="h-4 w-4" />
      </span>
      <div className="min-w-0">
        <p className="text-xxs font-medium uppercase tracking-eyebrow text-ink-faint">{label}</p>
        <p className="truncate text-sm font-semibold text-ink">{value}</p>
      </div>
    </div>
  );
}

export function OrderSummaryStrip({ order }: { order: OrderWithPricing }) {
  // Prefer the catalogue-priced total when present; label it "Est. total" so an
  // estimate is never read as a guaranteed amount. Falls back to `amount`.
  const pricing = order.pricing;
  const amountValue =
    pricing?.estimated_total_including_vat != null
      ? formatCurrency(pricing.estimated_total_including_vat, pricing.currency)
      : formatCurrency(order.amount);
  const amountLabel = pricing?.is_estimated ? "Est. total" : "Amount";

  const pills: { icon: LucideIcon; label: string; value: string }[] = [
    { icon: User, label: "Customer", value: order.customer },
    { icon: Sparkles, label: "Service", value: order.service },
    { icon: CalendarClock, label: "Pickup slot", value: order.pickupSlot },
    { icon: Truck, label: "Delivery slot", value: deliverySlotLabel(order) },
    { icon: CreditCard, label: "Payment", value: order.payment },
    { icon: Wallet, label: "Method", value: order.channel === "B2B" ? "Invoice" : "Card / POD" },
    { icon: Coins, label: amountLabel, value: amountValue },
    { icon: Truck, label: "Driver", value: order.driver ?? "Unassigned" },
    { icon: Building2, label: "Facility", value: order.facility || "Unassigned" },
    { icon: Radio, label: "Source", value: order.channel },
  ];

  return (
    <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-5">
      {pills.map((p) => (
        <Pill key={p.label} {...p} />
      ))}
    </div>
  );
}
