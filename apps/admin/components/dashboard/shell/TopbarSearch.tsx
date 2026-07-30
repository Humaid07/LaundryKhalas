"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { CornerDownLeft, Search } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { NAV_ITEMS } from "@/lib/dashboard/nav";
import { SECTIONS } from "@/lib/dashboard/sections";
import { accentClasses, accentForHref, type AccentClasses } from "@/lib/dashboard/accents";

type Command = {
  label: string;
  /** Parent section name for subsection commands. */
  group?: string;
  href: string;
  icon: LucideIcon;
  accent: AccentClasses;
  keywords: string;
};

/** Flat, searchable list of every destination: sections + their subsections. */
const COMMANDS: Command[] = (() => {
  const out: Command[] = [];
  for (const item of NAV_ITEMS) {
    const accent = accentClasses(accentForHref(item.href));
    out.push({
      label: item.label,
      href: item.href,
      icon: item.icon,
      accent,
      keywords: `${item.label} ${item.description}`.toLowerCase(),
    });
    const section = Object.values(SECTIONS).find((s) => s.base === item.href);
    if (section) {
      for (const sub of section.subsections) {
        out.push({
          label: sub.label,
          group: section.title,
          href: `${section.base}/${sub.slug}`,
          icon: sub.icon,
          accent,
          keywords: `${section.title} ${sub.label} ${sub.description}`.toLowerCase(),
        });
      }
    }
  }
  return out;
})();

/**
 * Topbar search — a lightweight, inline suggestions dropdown for fast keyboard
 * navigation to any section or subsection. Deliberately NOT a modal: opening the
 * suggestions must never darken, blur, or overlay the dashboard behind it. The
 * results panel is anchored directly under the search input (a `fixed` sheet on
 * mobile where there is no inline bar) and closes on Esc, outside-click, or after
 * navigating. Arrow keys move, Enter navigates.
 *
 * Filtering is synchronous in-memory (no network), so there is no loading state.
 */
export function TopbarSearch({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const desktopInputRef = useRef<HTMLInputElement>(null);
  const mobileInputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return COMMANDS.slice(0, 60);
    return COMMANDS.filter((c) => c.keywords.includes(q)).slice(0, 60);
  }, [query]);

  // Clear the query on CLOSE (not open) so the next open starts fresh without
  // racing the user's first keystroke, then focus the visible input on open.
  useEffect(() => {
    if (!open) {
      setQuery("");
      return;
    }
    setActive(0);
    const id = requestAnimationFrame(() => {
      const isMobile = typeof window !== "undefined" && window.innerWidth < 640;
      (isMobile ? mobileInputRef.current : desktopInputRef.current)?.focus();
    });
    return () => cancelAnimationFrame(id);
  }, [open]);

  useEffect(() => setActive(0), [query]);

  // Close on outside click — no backdrop element, so we listen on the document.
  // Elements marked data-search-trigger (the mobile search icon) are ignored so
  // tapping the trigger toggles cleanly instead of close-then-reopen flicker.
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      const target = e.target as HTMLElement | null;
      if (!target) return;
      if (containerRef.current?.contains(target)) return;
      if (target.closest("[data-search-trigger]")) return;
      onOpenChange(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open, onOpenChange]);

  // Keep the highlighted row in view.
  useEffect(() => {
    if (!open || !listRef.current) return;
    const el = listRef.current.querySelector(`[data-idx="${active}"]`) as HTMLElement | null;
    el?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  // Close once navigation commits — closing in the SAME tick as router.push()
  // intermittently aborts the client-side navigation, so we let the route change
  // drive the close instead.
  useEffect(() => {
    onOpenChange(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  const go = (href: string) => {
    if (href === pathname) {
      onOpenChange(false); // already here — push is a no-op, so close directly
      return;
    }
    router.push(href); // the pathname effect above closes the dropdown on arrival
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      onOpenChange(false);
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const r = results[active];
      if (r) go(r.href);
    }
  };

  const inputClasses =
    "h-9 w-full rounded-lg border border-border bg-surface pl-9 pr-16 text-sm text-ink placeholder:text-ink-faint transition-colors hover:border-border-strong focus:border-border-strong focus:outline-none";

  return (
    <div ref={containerRef} className="relative sm:flex-1 sm:max-w-md">
      {/* Desktop inline search bar */}
      <div className="relative hidden items-center sm:flex">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
        <input
          ref={desktopInputRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            if (!open) onOpenChange(true);
          }}
          onFocus={() => onOpenChange(true)}
          onKeyDown={onKeyDown}
          placeholder="Search orders, customers, conversations…"
          aria-label="Search and jump to a section"
          aria-expanded={open}
          aria-controls="topbar-search-results"
          role="combobox"
          className={inputClasses}
        />
        <kbd className="pointer-events-none absolute right-2 top-1/2 hidden -translate-y-1/2 rounded border border-border bg-surface-2 px-1.5 py-0.5 text-xxs font-medium text-ink-faint md:block">
          ⌘K
        </kbd>
      </div>

      {open && (
        <div
          id="topbar-search-results"
          className={cn(
            // Solid, fully opaque surface — no gradient, no backdrop-blur, so the
            // dashboard behind is never visible through the dropdown.
            "lk-menu-in fixed inset-x-3 top-[4.5rem] z-50 overflow-hidden rounded-2xl border border-border-strong bg-surface-raised shadow-pop",
            "sm:absolute sm:inset-x-0 sm:top-full sm:mt-2",
          )}
        >
          {/* Mobile-only search input (no inline bar exists on mobile). */}
          <div className="relative flex items-center border-b border-border px-3 py-2 sm:hidden">
            <Search className="pointer-events-none absolute left-5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
            <input
              ref={mobileInputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Search sections…"
              aria-label="Search and jump to a section"
              className="h-9 w-full rounded-lg border border-border bg-surface pl-8 pr-3 text-sm text-ink placeholder:text-ink-faint focus:border-border-strong focus:outline-none"
            />
          </div>

          <ul
            ref={listRef}
            role="listbox"
            aria-label="Search results"
            className="max-h-[min(60vh,26rem)] overflow-y-auto overflow-x-hidden p-2"
          >
            {results.length === 0 ? (
              <li className="px-3 py-8 text-center">
                <p className="text-sm font-medium text-ink">No results found</p>
                <p className="mt-1 text-xs text-ink-muted">
                  Try searching orders, operations, customers, facilities, reports, or agents.
                </p>
              </li>
            ) : (
              results.map((r, i) => {
                const on = i === active;
                const Icon = r.icon;
                return (
                  <li
                    key={`${r.href}-${i}`}
                    data-idx={i}
                    role="option"
                    aria-selected={on}
                    onMouseEnter={() => setActive(i)}
                    onClick={() => go(r.href)}
                    className={cn(
                      // Highlight uses warm amber/gold — distinct from the teal/green
                      // used elsewhere. Tint sits on the solid surface (never see-through).
                      "flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors",
                      on
                        ? "bg-accent-amber/[0.16] text-ink ring-1 ring-inset ring-accent-amber/30"
                        : "hover:bg-accent-amber/[0.10]",
                    )}
                  >
                    <span
                      className={cn(
                        "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-transform",
                        r.accent.chip,
                        on && "scale-105",
                      )}
                    >
                      <Icon className="h-4 w-4" />
                    </span>
                    <span className="min-w-0 flex-1 truncate">
                      {r.group && <span className="text-ink-faint">{r.group} · </span>}
                      <span className="font-medium text-ink">{r.label}</span>
                    </span>
                    {on && <CornerDownLeft className="h-3.5 w-3.5 shrink-0 text-accent-amber" />}
                  </li>
                );
              })
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
