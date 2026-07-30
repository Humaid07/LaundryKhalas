"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Filter, Check, X } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  emptyFilterState,
  inboxFilterCount,
  type InboxFilter,
  type InboxFilterState,
  type OrderStatusFilter,
} from "@/lib/dashboard/whatsapp-inbox";

/**
 * Compact filter control for the WhatsApp inbox list. Replaces the always-on
 * pill wall with ONE funnel button (carrying an active-count badge) that opens a
 * focus-managed popover. Mirrors the shell FilterMenu pattern (outside-click +
 * Escape + focus return) so it feels native.
 *
 * Two groups:
 *  - Attention  → checkboxes (Human Needed + Urgent can both be on).
 *  - Order status → radios (Active vs Resolved are mutually exclusive).
 * Counts are supplied by the parent from the live conversation dataset.
 */
export function InboxFilterMenu({
  state,
  onChange,
  counts,
  className,
}: {
  state: InboxFilterState;
  onChange: (next: InboxFilterState) => void;
  counts: Record<InboxFilter, number>;
  className?: string;
}) {
  const activeCount = inboxFilterCount(state);
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const panelId = useId();

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  // Close on Escape + return focus to the trigger.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
        btnRef.current?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  // Move focus into the panel when it opens.
  useEffect(() => {
    if (open) panelRef.current?.focus();
  }, [open]);

  // Re-clicking the active order-status radio clears it back to "any".
  const setOrderStatus = (v: OrderStatusFilter) =>
    onChange({ ...state, orderStatus: state.orderStatus === v ? "any" : v });

  return (
    <div ref={rootRef} className={cn("relative shrink-0", className)}>
      <button
        ref={btnRef}
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        aria-label="Filter conversations"
        title="Filter conversations"
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "inline-flex h-9 items-center gap-1.5 rounded-full border px-3 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40",
          activeCount > 0
            ? "border-rose/40 bg-rose/10 text-rose hover:bg-rose/[0.14]"
            : "border-border bg-surface-2 text-ink-muted hover:border-border-strong hover:text-ink",
        )}
      >
        <Filter className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">Filter</span>
        {activeCount > 0 && (
          <span className="grid h-4 min-w-4 place-items-center rounded-full bg-rose px-1 text-[10px] font-bold text-rose-contrast tnum">
            {activeCount}
          </span>
        )}
      </button>

      {open && (
        <div
          ref={panelRef}
          id={panelId}
          role="dialog"
          aria-label="Filter conversations"
          tabIndex={-1}
          className="lk-menu-in absolute right-0 z-50 mt-2 w-[min(17rem,calc(100vw-1.5rem))] rounded-2xl border border-border-strong bg-surface-raised p-3 shadow-pop focus:outline-none"
        >
          <div className="mb-2 flex items-center justify-between">
            <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">
              Filter conversations
            </p>
            {activeCount > 0 && (
              <button
                type="button"
                onClick={() => onChange(emptyFilterState)}
                className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xxs font-semibold text-ink-muted transition-colors hover:bg-surface-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40"
              >
                <X className="h-3 w-3" /> Clear all
              </button>
            )}
          </div>

          {/* Attention — multi-select checkboxes */}
          <Group label="Attention">
            <OptionRow
              variant="checkbox"
              label="Human Needed"
              count={counts.human_needed}
              checked={state.humanNeeded}
              onActivate={() => onChange({ ...state, humanNeeded: !state.humanNeeded })}
            />
            <OptionRow
              variant="checkbox"
              label="Urgent"
              count={counts.urgent}
              checked={state.urgent}
              onActivate={() => onChange({ ...state, urgent: !state.urgent })}
            />
          </Group>

          {/* Order status — single-select radios (mutually exclusive) */}
          <Group label="Order status" last>
            <div role="radiogroup" aria-label="Order status" className="flex flex-col gap-0.5">
              <OptionRow
                variant="radio"
                label="Active Orders"
                count={counts.active_orders}
                checked={state.orderStatus === "active"}
                onActivate={() => setOrderStatus("active")}
              />
              <OptionRow
                variant="radio"
                label="Resolved"
                count={counts.resolved}
                checked={state.orderStatus === "resolved"}
                onActivate={() => setOrderStatus("resolved")}
              />
            </div>
          </Group>
        </div>
      )}
    </div>
  );
}

function Group({ label, children, last }: { label: string; children: ReactNode; last?: boolean }) {
  return (
    <div className={cn("space-y-0.5", !last && "mb-2 border-b border-border pb-2")}>
      <p className="px-2 pb-0.5 text-[10px] font-semibold uppercase tracking-eyebrow text-ink-faint">
        {label}
      </p>
      {children}
    </div>
  );
}

function OptionRow({
  variant,
  label,
  count,
  checked,
  onActivate,
}: {
  variant: "checkbox" | "radio";
  label: string;
  count: number;
  checked: boolean;
  onActivate: () => void;
}) {
  return (
    <button
      type="button"
      role={variant}
      aria-checked={checked}
      onClick={onActivate}
      className={cn(
        "flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm transition-colors hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40",
        checked ? "text-ink" : "text-ink-muted hover:text-ink",
      )}
    >
      <span
        className={cn(
          "grid h-4 w-4 shrink-0 place-items-center border transition-colors",
          variant === "checkbox" ? "rounded" : "rounded-full",
          checked ? "border-rose bg-rose text-rose-contrast" : "border-border-strong",
        )}
      >
        {checked &&
          (variant === "checkbox" ? (
            <Check className="h-3 w-3" />
          ) : (
            <span className="h-1.5 w-1.5 rounded-full bg-rose-contrast" />
          ))}
      </span>
      <span className="min-w-0 flex-1 truncate font-medium">{label}</span>
      <span className="tnum shrink-0 text-xxs text-ink-faint">{count}</span>
    </button>
  );
}
