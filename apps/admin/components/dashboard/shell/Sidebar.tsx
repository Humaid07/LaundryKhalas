"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { cn } from "@/lib/utils";
import { NAV_ITEMS } from "@/lib/dashboard/nav";
import { BrandWordmark } from "./Brand";

export function Sidebar({
  collapsed,
  onToggleCollapse,
  onNavigate,
}: {
  collapsed: boolean;
  onToggleCollapse?: () => void;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();

  return (
    <div className="flex h-full flex-col bg-surface">
      {/* Brand */}
      <div className={cn("flex h-16 items-center border-b border-border px-4", collapsed && "justify-center px-0")}>
        <BrandWordmark collapsed={collapsed} />
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {!collapsed && (
          <p className="px-2 pb-2 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Command Center</p>
        )}
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              title={collapsed ? item.label : undefined}
              className={cn(
                "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200",
                collapsed && "justify-center px-0",
                active ? "bg-rose/10 text-rose" : "text-ink-muted hover:bg-surface-2 hover:text-ink",
              )}
            >
              {/* rose active rail */}
              {active && (
                <span className="absolute left-0 top-1/2 h-6 w-1 -translate-y-1/2 rounded-r-full bg-rose" />
              )}
              <Icon className={cn("h-[18px] w-[18px] shrink-0", active ? "text-rose" : "text-ink-faint group-hover:text-ink")} />
              {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
              {!collapsed && typeof item.badge === "number" && (
                <span
                  className={cn(
                    "rounded-full px-1.5 py-0.5 text-xxs font-semibold tnum",
                    active ? "bg-rose/15 text-rose" : "bg-ink/8 text-ink-muted",
                  )}
                >
                  {item.badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-border p-3">
        {onToggleCollapse && (
          <button
            type="button"
            onClick={onToggleCollapse}
            className={cn(
              "mt-2 hidden w-full items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium text-ink-muted transition-colors hover:bg-surface-2 hover:text-ink lg:flex",
              collapsed && "justify-center px-0",
            )}
          >
            {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
            {!collapsed && "Collapse"}
          </button>
        )}
      </div>
    </div>
  );
}
