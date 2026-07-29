import { Home, ClipboardList, Truck, Wallet, Settings, Building2, type LucideIcon } from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Route prefixes that should highlight this item as active. */
  match: string[];
};

/** The four primary destinations, shared by the mobile bottom nav and the
 *  desktop sidebar so they can never disagree. */
export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Home", icon: Home, match: ["/"] },
  { href: "/facilities", label: "Facilities", icon: Building2, match: ["/facilities"] },
  { href: "/orders", label: "Orders", icon: ClipboardList, match: ["/orders"] },
  { href: "/drivers", label: "Drivers", icon: Truck, match: ["/drivers"] },
  { href: "/finance", label: "Finance", icon: Wallet, match: ["/finance"] },
  { href: "/settings", label: "Settings", icon: Settings, match: ["/settings"] },
];

export function isActive(pathname: string, item: NavItem): boolean {
  if (item.href === "/") return pathname === "/";
  return item.match.some((m) => pathname === m || pathname.startsWith(`${m}/`));
}
