"use client";

import Link from "next/link";
import {
  Headset, Factory, Truck, ClipboardList, ArrowRight,
  AlertTriangle, Clock, PackageCheck, type LucideIcon,
} from "lucide-react";
import { Panel, PanelHeader, StatusBadge } from "@/components/dashboard/ui/primitives";
import type { Tone } from "@/lib/dashboard/types";
import { cn } from "@/lib/utils";

/* A clean executive overview for the Operations command center. Navigation to
 * the working pages lives in the LEFT SIDEBAR (Operations ▸ Customer Facing,
 * Facility Facing, Drivers, Customer Orders) — this page is a summary, not the
 * primary navigation, so it shows KPIs, urgent alerts and recent activity with
 * only lightweight quick links. */

type Kpi = { label: string; value: string; tone?: Tone; hint?: string };
const KPIS: Kpi[] = [
  { label: "Active orders", value: "82", tone: "rose", hint: "across all channels" },
  { label: "Open conversations", value: "24", hint: "8 pending reply" },
  { label: "In cleaning", value: "18", hint: "6 awaiting QC" },
  { label: "Active drivers", value: "12", tone: "success", hint: "9 pickups assigned" },
  { label: "Completed today", value: "31", tone: "success" },
  { label: "Urgent issues", value: "8", tone: "danger", hint: "needs attention" },
];

type Alert = { label: string; detail: string; tone: Tone; href: string; icon: LucideIcon };
const ALERTS: Alert[] = [
  { label: "3 orders delayed at facility", detail: "Beyond promised turnaround — review handoffs.", tone: "danger", href: "/operations/facility-facing", icon: AlertTriangle },
  { label: "5 urgent support tickets", detail: "Flagged by the WhatsApp agent for takeover.", tone: "danger", href: "/operations/customer-facing", icon: Headset },
  { label: "4 deliveries running late", detail: "Route status behind schedule.", tone: "warning", href: "/operations/drivers", icon: Clock },
  { label: "7 order changes pending", detail: "Customer-requested changes awaiting confirmation.", tone: "warning", href: "/operations/customer-orders", icon: ClipboardList },
];

type Activity = { text: string; time: string };
const ACTIVITY: Activity[] = [
  { text: "Order LC-TEST-1007 confirmed — Boutique Clean & Press, Dubai Marina.", time: "2m ago" },
  { text: "Facility 'Sparkle Dubai' marked 4 orders ready for delivery.", time: "11m ago" },
  { text: "Driver Imran completed 3 pickups in JLT.", time: "26m ago" },
  { text: "Support takeover resolved for +9715•• ticket #TK-2041.", time: "41m ago" },
  { text: "Order LC-TEST-1004 moved to In Cleaning.", time: "1h ago" },
];

const QUICK_LINKS: { slug: string; label: string; icon: LucideIcon; badge: number }[] = [
  { slug: "customer-facing", label: "Customer Facing", icon: Headset, badge: 7 },
  { slug: "facility-facing", label: "Facility Facing", icon: Factory, badge: 3 },
  { slug: "drivers", label: "Drivers", icon: Truck, badge: 12 },
  { slug: "customer-orders", label: "Customer Orders", icon: ClipboardList, badge: 82 },
];

const toneText: Record<Tone, string> = {
  rose: "text-rose", success: "text-emerald-600 dark:text-emerald-400",
  warning: "text-amber-600 dark:text-amber-400", danger: "text-red-600 dark:text-red-400",
  info: "text-sky-600 dark:text-sky-400", plum: "text-purple-600 dark:text-purple-400",
  neutral: "text-ink",
};

export function OperationsOverview() {
  return (
    <div className="space-y-5">
      {/* KPI row */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        {KPIS.map((k) => (
          <Panel key={k.label} className="p-4">
            <div className={cn("font-mono text-2xl font-semibold tnum", k.tone ? toneText[k.tone] : "text-ink")}>{k.value}</div>
            <p className="mt-1 text-xs font-medium text-ink">{k.label}</p>
            {k.hint && <p className="mt-0.5 truncate text-xxs text-ink-faint">{k.hint}</p>}
          </Panel>
        ))}
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        {/* Urgent alerts */}
        <Panel className="lg:col-span-2">
          <PanelHeader
            title="Urgent alerts"
            subtitle="Issues that need an operator today"
            action={<StatusBadge tone="danger" dot>{ALERTS.filter((a) => a.tone === "danger").length} critical</StatusBadge>}
          />
          <ul className="space-y-2">
            {ALERTS.map((a) => {
              const Icon = a.icon;
              return (
                <li key={a.label}>
                  <Link
                    href={a.href}
                    className="group flex items-center gap-3 rounded-xl border border-border bg-surface-2/40 px-3.5 py-3 transition-colors hover:border-rose/40 hover:bg-surface-2"
                  >
                    <span className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-surface", toneText[a.tone])}>
                      <Icon className="h-4 w-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-ink">{a.label}</p>
                      <p className="truncate text-xs text-ink-muted">{a.detail}</p>
                    </div>
                    <ArrowRight className="h-4 w-4 shrink-0 text-ink-faint transition-transform group-hover:translate-x-0.5 group-hover:text-rose" />
                  </Link>
                </li>
              );
            })}
          </ul>
        </Panel>

        {/* Recent activity */}
        <Panel>
          <PanelHeader title="Recent activity" subtitle="Latest operational events" />
          <ul className="space-y-3.5">
            {ACTIVITY.map((ev, i) => (
              <li key={i} className="flex gap-3">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-rose/60" />
                <div className="min-w-0">
                  <p className="text-[13px] leading-snug text-ink">{ev.text}</p>
                  <p className="mt-0.5 text-xxs text-ink-faint">{ev.time}</p>
                </div>
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      {/* Lightweight quick links (secondary — primary nav is the sidebar) */}
      <Panel padded={false} className="p-4">
        <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-eyebrow text-ink-faint">
          <PackageCheck className="h-3.5 w-3.5" /> Jump to a workspace
        </div>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          {QUICK_LINKS.map((l) => {
            const Icon = l.icon;
            return (
              <Link
                key={l.slug}
                href={`/operations/${l.slug}`}
                className="group flex items-center gap-2.5 rounded-xl border border-border px-3 py-2.5 text-sm font-medium text-ink-muted transition-colors hover:border-rose/40 hover:text-ink"
              >
                <Icon className="h-4 w-4 shrink-0 text-ink-faint group-hover:text-rose" />
                <span className="flex-1 truncate">{l.label}</span>
                <span className="rounded-full bg-ink/8 px-1.5 py-0.5 text-xxs font-semibold tnum text-ink-muted">{l.badge}</span>
              </Link>
            );
          })}
        </div>
      </Panel>
    </div>
  );
}
