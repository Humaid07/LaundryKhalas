"use client";

import Link from "next/link";
import { Headset, Factory, Truck, ClipboardList, ArrowRight, type LucideIcon } from "lucide-react";
import { StatusBadge } from "@/components/dashboard/ui/primitives";
import type { Tone } from "@/lib/dashboard/types";
import { cn } from "@/lib/utils";

type SectionCard = {
  slug: string;
  title: string;
  description: string;
  icon: LucideIcon;
  status: { label: string; tone: Tone };
  kpis: { label: string; value: string }[];
};

/** Clean, executive-friendly landing cards — one per Operations subsection. */
const CARDS: SectionCard[] = [
  {
    slug: "customer-facing",
    title: "Customer Facing",
    description: "Manage WhatsApp conversations, tickets, cancellations, customer follow-ups, and support escalations.",
    icon: Headset,
    status: { label: "7 pending replies", tone: "warning" },
    kpis: [
      { label: "Open conversations", value: "24" },
      { label: "Pending replies", value: "8" },
      { label: "Urgent tickets", value: "5" },
    ],
  },
  {
    slug: "facility-facing",
    title: "Facility Facing",
    description: "Manage facility assignments, cleaning progress, quality checks, facility issues, and delivery handoff.",
    icon: Factory,
    status: { label: "3 delayed", tone: "danger" },
    kpis: [
      { label: "In cleaning", value: "18" },
      { label: "Quality pending", value: "6" },
      { label: "Delayed orders", value: "3" },
    ],
  },
  {
    slug: "drivers",
    title: "Drivers",
    description: "Manage pickup/delivery drivers, driver queues, delivery progress, route status, and driver issues.",
    icon: Truck,
    status: { label: "12 active", tone: "success" },
    kpis: [
      { label: "Active drivers", value: "12" },
      { label: "Pickups assigned", value: "9" },
      { label: "Delayed deliveries", value: "4" },
    ],
  },
  {
    slug: "customer-orders",
    title: "Customer Orders",
    description: "Manage all customer orders from WhatsApp, website, app, B2B, and manual bookings.",
    icon: ClipboardList,
    status: { label: "82 active", tone: "rose" },
    kpis: [
      { label: "Active orders", value: "82" },
      { label: "Completed today", value: "31" },
      { label: "Changes pending", value: "7" },
    ],
  },
];

export function OperationsLanding() {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {CARDS.map((c) => {
        const Icon = c.icon;
        return (
          <Link
            key={c.slug}
            href={`/operations/${c.slug}`}
            className="group flex flex-col rounded-2xl border border-border bg-surface p-5 shadow-card transition-all duration-300 ease-out-quint hover:-translate-y-0.5 hover:border-rose/40 hover:shadow-raised"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-rose/12 text-rose transition-colors group-hover:bg-rose/16">
                  <Icon className="h-5 w-5" />
                </span>
                <h3 className="font-display text-lg font-semibold text-ink">{c.title}</h3>
              </div>
              <StatusBadge tone={c.status.tone} dot={false}>{c.status.label}</StatusBadge>
            </div>

            <p className="mt-3 text-sm leading-relaxed text-ink-muted">{c.description}</p>

            <div className="mt-4 grid grid-cols-3 gap-2 border-t border-border pt-4">
              {c.kpis.map((k) => (
                <div key={k.label} className="min-w-0">
                  <div className="font-mono text-xl font-semibold text-ink tnum">{k.value}</div>
                  <p className="mt-0.5 truncate text-xxs uppercase tracking-eyebrow text-ink-faint">{k.label}</p>
                </div>
              ))}
            </div>

            <div className="mt-4 flex items-center justify-end">
              <span className={cn(
                "inline-flex items-center gap-1.5 rounded-lg bg-surface-2 px-3 py-1.5 text-xs font-semibold text-ink transition-colors group-hover:bg-rose group-hover:text-rose-contrast",
              )}>
                Open section <ArrowRight className="h-3.5 w-3.5" />
              </span>
            </div>
          </Link>
        );
      })}
    </div>
  );
}
