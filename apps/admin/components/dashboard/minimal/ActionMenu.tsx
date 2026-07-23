"use client";

import { useEffect, useRef, useState } from "react";
import { MoreHorizontal, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export type MenuItem = {
  label: string;
  icon?: LucideIcon;
  tone?: "default" | "danger";
  /** Marks an action that requires human approval before it takes effect (RULE 13). */
  approval?: boolean;
  onClick?: () => void;
  disabled?: boolean;
};

/**
 * ActionMenu — overflow menu for secondary/risky record actions on a detail page.
 * Actions live ONLY on detail pages (never on main-page cards). Approval-gated
 * items are labelled so operators know a human sign-off is required.
 */
export function ActionMenu({ items, label = "More actions" }: { items: MenuItem[]; label?: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-border bg-surface-2 px-3 text-sm font-medium text-ink transition-colors hover:border-border-strong"
      >
        <MoreHorizontal className="h-4 w-4" /> {label}
      </button>
      {open && (
        <div role="menu" className="lk-menu-in absolute right-0 z-30 mt-1.5 w-60 overflow-hidden rounded-xl border border-border bg-surface p-1.5 shadow-pop">
          {items.map((it) => (
            <button
              key={it.label}
              type="button"
              role="menuitem"
              disabled={it.disabled}
              onClick={() => {
                it.onClick?.();
                setOpen(false);
              }}
              className={cn(
                "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-45",
                it.tone === "danger" ? "text-danger hover:bg-danger/8" : "text-ink hover:bg-surface-2",
              )}
            >
              {it.icon && <it.icon className="h-4 w-4 shrink-0 opacity-80" />}
              <span className="flex-1 truncate">{it.label}</span>
              {it.approval && (
                <span className="shrink-0 rounded-full bg-warning/15 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-warning">
                  Approval
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
