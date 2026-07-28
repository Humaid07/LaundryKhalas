import { AlertTriangle } from "lucide-react";
import type { DriverAssignment } from "@/lib/api-client";
import { statusToken } from "@/lib/status";
import { DriverAssignmentCard } from "./DriverAssignmentCard";

/**
 * DriverIssuePanel — surfaces assignments currently flagged with an "issue"
 * status so a manager can act on them. Renders nothing prominent when clear.
 */
export function DriverIssuePanel({ assignments }: { assignments: DriverAssignment[] }) {
  const flagged = (assignments ?? []).filter(
    (a) => statusToken(a.status) === "issue",
  );

  if (flagged.length === 0) {
    return <p className="text-sm text-ink-muted">No issues flagged on this driver&apos;s tasks.</p>;
  }

  return (
    <div className="space-y-2.5">
      <p className="inline-flex items-center gap-1.5 text-xs font-semibold text-danger">
        <AlertTriangle className="h-3.5 w-3.5" />
        {flagged.length} task{flagged.length > 1 ? "s" : ""} need attention
      </p>
      {flagged.map((a) => (
        <DriverAssignmentCard key={a.id} assignment={a} />
      ))}
    </div>
  );
}
