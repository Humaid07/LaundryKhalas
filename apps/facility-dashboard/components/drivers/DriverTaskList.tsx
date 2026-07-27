import type { DriverAssignment } from "@/lib/api-client";
import { DriverAssignmentCard } from "./DriverAssignmentCard";

/**
 * DriverTaskList — a vertical stack of the driver's assignments (today / recent).
 * Renders a quiet inline message when there are none.
 */
export function DriverTaskList({
  assignments,
  emptyLabel = "No assignments yet.",
}: {
  assignments: DriverAssignment[];
  emptyLabel?: string;
}) {
  if (!assignments || assignments.length === 0) {
    return <p className="text-sm text-ink-muted">{emptyLabel}</p>;
  }
  return (
    <div className="space-y-2.5">
      {assignments.map((a) => (
        <DriverAssignmentCard key={a.id} assignment={a} />
      ))}
    </div>
  );
}
