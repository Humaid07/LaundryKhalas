import { cn } from "@/lib/utils";
import { titleCase } from "@/lib/formatters";

type Tone = "success" | "warning" | "danger" | "info" | "neutral";

const TONE_CLASSES: Record<Tone, string> = {
  success: "bg-success-soft text-success-text",
  warning: "bg-warning-soft text-warning-text",
  danger: "bg-danger-soft text-danger-text",
  info: "bg-info-soft text-info-text",
  neutral: "bg-neutral-soft text-neutral-text",
};

const STATUS_TONE: Record<string, Tone> = {
  // conversation
  open: "info",
  closed: "neutral",
  // orders
  draft: "neutral",
  created: "info",
  awaiting_pickup: "info",
  picked_up: "info",
  processing: "info",
  ready_for_delivery: "info",
  out_for_delivery: "info",
  delivered: "success",
  cancelled: "neutral",
  escalated: "danger",
  // approvals
  pending: "warning",
  approved: "success",
  rejected: "danger",
  // messages
  received: "neutral",
  stored: "neutral",
  mock_sent: "success",
  failed: "danger",
  // misc
  manual_takeover: "warning",
  success: "success",
};

// Display overrides for status values whose raw key isn't customer-friendly.
const STATUS_LABEL: Record<string, string> = {
  mock_sent: "Sent",
};

export function StatusBadge({ status, className }: { status: string | null | undefined; className?: string }) {
  const key = (status ?? "").toLowerCase();
  const tone = STATUS_TONE[key] ?? "neutral";
  return (
    <span
      className={cn(
        "inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xxs font-semibold tracking-wide",
        TONE_CLASSES[tone],
        className
      )}
    >
      {STATUS_LABEL[key] ?? titleCase(status)}
    </span>
  );
}

export function BooleanBadge({
  value,
  trueLabel,
  falseLabel,
  trueTone = "warning",
}: {
  value: boolean;
  trueLabel: string;
  falseLabel?: string;
  trueTone?: Tone;
}) {
  if (!value && !falseLabel) return null;
  const tone = value ? trueTone : "neutral";
  return (
    <span
      className={cn(
        "inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xxs font-semibold tracking-wide",
        TONE_CLASSES[tone]
      )}
    >
      {value ? trueLabel : falseLabel}
    </span>
  );
}
