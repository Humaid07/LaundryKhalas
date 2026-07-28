"use client";

import { use, useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Loader2,
  Truck,
  ClipboardList,
  History,
  AlertTriangle,
  CircleCheck,
  Coffee,
  UserPlus,
  Ban,
} from "lucide-react";
import {
  facilityApi,
  type DriverAssignment,
  type SetDriverStatusPayload,
} from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { canManageFacility } from "@/lib/roles";
import { statusToken } from "@/lib/status";
import { DetailPageShell, DetailColumns } from "@/components/minimal/DetailPageShell";
import { DetailSectionCard } from "@/components/minimal/DetailSectionCard";
import { StatusBadge } from "@/components/ui/primitives";
import { Button } from "@/components/ui/Button";
import { LoadingState, ErrorState } from "@/components/ui/states";
import { DriverStatusBadge } from "@/components/drivers/DriverStatusBadge";
import { DriverDetailHeader } from "@/components/drivers/DriverDetailHeader";
import { DriverAssignmentCard } from "@/components/drivers/DriverAssignmentCard";
import { DriverTaskList } from "@/components/drivers/DriverTaskList";
import { DriverIssuePanel } from "@/components/drivers/DriverIssuePanel";
import { AssignDriverModal } from "@/components/drivers/AssignDriverModal";

const ACTIVE_STATUSES = new Set(["assigned", "in_progress"]);

export default function DriverDetailPage({ params }: { params: Promise<{ driverId: string }> }) {
  const { driverId } = use(params);
  const qc = useQueryClient();
  const { role } = useAuth();
  const canManage = canManageFacility(role);

  const [assignOpen, setAssignOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["facility", "driver", driverId],
    queryFn: () => facilityApi.driver(driverId),
  });

  const statusMutation = useMutation({
    mutationFn: (payload: SetDriverStatusPayload) => facilityApi.setDriverStatus(driverId, payload),
    onSuccess: () => {
      setActionError(null);
      qc.invalidateQueries({ queryKey: ["facility", "driver", driverId] });
      qc.invalidateQueries({ queryKey: ["facility", "drivers"] });
    },
    onError: (e: unknown) => setActionError(e instanceof Error ? e.message : "Action failed."),
  });

  const unassignMutation = useMutation({
    mutationFn: (assignmentId: string) =>
      facilityApi.updateAssignmentStatus(assignmentId, { status: "cancelled" }),
    onSuccess: () => {
      setActionError(null);
      qc.invalidateQueries({ queryKey: ["facility", "driver", driverId] });
      qc.invalidateQueries({ queryKey: ["facility", "drivers"] });
    },
    onError: (e: unknown) => setActionError(e instanceof Error ? e.message : "Action failed."),
  });

  const assignments: DriverAssignment[] = useMemo(() => data?.assignments ?? [], [data]);

  const currentAssignment = useMemo(
    () =>
      data?.current_assignment ??
      assignments.find((a) => ACTIVE_STATUSES.has(statusToken(a.status))) ??
      null,
    [data, assignments],
  );

  if (isLoading) return <LoadingState label="Loading driver…" />;
  if (isError || !data) {
    return <ErrorState description="Could not load this driver." onRetry={() => refetch()} />;
  }

  const busy = statusMutation.isPending || unassignMutation.isPending;

  return (
    <DetailPageShell
      backHref="/drivers"
      backLabel="Back to drivers"
      eyebrow="Driver"
      title={data.name}
      status={
        <>
          <DriverStatusBadge driver={data} />
          <StatusBadge tone={data.active === false ? "neutral" : "success"} dot={false}>
            {data.active === false ? "Offline" : "Active"}
          </StatusBadge>
        </>
      }
      actions={
        canManage ? (
          <Button variant="primary" size="lg" onClick={() => setAssignOpen(true)}>
            <UserPlus className="h-4 w-4" /> Assign
          </Button>
        ) : undefined
      }
    >
      {actionError && (
        <p className="rounded-lg border border-danger/30 bg-danger/8 px-3 py-2 text-xs font-medium text-danger">
          {actionError}
        </p>
      )}

      <DetailColumns
        main={
          <>
            <DriverDetailHeader driver={data} />

            {/* Current assignment */}
            <DetailSectionCard title="Current Assignment" icon={Truck}>
              {currentAssignment ? (
                <DriverAssignmentCard assignment={currentAssignment} />
              ) : (
                <p className="text-sm text-ink-muted">This driver has no active assignment.</p>
              )}
              {canManage && currentAssignment && (
                <Button
                  variant="danger"
                  size="md"
                  className="mt-3"
                  disabled={busy}
                  onClick={() => unassignMutation.mutate(currentAssignment.id)}
                >
                  <Ban className="h-4 w-4" /> Unassign
                </Button>
              )}
            </DetailSectionCard>

            {/* Recent assignments */}
            <DetailSectionCard title="Recent Assignments" icon={History}>
              <DriverTaskList assignments={assignments} emptyLabel="No assignments recorded yet." />
            </DetailSectionCard>
          </>
        }
        sidebar={
          <>
            {/* Issues */}
            <DetailSectionCard title="Issues" icon={AlertTriangle}>
              <DriverIssuePanel assignments={assignments} />
            </DetailSectionCard>

            {/* Actions */}
            {canManage && (
              <DetailSectionCard title="Actions" icon={ClipboardList}>
                <div className="space-y-2">
                  <Button
                    variant="secondary"
                    size="lg"
                    className="w-full"
                    disabled={busy}
                    onClick={() => statusMutation.mutate({ status: "free" })}
                  >
                    <CircleCheck className="h-4 w-4" /> Mark available
                  </Button>
                  <Button
                    variant="secondary"
                    size="lg"
                    className="w-full"
                    disabled={busy}
                    onClick={() => statusMutation.mutate({ status: "on_break" })}
                  >
                    <Coffee className="h-4 w-4" /> Set on break
                  </Button>
                  <Button
                    variant="primary"
                    size="lg"
                    className="w-full"
                    disabled={busy}
                    onClick={() => setAssignOpen(true)}
                  >
                    <UserPlus className="h-4 w-4" /> Assign order
                  </Button>
                  <Button
                    variant="danger"
                    size="lg"
                    className="w-full"
                    disabled={busy}
                    onClick={() => statusMutation.mutate({ status: "issue" })}
                  >
                    <AlertTriangle className="h-4 w-4" /> Report issue
                  </Button>
                </div>
              </DetailSectionCard>
            )}

            <DetailSectionCard title="Privacy">
              <p className="text-sm text-ink-muted">
                Driver views never include customer phone numbers or full addresses — only the
                area needed to run the job.
              </p>
            </DetailSectionCard>
          </>
        }
      />

      {canManage && (
        <AssignDriverModal
          open={assignOpen}
          onClose={() => setAssignOpen(false)}
          driver={data}
        />
      )}
    </DetailPageShell>
  );
}
