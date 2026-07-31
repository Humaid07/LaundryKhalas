"use client";

import { useEffect, useState } from "react";
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
  // The section-landing "Overview" child matches its exact route only, so it isn't
  // highlighted for every subsection route under the same base.
  const active = child.exact
    ? pathname === child.href
    : pathname === child.href || pathname.startsWith(`${child.href}/`);
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
          ? "bg-surface-sunken font-semibold text-ink"
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
  expanded: expandedProp,
  onToggle,
  onNavigate,
}: {
  item: NavItem;
  collapsed: boolean;
  /** Accordion state from the Sidebar — only one section is open at a time. */
  expanded: boolean;
  onToggle: () => void;
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
  const expanded = hasChildren && expandedProp;

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
          filled ? "bg-surface-sunken text-ink" : cn("text-ink-faint", accent.hoverBg, "hover:text-ink"),
        )}
      >
        {active && <span className={cn("absolute left-0 top-1/2 h-6 w-1 -translate-y-1/2 rounded-r-full", accent.rail)} />}
        <Icon className={cn("h-[18px] w-[18px] transition-all duration-200", accent.text, active ? "opacity-100" : "opacity-70 group-hover:opacity-100")} />
      </Link>
    );
  }

  const submenuId = `submenu-${item.href.replace(/\W+/g, "-").replace(/^-|-$/g, "")}`;

  // Shared row grammar (icon · label · badge · chevron) + the active/hover styling,
  // identical whether the row is a toggle button (has children) or a link (no children).
  const rowClasses = cn(
    // Fixed 4-column grid: icon · label · badge (reserved) · chevron (reserved).
    "lk-navrow relative grid h-11 w-full grid-cols-[24px_1fr_auto_18px] items-center gap-2.5 rounded-xl px-3 text-sm font-medium transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-rose/40",
    filled
      ? "bg-surface-sunken font-semibold text-ink"
      : active
        ? cn("text-ink", accent.hoverBg)
        : cn("text-ink-muted", accent.hoverBg, "hover:text-ink"),
  );

  const rowInner = (
    <>
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
          <ChevronDown className={cn("h-4 w-4 transition-transform duration-200 ease-out-quint", active ? accent.text : "text-ink-faint group-hover:text-ink-muted", expanded && "rotate-180")} />
        )}
      </span>
    </>
  );

  return (
    <div className="group relative">
      {hasChildren ? (
        // Section with subsections → the WHOLE row is the disclosure toggle.
        // (Enter/Space work natively; the landing page stays reachable via the
        // "Overview" child.)
        <button
          type="button"
          onClick={onToggle}
          title={item.label}
          aria-expanded={expanded}
          aria-controls={submenuId}
          className={cn(rowClasses, "text-left")}
        >
          {rowInner}
        </button>
      ) : (
        // Leaf section (no subsections) → the row navigates.
        <Link
          href={item.href}
          onClick={onNavigate}
          aria-current={exact ? "page" : undefined}
          title={item.label}
          className={rowClasses}
        >
          {rowInner}
        </Link>
      )}

      {expanded && (
        <div id={submenuId} className="mb-1 mt-1 ml-[19px] space-y-0.5 border-l border-border pl-2.5">
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
  const pathname = usePathname();
  // Show only the sections this role may open — same rule as the route guard so
  // the sidebar and guard can never drift apart.
  const items = role ? NAV_ITEMS.filter((item) => isRouteAllowed(role, item.href)) : NAV_ITEMS;

  // Accordion: exactly ONE section open at a time. Defaults to the section that
  // contains the current route; opening another collapses the previous one.
  const activeHref = items.find((i) => inSection(pathname, i.href))?.href ?? null;
  const [openHref, setOpenHref] = useState<string | null>(activeHref);
  // Navigating into a section opens it (and collapses the others). A manual
  // collapse within the same route persists because activeHref hasn't changed.
  useEffect(() => {
    if (activeHref) setOpenHref(activeHref);
  }, [activeHref]);
  const handleToggle = (href: string) => setOpenHref((cur) => (cur === href ? null : href));

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
          <ParentRow
            key={item.href}
            item={item}
            collapsed={collapsed}
            expanded={openHref === item.href}
            onToggle={() => handleToggle(item.href)}
            onNavigate={onNavigate}
          />
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
