"use client";

import { use, useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { CopyButton } from "@/components/ui/CopyButton";
import {
  Package,
  ClipboardList,
  History,
  Sparkles,
  MapPin,
  StickyNote,
  AlertTriangle,
  Loader2,
  Send,
  Truck,
  UserPlus,
  ChevronRight,
} from "lucide-react";
import {
  facilityApi,
  type FacilityOrderDetail,
  type RaiseIssuePayload,
} from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { canManageFacility } from "@/lib/roles";
import { formatDateTime, formatMoney, formatPricingUnit, formatQuantity } from "@/lib/formatters";
import {
  orderStatusLabel,
  orderStatusTone,
  slaLabel,
  slaTone,
  actionLabel,
  taskTypeLabel,
  assignmentStatusLabel,
  assignmentStatusTone,
  statusToken,
} from "@/lib/status";
import { DetailPageShell, DetailColumns } from "@/components/minimal/DetailPageShell";
import { DetailSectionCard, Field, FieldGrid } from "@/components/minimal/DetailSectionCard";
import { StatusBadge } from "@/components/ui/primitives";
import { Button } from "@/components/ui/Button";
import { LoadingState, ErrorState } from "@/components/ui/states";
import { AssignDriverModal } from "@/components/drivers/AssignDriverModal";
import { OrderPhotosSection } from "@/components/orders/OrderPhotosSection";
import { cn } from "@/lib/utils";

/** Fallback next-action when the backend doesn't send available_actions. */
const NEXT_ACTION: Record<string, string> = {
  new: "accept",
  pending: "accept",
  accepted: "mark_received",
  received: "start_cleaning",
  picked_up: "start_cleaning",
  in_cleaning: "move_to_qc",
  cleaning: "move_to_qc",
  qc: "mark_ready",
  quality_check: "mark_ready",
  ready: "confirm_handoff",
  ready_for_delivery: "confirm_handoff",
};

const ISSUE_TYPES = [
  { value: "delay", label: "Report Delay" },
  { value: "damage", label: "Report Damage" },
  { value: "missing", label: "Report Missing Item" },
  { value: "other", label: "Other" },
];

export default function OrderDetailPage({ params }: { params: Promise<{ orderId: string }> }) {
  const { orderId } = use(params);
  const qc = useQueryClient();
  const { role } = useAuth();
  const canManage = canManageFacility(role);
  const [assignOpen, setAssignOpen] = useState(false);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["facility", "order", orderId],
    queryFn: () => facilityApi.order(orderId),
  });

  const [note, setNote] = useState("");
  const [issueOpen, setIssueOpen] = useState(false);
  const [issueType, setIssueType] = useState("delay");
  const [issueMessage, setIssueMessage] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);

  const statusMutation = useMutation({
    mutationFn: (action: string) => facilityApi.updateOrderStatus(orderId, action),
    onSuccess: () => {
      setActionError(null);
      qc.invalidateQueries({ queryKey: ["facility", "order", orderId] });
      qc.invalidateQueries({ queryKey: ["facility", "orders"] });
      qc.invalidateQueries({ queryKey: ["facility", "overview"] });
    },
    onError: (e: unknown) => setActionError(e instanceof Error ? e.message : "Action failed."),
  });

  const noteMutation = useMutation({
    mutationFn: (text: string) => facilityApi.addOrderNote(orderId, text),
    onSuccess: () => {
      setNote("");
      qc.invalidateQueries({ queryKey: ["facility", "order", orderId] });
    },
  });

  const issueMutation = useMutation({
    mutationFn: (payload: RaiseIssuePayload) => facilityApi.raiseOrderIssue(orderId, payload),
    onSuccess: () => {
      setIssueOpen(false);
      setIssueMessage("");
      qc.invalidateQueries({ queryKey: ["facility", "order", orderId] });
      qc.invalidateQueries({ queryKey: ["facility", "issues"] });
    },
  });

  if (isLoading) return <LoadingState label="Loading order…" />;
  if (isError || !data) {
    return <ErrorState description="Could not load this order." onRetry={() => refetch()} />;
  }

  const order: FacilityOrderDetail = data;
  const displayId = order.order_id ?? order.id;
  const service = order.service_display_name ?? order.service ?? "Order";
  const statusKey = statusToken(order.status);
  const actions =
    order.available_actions && order.available_actions.length > 0
      ? order.available_actions
      : statusKey && NEXT_ACTION[statusKey]
        ? [NEXT_ACTION[statusKey]]
        : [];
  const primaryAction = actions[0];
  const secondaryActions = actions.slice(1);

  return (
    <DetailPageShell
      backHref="/orders"
      backLabel="Back to orders"
      eyebrow="Order"
      title={displayId}
      status={
        <>
          <StatusBadge tone={orderStatusTone(order.status)} dot={false}>
            {orderStatusLabel(order.status, order.status_label)}
          </StatusBadge>
          {order.sla_status && (
            <StatusBadge tone={slaTone(order.sla_status)} dot={false}>
              {slaLabel(order.sla_status)}
            </StatusBadge>
          )}
          <CopyButton value={String(displayId)} label="order reference" />
        </>
      }
      actions={
        primaryAction ? (
          <Button
            variant="primary"
            size="lg"
            disabled={statusMutation.isPending}
            onClick={() => statusMutation.mutate(primaryAction)}
          >
            {statusMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            {actionLabel(primaryAction)}
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
            {/* Summary */}
            <DetailSectionCard title="Summary" icon={Package}>
              <FieldGrid>
                <Field label="Service" value={service} />
                <Field label="Items" value={order.item_count != null ? String(order.item_count) : "—"} />
                <Field label="Turnaround" value={order.turnaround ?? "—"} />
                <Field
                  label="Amount"
                  value={order.amount != null ? formatMoney(order.amount, order.currency ?? "AED") : "—"}
                />
              </FieldGrid>
              {order.instructions && (
                <div className="mt-4 rounded-lg border border-border/60 bg-surface-2 px-3.5 py-3">
                  <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Instructions</p>
                  <p className="mt-1 text-sm text-ink">{order.instructions}</p>
                </div>
              )}
            </DetailSectionCard>

            {/* Item breakdown */}
            {order.line_items && order.line_items.length > 0 && (
              <DetailSectionCard title="Items" icon={ClipboardList}>
                <ul className="divide-y divide-border/60">
                  {order.line_items.map((li, i) => {
                    const pricingUnit = formatPricingUnit(li.pricing_unit);
                    return (
                      <li key={i} className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-ink">{li.name ?? "Item"}</p>
                          {li.note && <p className="truncate text-xxs text-ink-muted">{li.note}</p>}
                        </div>
                        <span className="shrink-0 font-mono text-sm text-ink-muted tnum">
                          ×{formatQuantity(li.quantity)}
                          {pricingUnit ? ` · ${pricingUnit}` : ""}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              </DetailSectionCard>
            )}

            {/* Additional order notes — customer instructions captured during the
                WhatsApp booking, grouped by operational section (not raw JSON). */}
            {order.additional_notes && Object.keys(order.additional_notes).length > 0 && (() => {
              const NOTE_LABELS: Record<string, string> = {
                PICKUP_INSTRUCTION: "Pickup Instructions",
                DELIVERY_INSTRUCTION: "Delivery Instructions",
                ACCESS_INSTRUCTION: "Building & Access Instructions",
                CONTACT_PREFERENCE: "Contact Preferences",
                TIMING_PREFERENCE: "Timing Preferences",
                ITEM_HANDLING: "Item Handling",
                STAIN_NOTE: "Stains",
                EXISTING_DAMAGE: "Existing Damage",
                SPECIAL_CARE: "Special Care",
                FACILITY_INSTRUCTION: "Facility Instructions",
                INSPECTION_REQUIREMENT: "Inspection Requirements",
                OTHER_OPERATIONAL_NOTE: "Other Notes",
              };
              return (
                <DetailSectionCard title="Additional Notes" icon={ClipboardList}>
                  <div className="space-y-3.5">
                    {Object.entries(order.additional_notes).map(([cat, texts]) => (
                      <div key={cat}>
                        <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">
                          {NOTE_LABELS[cat] ?? cat}
                        </p>
                        <ul className="mt-1 space-y-1">
                          {texts.map((t, i) => (
                            <li key={i} className="text-sm text-ink">• {t}</li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                </DetailSectionCard>
              );
            })()}

            {/* Order photos — intake + pre-dispatch proof */}
            <OrderPhotosSection orderId={orderId} status={order.status} canManage={canManage} />

            {/* Cleaning details */}
            {order.cleaning_details && Object.keys(order.cleaning_details).length > 0 && (
              <DetailSectionCard title="Cleaning Details" icon={Sparkles}>
                <FieldGrid>
                  {Object.entries(order.cleaning_details).map(([k, v]) => (
                    <Field
                      key={k}
                      label={k.replace(/[_-]+/g, " ")}
                      value={v == null ? "—" : String(v)}
                    />
                  ))}
                </FieldGrid>
              </DetailSectionCard>
            )}

            {/* Timeline */}
            <DetailSectionCard title="Timeline" icon={History}>
              {order.events && order.events.length > 0 ? (
                <ol className="space-y-3">
                  {order.events.map((e, i) => (
                    <li key={e.id ?? i} className="flex gap-3">
                      <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-rose" />
                      <div className="min-w-0">
                        <p className="text-sm text-ink">
                          {e.label ?? orderStatusLabel(e.event_type)}
                        </p>
                        {e.notes && <p className="text-xs text-ink-muted">{e.notes}</p>}
                        <p className="text-xxs text-ink-faint">
                          {formatDateTime(e.created_at)}
                          {e.actor_name ? ` · ${e.actor_name}` : ""}
                        </p>
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="text-sm text-ink-muted">No events recorded yet.</p>
              )}
            </DetailSectionCard>

            {/* Facility notes */}
            <DetailSectionCard title="Facility Notes" icon={StickyNote}>
              {order.notes && order.notes.length > 0 ? (
                <ul className="mb-4 space-y-3">
                  {order.notes.map((n, i) => (
                    <li key={n.id ?? i} className="rounded-lg border border-border/60 bg-surface-2 px-3.5 py-2.5">
                      <p className="text-sm text-ink">{n.note}</p>
                      <p className="mt-1 text-xxs text-ink-faint">
                        {n.author ? `${n.author} · ` : ""}
                        {formatDateTime(n.created_at)}
                      </p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mb-4 text-sm text-ink-muted">No notes yet.</p>
              )}
              <div className="flex flex-col gap-2 sm:flex-row">
                <input
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="Add a note for your team…"
                  className="h-11 flex-1 rounded-lg border border-border bg-canvas px-3 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none"
                />
                <Button
                  variant="secondary"
                  size="lg"
                  disabled={!note.trim() || noteMutation.isPending}
                  onClick={() => noteMutation.mutate(note.trim())}
                >
                  {noteMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                  Add note
                </Button>
              </div>
            </DetailSectionCard>
          </>
        }
        sidebar={
          <>
            {/* Pickup / delivery — area only (privacy firewall) */}
            <DetailSectionCard title="Pickup & Delivery" icon={MapPin}>
              <FieldGrid cols={2}>
                <Field label="Pickup area" value={order.pickup_area ?? "—"} />
                <Field label="Delivery area" value={order.delivery_area ?? "—"} />
              </FieldGrid>
              <p className="mt-3 text-xxs text-ink-faint">
                Exact customer contact and address are handled by LaundryKhalas operations.
              </p>
            </DetailSectionCard>

            {/* Driver assignment */}
            <DetailSectionCard title="Driver" icon={Truck}>
              {order.driver ? (
                <>
                  <Link
                    href={`/drivers/${order.driver.id}`}
                    className="group flex items-center justify-between gap-3 rounded-lg border border-border/60 bg-surface-2 px-3.5 py-3 transition-colors hover:border-border-strong"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-ink">{order.driver.name}</p>
                      {order.driver.masked_phone && (
                        <p className="truncate font-mono text-xxs text-ink-muted">
                          {order.driver.masked_phone}
                        </p>
                      )}
                    </div>
                    <ChevronRight className="h-4 w-4 shrink-0 text-ink-faint transition-colors group-hover:text-rose" />
                  </Link>
                  {order.driver_assignment && (
                    <FieldGrid cols={2}>
                      <Field label="Task" value={taskTypeLabel(order.driver_assignment.task_type)} />
                      <Field
                        label="Status"
                        value={
                          <StatusBadge
                            tone={assignmentStatusTone(order.driver_assignment.status)}
                            dot={false}
                          >
                            {assignmentStatusLabel(order.driver_assignment.status)}
                          </StatusBadge>
                        }
                      />
                      <Field
                        label="Expected"
                        value={
                          order.driver_assignment.expected_completion_at
                            ? formatDateTime(order.driver_assignment.expected_completion_at)
                            : "—"
                        }
                      />
                    </FieldGrid>
                  )}
                  {canManage && (
                    <Button variant="secondary" size="md" className="mt-3" onClick={() => setAssignOpen(true)}>
                      <UserPlus className="h-4 w-4" /> Reassign
                    </Button>
                  )}
                </>
              ) : canManage ? (
                <div className="space-y-3">
                  <p className="text-sm text-ink-muted">No driver assigned to this order yet.</p>
                  <Button variant="primary" size="lg" className="w-full" onClick={() => setAssignOpen(true)}>
                    <UserPlus className="h-4 w-4" /> Assign a driver
                  </Button>
                </div>
              ) : (
                <p className="text-sm text-ink-muted">No driver assigned yet.</p>
              )}
            </DetailSectionCard>

            {/* Status actions */}
            {(primaryAction || secondaryActions.length > 0) && (
              <DetailSectionCard title="Update Status">
                <div className="space-y-2">
                  {actions.map((a) => (
                    <Button
                      key={a}
                      variant={a === primaryAction ? "primary" : "secondary"}
                      size="lg"
                      className="w-full"
                      disabled={statusMutation.isPending}
                      onClick={() => statusMutation.mutate(a)}
                    >
                      {actionLabel(a)}
                    </Button>
                  ))}
                </div>
              </DetailSectionCard>
            )}

            {/* Issue panel */}
            <DetailSectionCard title="Issues" icon={AlertTriangle}>
              {order.issues && order.issues.length > 0 && (
                <ul className="mb-3 space-y-2">
                  {order.issues.map((iss) => (
                    <li key={iss.id} className="rounded-lg border border-border/60 bg-surface-2 px-3 py-2">
                      <p className="text-sm font-medium text-ink">{iss.title ?? iss.issue_type ?? "Issue"}</p>
                      {iss.message && <p className="mt-0.5 text-xxs text-ink-muted">{iss.message}</p>}
                    </li>
                  ))}
                </ul>
              )}

              {issueOpen ? (
                <div className="space-y-2.5">
                  <select
                    value={issueType}
                    onChange={(e) => setIssueType(e.target.value)}
                    className="h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink focus:border-rose focus-visible:outline-none"
                  >
                    {ISSUE_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                  <textarea
                    value={issueMessage}
                    onChange={(e) => setIssueMessage(e.target.value)}
                    rows={3}
                    placeholder="Describe what happened…"
                    className="w-full rounded-lg border border-border bg-canvas px-3 py-2.5 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none"
                  />
                  <div className="flex gap-2">
                    <Button
                      variant="primary"
                      size="md"
                      className="flex-1"
                      disabled={!issueMessage.trim() || issueMutation.isPending}
                      onClick={() =>
                        issueMutation.mutate({ issue_type: issueType, message: issueMessage.trim() })
                      }
                    >
                      {issueMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                      Submit
                    </Button>
                    <Button variant="ghost" size="md" onClick={() => setIssueOpen(false)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <Button
                  variant="danger"
                  size="lg"
                  className={cn("w-full", order.issues && order.issues.length > 0 && "mt-1")}
                  onClick={() => setIssueOpen(true)}
                >
                  <AlertTriangle className="h-4 w-4" /> Report an issue
                </Button>
              )}
            </DetailSectionCard>

            <DetailSectionCard title="Need help?">
              <p className="text-sm text-ink-muted">
                For anything urgent, contact LaundryKhalas operations directly.
              </p>
            </DetailSectionCard>
          </>
        }
      />

      {canManage && (
        <AssignDriverModal open={assignOpen} onClose={() => setAssignOpen(false)} orderId={orderId} />
      )}
    </DetailPageShell>
  );
}
