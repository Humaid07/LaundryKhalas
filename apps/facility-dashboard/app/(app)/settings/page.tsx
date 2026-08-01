"use client";

import Link from "next/link";
import {
  Tag,
  SlidersHorizontal,
  Users,
  Clock,
  Bell,
  Building2,
  ChevronRight,
  type LucideIcon,
} from "lucide-react";
import { MobilePageHeader } from "@/components/shared/MobilePageHeader";

const ITEMS: { href: string; label: string; description: string; icon: LucideIcon }[] = [
  { href: "/settings/profile", label: "Facility Profile", description: "Name, area and city.", icon: Building2 },
  { href: "/settings/operations", label: "Operations", description: "Accepting orders, capacity and handoff.", icon: SlidersHorizontal },
  { href: "/settings/timings", label: "Timings", description: "Weekly hours and blackout dates.", icon: Clock },
  { href: "/settings/price", label: "Price List", description: "View catalogue rates and request changes.", icon: Tag },
  { href: "/settings/teams", label: "Team", description: "Members, drivers and runners.", icon: Users },
  { href: "/settings/notifications", label: "Notifications", description: "Mobile contacts and alert types.", icon: Bell },
];

export default function SettingsPage() {
  return (
    <div className="lk-enter space-y-5">
      <MobilePageHeader title="Settings" description="Manage how your facility runs." />

      <div className="grid gap-3 sm:grid-cols-2">
        {ITEMS.map((it) => (
          <Link
            key={it.href}
            href={it.href}
            className="group flex items-center gap-4 rounded-2xl border border-border/70 bg-surface p-4 shadow-card transition-all duration-200 ease-out-quint hover:-translate-y-0.5 hover:border-border-strong hover:shadow-raised"
          >
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-rose/10 text-rose">
              <it.icon className="h-5 w-5" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-ink">{it.label}</p>
              <p className="truncate text-xs text-ink-muted">{it.description}</p>
            </div>
            <ChevronRight className="h-4 w-4 shrink-0 text-ink-faint transition-colors group-hover:text-rose" />
          </Link>
        ))}
      </div>
    </div>
  );
}
