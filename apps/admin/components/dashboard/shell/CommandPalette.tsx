"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
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
 * ⌘K command palette — fast keyboard navigation to any section or subsection,
 * so operators don't have to hunt the sidebar tree. Opened from the Topbar search
 * (or ⌘K / Ctrl+K). Arrow keys move, Enter navigates, Esc closes.
 */
export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return COMMANDS.slice(0, 60);
    return COMMANDS.filter((c) => c.keywords.includes(q)).slice(0, 60);
  }, [query]);

  // Reset state + focus the input each time the palette opens.
  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      // focus after paint
      const id = requestAnimationFrame(() => inputRef.current?.focus());
      return () => cancelAnimationFrame(id);
    }
  }, [open]);

  useEffect(() => setActive(0), [query]);

  // Keep the highlighted row in view.
  useEffect(() => {
    if (!open || !listRef.current) return;
    const el = listRef.current.querySelector(`[data-idx="${active}"]`) as HTMLElement | null;
    el?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  if (!open) return null;

  const go = (href: string) => {
    onClose();
    router.push(href);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
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

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center px-4 pt-[12vh]" role="dialog" aria-modal="true" aria-label="Command palette">
      {/* backdrop */}
      <div className="absolute inset-0 bg-ink/40 backdrop-blur-sm" onClick={onClose} aria-hidden />

      <div
        className="lk-menu-in relative w-full max-w-xl overflow-hidden rounded-2xl border border-border-strong bg-surface-raised shadow-pop"
        onKeyDown={onKeyDown}
      >
        <div className="flex items-center gap-3 border-b border-border px-4">
          <Search className="h-4 w-4 shrink-0 text-ink-faint" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Jump to a section or subsection…"
            aria-label="Search sections"
            className="h-12 w-full bg-transparent text-sm text-ink placeholder:text-ink-faint focus:outline-none"
          />
          <kbd className="hidden rounded border border-border bg-surface-2 px-1.5 py-0.5 text-xxs font-medium text-ink-faint sm:block">Esc</kbd>
        </div>

        <ul ref={listRef} role="listbox" aria-label="Results" className="max-h-[52vh] overflow-y-auto p-2">
          {results.length === 0 ? (
            <li className="px-3 py-8 text-center text-sm text-ink-muted">No matches for “{query}”.</li>
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
                    "flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors",
                    on ? "bg-surface-2" : "hover:bg-surface-2",
                  )}
                >
                  <span className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-lg", r.accent.chip)}>
                    <Icon className="h-4 w-4" />
                  </span>
                  <span className="min-w-0 flex-1 truncate">
                    {r.group && <span className="text-ink-faint">{r.group} · </span>}
                    <span className="font-medium text-ink">{r.label}</span>
                  </span>
                  {on && <CornerDownLeft className="h-3.5 w-3.5 shrink-0 text-ink-faint" />}
                </li>
              );
            })
          )}
        </ul>
      </div>
    </div>
  );
}
