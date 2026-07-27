"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bell,
  Check,
  X,
  Package,
  Truck,
  AlertTriangle,
  MessageSquare,
  Wallet,
  CalendarDays,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { facilityApi, type FacilityNotification } from "@/lib/api-client";
import { formatRelativeTime } from "@/lib/formatters";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";

/** Icon per notification type — falls back to a bell for unknown types. */
const TYPE_ICON: Record<string, LucideIcon> = {
  new_order_assigned: Package,
  order_status_updated: Package,
  driver_assigned: Truck,
  sla_risk: AlertTriangle,
  issue_response: MessageSquare,
  internal_issue_reply: MessageSquare,
  payout_update: Wallet,
  daily_summary: CalendarDays,
};

/** Where a notification should navigate when tapped — issues take precedence
 *  over the linked order. Returns null when there's nowhere meaningful to go. */
function notificationHref(n: FacilityNotification): string | null {
  if (n.issue_id) return `/issues/${n.issue_id}`;
  if (n.related_order_id) return `/orders/${n.related_order_id}`;
  return null;
}

/**
 * NotificationCenter — a right-side drawer listing the facility's notifications.
 * Tapping one marks it read and (if it links an order) navigates there.
 */
export function NotificationCenter({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["notifications", "list"],
    queryFn: () => facilityApi.notifications(),
    enabled: open,
  });

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

  const markRead = async (n: FacilityNotification) => {
    if (n.read) return;
    try {
      await facilityApi.markNotificationRead(n.id);
      qc.invalidateQueries({ queryKey: ["notifications"] });
    } catch {
      /* fail soft — badge will re-sync on next poll */
    }
  };

  const notifications = data ?? [];

  return (
    <div className={cn("fixed inset-0 z-[60]", open ? "pointer-events-auto" : "pointer-events-none")} aria-hidden={!open}>
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
        aria-label="Notifications"
        className={cn(
          "absolute inset-y-0 right-0 flex w-full max-w-[420px] flex-col border-l border-border bg-surface shadow-pop transition-transform duration-300 ease-out-quint",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <header className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-rose/12 text-rose">
              <Bell className="h-4 w-4" />
            </span>
            <h2 className="font-display text-lg font-semibold text-ink">Notifications</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close notifications"
            className="flex h-9 w-9 items-center justify-center rounded-lg text-ink-muted transition-colors hover:bg-surface-2 hover:text-ink"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto p-4">
          {isLoading ? (
            <LoadingState label="Loading notifications…" />
          ) : isError ? (
            <ErrorState description="Could not load notifications." onRetry={() => refetch()} />
          ) : notifications.length === 0 ? (
            <EmptyState icon={Bell} title="You're all caught up" description="New order and issue updates will appear here." />
          ) : (
            <ul className="space-y-2">
              {notifications.map((n) => {
                const Icon = (n.type && TYPE_ICON[n.type]) || Bell;
                const href = notificationHref(n);
                const inner = (
                  <div
                    className={cn(
                      "flex gap-3 rounded-xl border p-3.5 transition-colors",
                      n.read ? "border-border/60 bg-surface" : "border-rose/25 bg-rose/[0.06]",
                    )}
                  >
                    <span
                      className={cn(
                        "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg",
                        n.read ? "bg-ink/6 text-ink-faint" : "bg-rose/12 text-rose",
                      )}
                    >
                      <Icon className="h-3.5 w-3.5" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-ink">{n.title ?? "Update"}</p>
                      {n.body && <p className="mt-0.5 text-xs leading-relaxed text-ink-muted">{n.body}</p>}
                      <p className="mt-1.5 text-xxs text-ink-faint">{formatRelativeTime(n.created_at)}</p>
                    </div>
                    {!n.read && <Check className="mt-1 h-4 w-4 shrink-0 text-ink-faint" />}
                  </div>
                );
                return (
                  <li key={n.id}>
                    {href ? (
                      <Link
                        href={href}
                        onClick={() => {
                          markRead(n);
                          onClose();
                        }}
                        className="block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40 rounded-xl"
                      >
                        {inner}
                      </Link>
                    ) : (
                      <button type="button" onClick={() => markRead(n)} className="block w-full text-left">
                        {inner}
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </aside>
    </div>
  );
}
