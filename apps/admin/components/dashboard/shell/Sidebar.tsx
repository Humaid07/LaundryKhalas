"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronDown, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { cn } from "@/lib/utils";
import { NAV_ITEMS, type NavChild, type NavItem } from "@/lib/dashboard/nav";
import { useAuth } from "@/lib/dashboard/auth-context";
import { isRouteAllowed } from "@/lib/dashboard/auth";
import { accentClasses, accentForHref } from "@/lib/dashboard/accents";
import { BrandWordmark } from "./Brand";
import { NavLabel } from "./NavLabel";

/** Is the current route inside this section (exact landing or any child route)? */
function inSection(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

/* -------------------------------- Child row -------------------------------- */

function ChildRow({ child, onNavigate }: { child: NavChild; onNavigate?: () => void }) {
  const pathname = usePathname();
  const active = pathname === child.href || pathname.startsWith(`${child.href}/`);
  const accent = accentClasses(accentForHref(child.href));
  return (
    <Link
      href={child.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      title={child.label}
      className={cn(
        "lk-navrow group/child relative grid h-9 grid-cols-[16px_1fr_auto] items-center gap-2.5 rounded-lg pl-3 pr-2 text-[13px] transition-colors duration-200",
        active
          ? cn(accent.softBg, "font-semibold", accent.text)
          : cn("font-medium text-ink-muted", accent.hoverBg, "hover:text-ink"),
      )}
    >
      {active && <span className={cn("absolute -left-[9px] top-1/2 h-4 w-1 -translate-y-1/2 rounded-r-full", accent.rail)} />}
      <span className={cn("h-1.5 w-1.5 justify-self-center rounded-full transition-colors", active ? accent.dot : "bg-ink-faint/50 group-hover/child:bg-ink-faint")} />
      <NavLabel label={child.label} />
      <span className="flex justify-end">
        {typeof child.badge === "number" && (
          <span className={cn("grid h-[18px] min-w-[20px] place-items-center rounded-full px-1 text-xxs font-semibold tnum", active ? cn(accent.strongBg, accent.text) : "bg-ink/8 text-ink-muted")}>
            {child.badge}
          </span>
        )}
      </span>
    </Link>
  );
}

/* ------------------------------- Parent row -------------------------------- */

function ParentRow({
  item,
  collapsed,
  onNavigate,
}: {
  item: NavItem;
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const Icon = item.icon;
  const accent = accentClasses(accentForHref(item.href));
  const hasChildren = !collapsed && !!item.children?.length;

  const active = inSection(pathname, item.href);
  const exact = pathname === item.href;
  // Filled (accent background) on the section's own landing route; when a child
  // route is active the parent keeps accent text but the child gets the fill.
  const filled = exact;

  const [open, setOpen] = useState<boolean | null>(null);
  const expanded = hasChildren && (open ?? (active || !!item.defaultOpen));

  /* Collapsed rail: icon-only, centered, tooltip via title. */
  if (collapsed) {
    return (
      <Link
        href={item.href}
        onClick={onNavigate}
        title={item.label}
        aria-current={exact ? "page" : undefined}
        className={cn(
          "group relative grid h-11 place-items-center rounded-xl transition-colors duration-200",
          filled ? cn(accent.softBg, accent.text) : cn("text-ink-faint", accent.hoverBg, "hover:text-ink"),
        )}
      >
        {active && <span className={cn("absolute left-0 top-1/2 h-6 w-1 -translate-y-1/2 rounded-r-full", accent.rail)} />}
        <Icon className={cn("h-[18px] w-[18px] transition-all duration-200", accent.text, active ? "opacity-100" : "opacity-70 group-hover:opacity-100")} />
      </Link>
    );
  }

  return (
    <div className="group relative">
      <Link
        href={item.href}
        onClick={onNavigate}
        aria-current={exact ? "page" : undefined}
        title={item.label}
        className={cn(
          // Fixed 4-column grid: icon · label · badge (reserved) · chevron (reserved).
          "lk-navrow relative grid h-11 grid-cols-[24px_1fr_auto_18px] items-center gap-2.5 rounded-xl px-3 text-sm font-medium transition-colors duration-200",
          filled
            ? cn(accent.softBg, accent.text)
            : active
              ? cn(accent.text, accent.hoverBg)
              : cn("text-ink-muted", accent.hoverBg, "hover:text-ink"),
        )}
      >
        {/* left active indicator */}
        {active && <span className={cn("absolute left-0 top-1/2 h-6 w-1 -translate-y-1/2 rounded-r-full", accent.rail)} />}

        {/* 1 · icon — persistent subtle section tint, brightens on hover/active */}
        <Icon className={cn("h-[18px] w-[18px] justify-self-center transition-all duration-200", accent.text, active ? "opacity-100" : "opacity-60 group-hover:opacity-100")} />

        {/* 2 · label */}
        <NavLabel label={item.label} />

        {/* 3 · badge (column always present; empty when no count) */}
        <span className="flex min-w-0 justify-end">
          {typeof item.badge === "number" && (
            <span className={cn("grid h-[22px] min-w-[24px] place-items-center rounded-full px-1.5 text-xxs font-semibold tnum", active ? cn(accent.strongBg, accent.text) : "bg-ink/8 text-ink-muted")}>
              {item.badge}
            </span>
          )}
        </span>

        {/* 4 · chevron (column always reserved; icon only when the section has children) */}
        <span className="flex w-[18px] items-center justify-center">
          {!!item.children?.length && (
            <ChevronDown className={cn("h-4 w-4 transition-transform duration-200 ease-out-quint", active ? accent.text : "text-ink-faint", expanded && "rotate-180")} />
          )}
        </span>
      </Link>

      {/* Transparent hit target over the chevron column — toggles the submenu
          without navigating. Sits on top of the Link's right edge. */}
      {hasChildren && (
        <button
          type="button"
          onClick={() => setOpen((o) => !(o ?? (active || !!item.defaultOpen)))}
          aria-label={expanded ? `Collapse ${item.label}` : `Expand ${item.label}`}
          aria-expanded={expanded}
          className="absolute inset-y-0 right-0 w-9 rounded-r-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40"
        />
      )}

      {expanded && (
        <div className="mb-1 mt-1 ml-[19px] space-y-0.5 border-l border-border pl-2.5">
          {item.children!.map((child) => (
            <ChildRow key={child.href} child={child} onNavigate={onNavigate} />
          ))}
        </div>
      )}
    </div>
  );
}

/* --------------------------------- Sidebar --------------------------------- */

export function Sidebar({
  collapsed,
  onToggleCollapse,
  onNavigate,
}: {
  collapsed: boolean;
  onToggleCollapse?: () => void;
  onNavigate?: () => void;
}) {
  const { role } = useAuth();
  // Show only the sections this role may open — same rule as the route guard so
  // the sidebar and guard can never drift apart.
  const items = role ? NAV_ITEMS.filter((item) => isRouteAllowed(role, item.href)) : NAV_ITEMS;

  return (
    <div className="flex h-full flex-col overflow-x-hidden bg-surface">
      {/* Brand */}
      <div className={cn("flex h-16 items-center border-b border-border px-4", collapsed && "justify-center px-0")}>
        <BrandWordmark collapsed={collapsed} />
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-1 overflow-y-auto overflow-x-hidden px-3 py-4">
        {!collapsed && (
          <p className="px-2 pb-2 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Command Center</p>
        )}
        {items.map((item) => (
          <ParentRow key={item.href} item={item} collapsed={collapsed} onNavigate={onNavigate} />
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-border p-3">
        {onToggleCollapse && (
          <button
            type="button"
            onClick={onToggleCollapse}
            className={cn(
              "hidden w-full items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium text-ink-muted transition-colors hover:bg-surface-2 hover:text-ink lg:flex",
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
