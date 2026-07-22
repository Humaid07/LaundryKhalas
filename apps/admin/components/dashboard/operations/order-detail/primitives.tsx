"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { MoreHorizontal, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { StatusBadge } from "@/components/dashboard/ui/primitives";
import type { Tone } from "@/lib/dashboard/types";

/* Spacious, softly-bordered section block — the building unit of the detail page. */
export function SectionCard({
  title, icon: Icon, action, children, className, bodyClassName,
}: {
  title?: string;
  icon?: LucideIcon;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={cn("rounded-2xl border border-border/70 bg-surface shadow-card", className)}>
      {title && (
        <header className="flex items-center justify-between gap-3 border-b border-border/60 px-5 py-3.5">
          <div className="flex items-center gap-2.5">
            {Icon && <Icon className="h-4 w-4 text-rose" />}
            <h2 className="font-display text-[0.95rem] font-semibold text-ink">{title}</h2>
          </div>
          {action}
        </header>
      )}
      <div className={cn("px-5 py-4", bodyClassName)}>{children}</div>
    </section>
  );
}

/** A label/value pair. `mono` for IDs, `strong` for emphasis. */
export function Field({ label, value, mono }: { label: string; value: ReactNode; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-xxs font-medium uppercase tracking-eyebrow text-ink-faint">{label}</dt>
      <dd className={cn("mt-1 break-words text-sm font-medium text-ink", mono && "font-mono")}>{value ?? "—"}</dd>
    </div>
  );
}

export function FieldGrid({ children, cols = 2 }: { children: ReactNode; cols?: 2 | 3 }) {
  return <dl className={cn("grid gap-x-6 gap-y-4", cols === 3 ? "sm:grid-cols-3" : "sm:grid-cols-2")}>{children}</dl>;
}

export function Chip({ tone, children }: { tone: Tone; children: ReactNode }) {
  return <StatusBadge tone={tone} dot={false}>{children}</StatusBadge>;
}

/* ------------------------------- overflow menu ------------------------------ */

export type MenuItem = {
  label: string;
  icon?: LucideIcon;
  tone?: "default" | "danger";
  approval?: boolean;
  onClick?: () => void;
  disabled?: boolean;
};

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
        <div role="menu" className="absolute right-0 z-30 mt-1.5 w-60 overflow-hidden rounded-xl border border-border bg-surface p-1.5 shadow-pop">
          {items.map((it) => (
            <button
              key={it.label}
              type="button"
              role="menuitem"
              disabled={it.disabled}
              onClick={() => { it.onClick?.(); setOpen(false); }}
              className={cn(
                "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-45",
                it.tone === "danger" ? "text-danger hover:bg-danger/8" : "text-ink hover:bg-surface-2",
              )}
            >
              {it.icon && <it.icon className="h-4 w-4 shrink-0 opacity-80" />}
              <span className="flex-1 truncate">{it.label}</span>
              {it.approval && <span className="shrink-0 rounded-full bg-warning/15 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-warning">Approval</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
