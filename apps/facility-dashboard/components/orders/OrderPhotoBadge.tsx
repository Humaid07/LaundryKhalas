import { Camera } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * OrderPhotoBadge — a subtle proof-photo indicator for the order card.
 *
 * Guidance-only (never blocks a status change): if items are in/at the facility
 * with no intake photo, or ready for handoff with no pre-dispatch photo, it
 * nudges "… photo needed"; otherwise it shows the photo count, or nothing when
 * there is nothing useful to say. Kept deliberately small so the card stays clean.
 */
const INTAKE_STATUSES = new Set(["active", "pickup_scheduled", "picked_up", "in_cleaning"]);
const DISPATCH_STATUSES = new Set(["ready_for_delivery", "out_for_delivery"]);

export function OrderPhotoBadge({
  status,
  intakeCount = 0,
  preDispatchCount = 0,
  className,
}: {
  status?: string | null;
  intakeCount?: number | null;
  preDispatchCount?: number | null;
  className?: string;
}) {
  const s = (status ?? "").toLowerCase();
  const intake = intakeCount ?? 0;
  const dispatch = preDispatchCount ?? 0;
  const total = intake + dispatch;

  const needsIntake = INTAKE_STATUSES.has(s) && intake === 0;
  const needsDispatch = DISPATCH_STATUSES.has(s) && dispatch === 0;

  let tone: "warning" | "muted" = "muted";
  let label: string;
  if (needsIntake) {
    tone = "warning";
    label = "Intake photo needed";
  } else if (needsDispatch) {
    tone = "warning";
    label = "Dispatch photo needed";
  } else if (total > 0) {
    label = `${total} photo${total === 1 ? "" : "s"}`;
  } else {
    return null; // nothing worth showing
  }

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-xxs font-medium",
        tone === "warning"
          ? "bg-warning/12 text-warning"
          : "bg-surface-2 text-ink-muted",
        className,
      )}
    >
      <Camera className="h-3 w-3" />
      {label}
    </span>
  );
}
