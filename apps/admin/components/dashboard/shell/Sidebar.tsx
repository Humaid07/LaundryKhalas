"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronDown, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { cn } from "@/lib/utils";
import { NAV_ITEMS, type NavChild, type NavItem } from "@/lib/dashboard/nav";
import { BrandWordmark } from "./Brand";

/** Is the current route inside this section (exact landing or any child route)? */
function inSection(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function Badge({ value, active }: { value: number; active: boolean }) {
  return (
    <span
      className={cn(
        "ml-auto shrink-0 rounded-full px-1.5 py-0.5 text-xxs font-semibold tnum",
        active ? "bg-rose/15 text-rose" : "bg-ink/8 text-ink-muted",
      )}
    >
      {value}
    </span>
  );
}

function ChildRow({ child, onNavigate }: { child: NavChild; onNavigate?: () => void }) {
  const pathname = usePathname();
  const active = pathname === child.href || pathname.startsWith(`${child.href}/`);
  return (
    <Link
      href={child.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group relative flex items-center gap-2.5 rounded-lg py-2 pl-3 pr-2 text-[13px] transition-colors duration-200",
        active ? "bg-rose/10 font-semibold text-rose" : "font-medium text-ink-muted hover:bg-surface-2 hover:text-ink",
      )}
    >
      {/* rose rail for the active child */}
      {active && <span className="absolute -left-[9px] top-1/2 h-4 w-1 -translate-y-1/2 rounded-r-full bg-rose" />}
      <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full transition-colors", active ? "bg-rose" : "bg-ink-faint/50 group-hover:bg-ink-faint")} />
      <span className="flex-1 truncate">{child.label}</span>
      {typeof child.badge === "number" && <Badge value={child.badge} active={active} />}
    </Link>
  );
}

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
  const hasChildren = !collapsed && !!item.children?.length;

  const active = inSection(pathname, item.href);
  const exact = pathname === item.href;
  // The parent is "selected" (filled) only on its own landing route; when a
  // child route is active the parent stays highlighted (rose text) but the
  // child gets the filled treatment so the current page reads clearly.
  const filled = exact;

  // Expanded when the user opened it OR the current route is inside this
  // section OR the section is flagged defaultOpen. User toggle wins once set.
  const [open, setOpen] = useState<boolean | null>(null);
  const expanded = hasChildren && (open ?? (active || !!item.defaultOpen));

  return (
    <div>
      <div className="flex items-center gap-1">
        <Link
          href={item.href}
          onClick={onNavigate}
          title={collapsed ? item.label : undefined}
          className={cn(
            "group relative flex flex-1 items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200",
            collapsed && "justify-center px-0",
            filled
              ? "bg-rose/10 text-rose"
              : active
                ? "text-rose hover:bg-surface-2"
                : "text-ink-muted hover:bg-surface-2 hover:text-ink",
          )}
        >
          {filled && <span className="absolute left-0 top-1/2 h-6 w-1 -translate-y-1/2 rounded-r-full bg-rose" />}
          <Icon className={cn("h-[18px] w-[18px] shrink-0", active ? "text-rose" : "text-ink-faint group-hover:text-ink")} />
          {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
          {!collapsed && typeof item.badge === "number" && <Badge value={item.badge} active={active} />}
        </Link>

        {hasChildren && (
          <button
            type="button"
            onClick={() => setOpen((o) => !(o ?? (active || !!item.defaultOpen)))}
            aria-label={expanded ? `Collapse ${item.label}` : `Expand ${item.label}`}
            aria-expanded={expanded}
            className="flex h-9 w-7 shrink-0 items-center justify-center rounded-lg text-ink-faint transition-colors hover:bg-surface-2 hover:text-ink"
          >
            <ChevronDown className={cn("h-4 w-4 transition-transform duration-200", expanded && "rotate-180")} />
          </button>
        )}
      </div>

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

export function Sidebar({
  collapsed,
  onToggleCollapse,
  onNavigate,
}: {
  collapsed: boolean;
  onToggleCollapse?: () => void;
  onNavigate?: () => void;
}) {
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
        {NAV_ITEMS.map((item) => (
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
