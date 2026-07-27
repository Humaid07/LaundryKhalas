"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AlertCircle, LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";
import { roleLabel } from "@/lib/roles";
import { NAV_ITEMS, isActive } from "./nav-items";
import { useUnreadCount } from "@/lib/use-notifications";
import { BrandWordmark } from "@/components/shell/Brand";

/**
 * FacilityDesktopShell — a simple, quiet left sidebar for md+ screens. Mobile
 * uses the bottom nav instead (this sidebar is hidden under md).
 */
export function FacilityDesktopShell() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const unread = useUnreadCount();
  const settingsItem = NAV_ITEMS.find((item) => item.href === "/settings");

  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-border bg-surface md:flex">
      <div className="px-5 py-5">
        <BrandWordmark />
      </div>

      <nav className="flex-1 px-3">
        <ul className="space-y-1">
          {/* Primary destinations (Settings is pulled out below so it sits
              after the Issues link). */}
          {NAV_ITEMS.filter((item) => item.href !== "/settings").map((item) => {
            const on = isActive(pathname, item);
            const showBadge = item.href === "/orders" && unread > 0;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={on ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                    on
                      ? "bg-rose/10 text-rose"
                      : "text-ink-muted hover:bg-surface-2 hover:text-ink",
                  )}
                >
                  <item.icon className={cn("h-[1.15rem] w-[1.15rem]", on && "stroke-[2.2]")} />
                  <span className="flex-1">{item.label}</span>
                  {showBadge && (
                    <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-rose px-1.5 text-xxs font-bold text-rose-contrast">
                      {unread > 9 ? "9+" : unread}
                    </span>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>

        <div className="mt-2 space-y-1 border-t border-border/60 pt-2">
          <Link
            href="/issues"
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
              isActive(pathname, { href: "/issues", label: "Issues", icon: AlertCircle, match: ["/issues"] })
                ? "bg-rose/10 text-rose"
                : "text-ink-muted hover:bg-surface-2 hover:text-ink",
            )}
          >
            <AlertCircle className="h-[1.15rem] w-[1.15rem]" />
            <span className="flex-1">Issues</span>
          </Link>
          {settingsItem && (
            <Link
              href={settingsItem.href}
              aria-current={isActive(pathname, settingsItem) ? "page" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                isActive(pathname, settingsItem)
                  ? "bg-rose/10 text-rose"
                  : "text-ink-muted hover:bg-surface-2 hover:text-ink",
              )}
            >
              <settingsItem.icon className="h-[1.15rem] w-[1.15rem]" />
              <span className="flex-1">{settingsItem.label}</span>
            </Link>
          )}
        </div>
      </nav>

      <div className="border-t border-border px-3 py-3">
        <div className="flex items-center gap-3 rounded-lg px-3 py-2">
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-ink">{user?.full_name ?? "Partner"}</p>
            <p className="truncate text-xxs text-ink-faint">{roleLabel(user?.role)}</p>
          </div>
          <button
            type="button"
            onClick={logout}
            aria-label="Sign out"
            className="flex h-8 w-8 items-center justify-center rounded-lg text-ink-muted transition-colors hover:bg-surface-2 hover:text-ink"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
