"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const TABS = [
  { href: "/finance", label: "Summary" },
  { href: "/finance/revenue", label: "Revenue" },
  { href: "/finance/services", label: "Services" },
  { href: "/finance/payouts", label: "Payouts" },
];

/** Horizontal, scrollable sub-navigation for the Finance section. */
export function FinanceNav() {
  const pathname = usePathname();
  return (
    <div className="overflow-x-auto">
      <div className="inline-flex min-w-max gap-1 rounded-xl border border-border bg-surface-2 p-1">
        {TABS.map((t) => {
          const on = pathname === t.href;
          return (
            <Link
              key={t.href}
              href={t.href}
              className={cn(
                "whitespace-nowrap rounded-lg px-3.5 py-2 text-sm font-semibold transition-all duration-200",
                on ? "bg-surface text-rose shadow-card" : "text-ink-muted hover:text-ink",
              )}
            >
              {t.label}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
