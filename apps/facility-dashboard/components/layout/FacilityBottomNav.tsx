"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { MoreHorizontal } from "lucide-react";
import { cn } from "@/lib/utils";
import { NAV_ITEMS, isActive, type NavItem } from "./nav-items";
import { useUnreadCount } from "@/lib/use-notifications";

/**
 * Mobile bottom nav shows five destinations: the four primary sections plus a
 * "More" entry that opens Settings (Settings/Issues live under More on mobile).
 */
const MORE_ITEM: NavItem = {
  href: "/settings",
  label: "More",
  icon: MoreHorizontal,
  match: ["/settings", "/issues"],
};

const BOTTOM_ITEMS: NavItem[] = [
  ...NAV_ITEMS.filter((item) => item.href !== "/settings"),
  MORE_ITEM,
];

/**
 * FacilityBottomNav — the primary mobile navigation. Fixed to the bottom with
 * large tap targets (min 64px tall incl. safe-area). Hidden on md+ where the
 * desktop sidebar takes over.
 */
export function FacilityBottomNav() {
  const pathname = usePathname();
  const unread = useUnreadCount();

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-surface/95 backdrop-blur md:hidden"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      <ul className="mx-auto grid max-w-lg grid-cols-5">
        {BOTTOM_ITEMS.map((item) => {
          const on = isActive(pathname, item);
          const showBadge = item.href === "/orders" && unread > 0;
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={on ? "page" : undefined}
                className={cn(
                  "relative flex min-h-[56px] flex-col items-center justify-center gap-1 py-2 text-xxs font-semibold transition-colors",
                  on ? "text-rose" : "text-ink-faint hover:text-ink",
                )}
              >
                <span className="relative">
                  <item.icon className={cn("h-6 w-6", on && "stroke-[2.2]")} />
                  {showBadge && (
                    <span className="absolute -right-2 -top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose px-1 text-[9px] font-bold text-rose-contrast">
                      {unread > 9 ? "9+" : unread}
                    </span>
                  )}
                </span>
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
