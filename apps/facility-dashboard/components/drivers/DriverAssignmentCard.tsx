import Link from "next/link";
import { Package, Clock } from "lucide-react";
import type { DriverAssignment } from "@/lib/api-client";
import { formatDateTime } from "@/lib/formatters";
import {
  assignmentStatusLabel,
  assignmentStatusTone,
  taskTypeLabel,
  taskTypeTone,
} from "@/lib/status";
import { StatusBadge } from "@/components/ui/primitives";

/**
 * DriverAssignmentCard — one delivery/pickup task in a driver's task list:
 * order ref, service summary, task type, status and timing. Links to the order
 * when one is attached. No customer PII is present in the payload.
 */
export function DriverAssignmentCard({ assignment }: { assignment: DriverAssignment }) {
  const orderRef = assignment.order_ref ?? assignment.order_id ?? null;

  return (
    <div className="rounded-xl border border-border/60 bg-surface-2 px-3.5 py-3">
      <div className="flex flex-wrap items-center gap-2">
        {orderRef &&
          (assignment.order_id ? (
            <Link
              href={`/orders/${assignment.order_id}`}
              className="inline-flex items-center gap-1 font-mono text-xs font-semibold text-rose hover:underline"
            >
              <Package className="h-3 w-3" />
              {orderRef}
            </Link>
          ) : (
            <span className="inline-flex items-center gap-1 font-mono text-xs font-semibold text-rose">
              <Package className="h-3 w-3" />
              {orderRef}
            </span>
          ))}
        <StatusBadge tone={taskTypeTone(assignment.task_type)} dot={false}>
          {taskTypeLabel(assignment.task_type)}
        </StatusBadge>
        <StatusBadge tone={assignmentStatusTone(assignment.status)} dot={false}>
          {assignmentStatusLabel(assignment.status)}
        </StatusBadge>
      </div>

      {assignment.service_summary && (
        <p className="mt-1.5 text-sm text-ink">{assignment.service_summary}</p>
      )}

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xxs text-ink-faint">
        {assignment.area && <span>{assignment.area}</span>}
        <span>Assigned {formatDateTime(assignment.assigned_at)}</span>
        {assignment.expected_completion_at && (
          <span className="inline-flex items-center gap-1">
            <Clock className="h-3 w-3" />
            Due {formatDateTime(assignment.expected_completion_at)}
          </span>
        )}
        {assignment.completed_at && <span>Completed {formatDateTime(assignment.completed_at)}</span>}
      </div>

      {assignment.notes && <p className="mt-1.5 text-xs text-ink-muted">{assignment.notes}</p>}
    </div>
  );
}
