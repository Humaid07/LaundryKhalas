"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AlertCircle, LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";
import { roleLabel } from "@/lib/roles";
import { accentClasses, accentForHref } from "@/lib/accents";
import { NAV_ITEMS, isActive, type NavItem } from "./nav-items";
import { NavLabel } from "./NavLabel";
import { useUnreadCount } from "@/lib/use-notifications";
import { BrandWordmark } from "@/components/shell/Brand";

const ISSUES_ITEM: NavItem = { href: "/issues", label: "Issues", icon: AlertCircle, match: ["/issues"] };

/** One sidebar row — fixed grid (icon · label · badge), per-section accent. */
function SidebarLink({ item, badge }: { item: NavItem; badge?: number }) {
  const pathname = usePathname();
  const on = isActive(pathname, item);
  const accent = accentClasses(accentForHref(item.href));
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      aria-current={on ? "page" : undefined}
      title={item.label}
      className={cn(
        "lk-navrow group relative grid h-11 grid-cols-[24px_1fr_auto] items-center gap-2.5 rounded-xl px-3 text-sm font-medium transition-colors duration-200",
        on ? cn(accent.softBg, accent.text) : cn("text-ink-muted", accent.hoverBg, "hover:text-ink"),
      )}
    >
      {on && <span className={cn("absolute left-0 top-1/2 h-6 w-1 -translate-y-1/2 rounded-r-full", accent.rail)} />}
      <Icon className={cn("h-[18px] w-[18px] justify-self-center transition-all duration-200", accent.text, on ? "opacity-100" : "opacity-60 group-hover:opacity-100")} />
      <NavLabel label={item.label} />
      <span className="flex justify-end">
        {typeof badge === "number" && badge > 0 && (
          <span className={cn("grid h-5 min-w-5 place-items-center rounded-full px-1.5 text-xxs font-bold tnum", on ? cn(accent.strongBg, accent.text) : "bg-rose text-rose-contrast")}>
            {badge > 9 ? "9+" : badge}
          </span>
        )}
      </span>
    </Link>
  );
}

/**
 * FacilityDesktopShell — quiet left sidebar for md+ screens (mobile uses the
 * bottom nav). Every row is a fixed grid with a persistent per-section accent.
 */
export function FacilityDesktopShell() {
  const { user, logout } = useAuth();
  const unread = useUnreadCount();
  const settingsItem = NAV_ITEMS.find((item) => item.href === "/settings");

  return (
    <aside className="hidden w-60 shrink-0 flex-col overflow-x-hidden border-r border-border bg-surface md:flex">
      <div className="px-5 py-5">
        <BrandWordmark />
      </div>

      <nav className="flex-1 overflow-x-hidden px-3">
        <ul className="space-y-1">
          {NAV_ITEMS.filter((item) => item.href !== "/settings").map((item) => (
            <li key={item.href}>
              <SidebarLink item={item} badge={item.href === "/orders" ? unread : undefined} />
            </li>
          ))}
        </ul>

        <div className="mt-2 space-y-1 border-t border-border/60 pt-2">
          <SidebarLink item={ISSUES_ITEM} />
          {settingsItem && <SidebarLink item={settingsItem} />}
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
