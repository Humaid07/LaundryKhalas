"use client";

import { useEffect, type ReactNode } from "react";
import { X, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { StatusBadge } from "@/components/dashboard/ui/primitives";
import type { Tone } from "@/lib/dashboard/types";

/* ============================================================================
 * Operations workspace primitives — the shared building blocks that give every
 * Operations subsection the SAME shape:
 *   sidebar (which subsection)  →  WorkflowTabs (which status/workflow view)
 *   →  RecordCard grid (filtered records)  →  DetailDrawer (full data + actions)
 *
 * See docs/architecture/operations-navigation.md. Subsection navigation lives
 * ONLY in the left sidebar; these top tabs are status/workflow filters, never
 * links to another subsection. Actions live ONLY inside the DetailDrawer for the
 * selected record — never as a standalone actions panel on the page.
 * ========================================================================== */

/* ------------------------------ Workflow tabs ------------------------------- */

export type WorkflowTab = { id: string; label: string; count?: number };

export function WorkflowTabs({
  tabs,
  value,
  onChange,
}: {
  tabs: WorkflowTab[];
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <div role="tablist" className="inline-flex min-w-max gap-1 rounded-xl border border-border bg-surface-2 p-1">
        {tabs.map((t) => {
          const on = t.id === value;
          return (
            <button
              key={t.id}
              role="tab"
              aria-selected={on}
              onClick={() => onChange(t.id)}
              className={cn(
                "flex items-center gap-2 whitespace-nowrap rounded-lg px-3.5 py-2 text-sm font-semibold transition-all duration-200",
                on ? "bg-surface text-rose shadow-card" : "text-ink-muted hover:text-ink",
              )}
            >
              {t.label}
              {typeof t.count === "number" && (
                <span
                  className={cn(
                    "rounded-full px-1.5 py-0.5 text-xxs font-semibold tnum",
                    on ? "bg-rose/12 text-rose" : "bg-ink/8 text-ink-muted",
                  )}
                >
                  {t.count}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ------------------------------- Record card -------------------------------- */

export type CardField = { label: string; value: ReactNode };

/** A clickable operational record card. Clicking opens the DetailDrawer — the
 * card itself carries NO actions (those live in the drawer). */
export function RecordCard({
  id,
  title,
  badges,
  fields,
  footer,
  onClick,
}: {
  id?: string;
  title: ReactNode;
  badges?: ReactNode;
  fields: CardField[];
  footer?: ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex w-full flex-col rounded-xl border border-border bg-surface p-4 text-left shadow-card transition-all duration-200 ease-out-quint hover:-translate-y-0.5 hover:border-rose/40 hover:shadow-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          {id && <p className="font-mono text-xs font-semibold text-rose">{id}</p>}
          <p className="mt-0.5 truncate text-sm font-semibold text-ink">{title}</p>
        </div>
        {badges && <div className="flex shrink-0 flex-wrap items-center justify-end gap-1">{badges}</div>}
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 border-t border-border pt-3">
        {fields.map((f, i) => (
          <div key={i} className="min-w-0">
            <dt className="text-xxs uppercase tracking-eyebrow text-ink-faint">{f.label}</dt>
            <dd className="truncate text-xs font-medium text-ink">{f.value ?? "—"}</dd>
          </div>
        ))}
      </dl>
      {footer && <div className="mt-3 border-t border-border pt-3 text-xs text-ink-muted">{footer}</div>}
    </button>
  );
}

/** Responsive grid wrapper for RecordCards. */
export function CardGrid({ children }: { children: ReactNode }) {
  return <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{children}</div>;
}

/* ------------------------------ Detail drawer ------------------------------- */

export function DetailDrawer({
  open,
  onClose,
  eyebrow,
  title,
  subtitle,
  badges,
  children,
  actions,
}: {
  open: boolean;
  onClose: () => void;
  eyebrow?: string;
  title: ReactNode;
  subtitle?: ReactNode;
  badges?: ReactNode;
  children: ReactNode;
  /** Actions footer — the ONLY place actions for a record appear. */
  actions?: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  return (
    <div className={cn("fixed inset-0 z-50", open ? "pointer-events-auto" : "pointer-events-none")} aria-hidden={!open}>
      <div
        onClick={onClose}
        className={cn(
          "absolute inset-0 bg-ink/40 backdrop-blur-sm transition-opacity duration-300",
          open ? "opacity-100" : "opacity-0",
        )}
      />
      <aside
        role="dialog"
        aria-modal="true"
        className={cn(
          "absolute inset-y-0 right-0 flex w-full max-w-[480px] flex-col border-l border-border bg-surface shadow-pop transition-transform duration-300 ease-out-quint",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <header className="flex items-start justify-between gap-3 border-b border-border px-5 py-4">
          <div className="min-w-0">
            {eyebrow && <p className="text-xxs font-semibold uppercase tracking-eyebrow text-rose">{eyebrow}</p>}
            <h2 className="truncate font-display text-lg font-semibold text-ink">{title}</h2>
            {subtitle && <p className="mt-0.5 text-xs text-ink-muted">{subtitle}</p>}
            {badges && <div className="mt-2 flex flex-wrap items-center gap-1.5">{badges}</div>}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close details"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-ink-muted transition-colors hover:bg-surface-2 hover:text-ink"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="flex-1 space-y-5 overflow-y-auto px-5 py-5">{children}</div>

        {actions && <footer className="border-t border-border bg-surface-2/40 px-5 py-4">{actions}</footer>}
      </aside>
    </div>
  );
}

/* ---------------------- Drawer building blocks ------------------------------ */

/** A titled section inside the drawer body. */
export function DrawerSection({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">{title}</h3>
        {action}
      </div>
      {children}
    </section>
  );
}

/** A label/value grid for the drawer body. */
export function DetailFields({ fields }: { fields: CardField[] }) {
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
      {fields.map((f, i) => (
        <div key={i} className="min-w-0">
          <dt className="text-xxs uppercase tracking-eyebrow text-ink-faint">{f.label}</dt>
          <dd className="mt-0.5 break-words text-sm font-medium text-ink">{f.value ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

/** A vertical lifecycle/event timeline for the drawer body. */
export function DrawerTimeline({ events }: { events: { label: string; time?: string; tone?: Tone; done?: boolean }[] }) {
  return (
    <ol className="space-y-3">
      {events.map((e, i) => (
        <li key={i} className="flex gap-3">
          <span
            className={cn(
              "mt-1 h-2 w-2 shrink-0 rounded-full",
              e.done ? "bg-rose" : e.tone === "danger" ? "bg-danger" : e.tone === "warning" ? "bg-warning" : "bg-ink-faint/40",
            )}
          />
          <div className="min-w-0">
            <p className="text-sm text-ink">{e.label}</p>
            {e.time && <p className="text-xxs text-ink-faint">{e.time}</p>}
          </div>
        </li>
      ))}
    </ol>
  );
}

/* -------------------------------- Actions ----------------------------------- */

export type DrawerAction = {
  label: string;
  icon: LucideIcon;
  tone?: "default" | "primary" | "danger";
  /** Requires human approval before it takes effect (RULE 13). */
  approval?: boolean;
  /** Show but disable (e.g. "Cancel order" only when policy allows). */
  disabled?: boolean;
  onClick?: () => void;
};

/** The actions block rendered in a drawer footer — the ONLY place record
 * actions live. Approval-gated actions are labelled so operators know a human
 * sign-off is required (nothing here performs a live action in mock mode). */
export function DrawerActions({ actions, note }: { actions: DrawerAction[]; note?: string }) {
  return (
    <div className="space-y-2.5">
      <div className="grid grid-cols-2 gap-2">
        {actions.map((a) => (
          <button
            key={a.label}
            type="button"
            disabled={a.disabled}
            onClick={a.onClick}
            title={a.disabled ? "Not available for this record" : undefined}
            className={cn(
              "flex items-center gap-2 rounded-lg border px-2.5 py-2 text-left text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-45",
              a.tone === "danger"
                ? "border-danger/25 bg-danger/8 text-danger hover:bg-danger/12"
                : a.tone === "primary"
                  ? "border-rose/30 bg-rose/10 text-rose hover:bg-rose/16"
                  : "border-border bg-surface text-ink hover:border-rose/40",
            )}
          >
            <a.icon className="h-3.5 w-3.5 shrink-0 opacity-80" />
            <span className="flex-1 truncate">{a.label}</span>
            {a.approval && (
              <span className="shrink-0 rounded-full bg-warning/15 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-warning">
                Approval
              </span>
            )}
          </button>
        ))}
      </div>
      {note && <p className="text-xxs text-ink-faint">{note}</p>}
    </div>
  );
}

/** Small helper to render a tone badge inline in cards/drawers. */
export function Badge({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <StatusBadge tone={tone} dot={false}>
      {children}
    </StatusBadge>
  );
}

/** Mask a phone number for list views (privacy firewall) — keep the country
 * code and last 2 digits, hide the middle: "+971 50 220 4471" → "+971 •• •• 71".
 * The full number is shown only in the secure detail drawer. */
export function maskPhone(phone: string | null | undefined): string {
  if (!phone) return "—";
  const digits = phone.replace(/\D/g, "");
  if (digits.length < 4) return "•••";
  const cc = phone.trim().startsWith("+") ? `+${digits.slice(0, digits.length - 9 > 0 ? digits.length - 9 : 2)}` : "";
  return `${cc} •• ••• ${digits.slice(-2)}`.trim();
}
