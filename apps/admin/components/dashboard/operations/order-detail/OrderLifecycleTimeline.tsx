"use client";

import { Check, AlertTriangle, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatRelativeTime } from "@/lib/dashboard/formatters";
import type { Order } from "@/lib/dashboard/types";
import { lifecycleSteps, isCancelled, isFlagged, nextStep } from "./data";

/**
 * A premium, step-based vertical lifecycle timeline. Completed steps read solid
 * rose with a check; the current step is highlighted with a ring + label; future
 * steps are muted. Cancelled / flagged orders get a clear banner instead of a
 * misleading progress bar.
 */
export function OrderLifecycleTimeline({ order }: { order: Order }) {
  const steps = lifecycleSteps(order);
  const cancelled = isCancelled(order);
  const flagged = isFlagged(order);

  return (
    <div className="space-y-4">
      {cancelled && (
        <div className="flex items-start gap-2.5 rounded-xl border border-danger/25 bg-danger/8 px-3.5 py-2.5">
          <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-danger" />
          <p className="text-xs text-ink"><span className="font-semibold text-danger">Order cancelled.</span> Progression is closed. {order.payment === "Refunded" && "A refund was issued."}</p>
        </div>
      )}
      {flagged && (
        <div className="flex items-start gap-2.5 rounded-xl border border-warning/30 bg-warning/8 px-3.5 py-2.5">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
          <p className="text-xs text-ink"><span className="font-semibold text-warning">Concern raised.</span> This order is flagged for review — progression is on hold pending resolution.</p>
        </div>
      )}

      <ol className="relative">
        {steps.map((s, i) => {
          const last = i === steps.length - 1;
          const done = s.state === "done";
          const current = s.state === "current";
          return (
            <li key={s.label} className="relative flex gap-4 pb-6 last:pb-0">
              {/* connector */}
              {!last && (
                <span
                  className={cn(
                    "absolute left-[11px] top-6 h-[calc(100%-1rem)] w-px",
                    done ? "bg-rose/40" : "bg-border",
                  )}
                  aria-hidden
                />
              )}
              {/* node */}
              <span
                className={cn(
                  "relative z-10 mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 transition-colors",
                  done && "border-rose bg-rose text-rose-contrast",
                  current && "border-rose bg-surface text-rose ring-4 ring-rose/15",
                  s.state === "future" && "border-border bg-surface text-ink-faint",
                )}
              >
                {done ? <Check className="h-3.5 w-3.5" /> : <span className={cn("h-1.5 w-1.5 rounded-full", current ? "bg-rose" : "bg-ink-faint/50")} />}
              </span>
              {/* content */}
              <div className="min-w-0 flex-1 pt-0.5">
                <div className="flex flex-wrap items-center gap-2">
                  <p className={cn("text-sm font-semibold", current ? "text-rose" : done ? "text-ink" : "text-ink-faint")}>{s.label}</p>
                  {current && <span className="rounded-full bg-rose/12 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-rose">Current</span>}
                </div>
                {(s.at || s.actor) && (
                  <p className="mt-0.5 text-xs text-ink-muted">
                    {s.at && formatRelativeTime(s.at)}{s.at && s.actor && " · "}{s.actor}
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ol>

      {!cancelled && (
        <div className="rounded-xl border border-border/70 bg-surface-2 px-3.5 py-3">
          <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Next step</p>
          <p className="mt-1 text-sm text-ink">{nextStep(order)}</p>
        </div>
      )}
    </div>
  );
}
