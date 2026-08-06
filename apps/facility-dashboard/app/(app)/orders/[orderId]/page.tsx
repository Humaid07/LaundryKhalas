"use client";

import { use, useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Package,
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
  ListChecks,
  Camera,
  Clock,
} from "lucide-react";
import {
  facilityApi,
  type FacilityOrderDetail,
  type FacilityOrderView,
} from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { canManageFacility } from "@/lib/roles";
import { formatDateTime, formatRelativeTime } from "@/lib/formatters";
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
import { PhotoGallery } from "@/components/orders/PhotoViewer";
import { GeneralPhotoLinker } from "@/components/orders/GeneralPhotoLinker";
import { RaiseIssueForm } from "@/components/orders/RaiseIssueForm";
import { QuoteRevisionPanel } from "@/components/orders/QuoteRevisionPanel";
import {
  RequiredWorkList,
  CriticalNotesBanner,
  ImportantNotes,
  ReviewAckBanner,
  FacilityFeeBlock,
  ItemsBreakdown,
} from "@/components/orders/OrderViewSections";

/** Fallback next-action when the backend doesn't send a structured view. */
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
  const [actionError, setActionError] = useState<string | null>(null);

  const invalidateOrder = () => {
    qc.invalidateQueries({ queryKey: ["facility", "order", orderId] });
    qc.invalidateQueries({ queryKey: ["facility", "orders"] });
    qc.invalidateQueries({ queryKey: ["facility", "overview"] });
  };

  const statusMutation = useMutation({
    mutationFn: (action: string) => facilityApi.updateOrderStatus(orderId, action),
    onSuccess: () => {
      setActionError(null);
      invalidateOrder();
    },
    onError: (e: unknown) => setActionError(e instanceof Error ? e.message : "Action failed."),
  });

  const ackMutation = useMutation({
    mutationFn: () => facilityApi.acknowledgeReview(orderId),
    onSuccess: () => {
      setActionError(null);
      invalidateOrder();
    },
    onError: (e: unknown) => setActionError(e instanceof Error ? e.message : "Could not record your review."),
  });

  const noteMutation = useMutation({
    mutationFn: (text: string) => facilityApi.addOrderNote(orderId, text),
    onSuccess: () => {
      setNote("");
      qc.invalidateQueries({ queryKey: ["facility", "order", orderId] });
    },
  });

  if (isLoading) return <LoadingState label="Loading order…" />;
  if (isError || !data) {
    return <ErrorState description="Could not load this order." onRetry={() => refetch()} />;
  }

  const order: FacilityOrderDetail = data;
  const view: FacilityOrderView | null = order.view ?? null;
  const displayId = order.order_id ?? order.id;
  const service = view?.order.service_summary ?? order.service_display_name ?? order.service ?? "Order";
  const statusKey = statusToken(order.status);

  // Structured actions from the view (backend-validated); fall back to the old map.
  const viewActions = view?.available_actions ?? [];
  const fallbackActions =
    viewActions.length === 0 && statusKey && NEXT_ACTION[statusKey] ? [NEXT_ACTION[statusKey]] : [];
  const primary = view?.next_action ?? (viewActions.find((a) => a.primary && a.enabled) ?? null);
  const ack = view?.review_acknowledgement;

  const runAction = (action: string) => {
    if (action === "acknowledge_review") ackMutation.mutate();
    else if (action === "raise_issue") setIssueOpen(true);
    else statusMutation.mutate(action);
  };
  const anyActionPending = statusMutation.isPending || ackMutation.isPending;

  return (
    <DetailPageShell
      backHref="/orders"
      backLabel="Back to orders"
      eyebrow="Order"
      title={displayId}
      status={
        <>
          {view?.order.priority === "EXPRESS" && <StatusBadge tone="warning" dot={false}>Express</StatusBadge>}
          <StatusBadge tone={orderStatusTone(order.status)} dot={false}>
            {orderStatusLabel(order.status, order.status_label)}
          </StatusBadge>
          {order.sla_status && (
            <StatusBadge tone={slaTone(order.sla_status)} dot={false}>
              {slaLabel(order.sla_status)}
            </StatusBadge>
          )}
        </>
      }
      actions={
        primary ? (
          <Button
            variant="primary"
            size="lg"
            disabled={anyActionPending || primary.enabled === false}
            onClick={() => runAction(primary.action)}
          >
            {anyActionPending && <Loader2 className="h-4 w-4 animate-spin" />}
            {primary.label ?? actionLabel(primary.action)}
          </Button>
        ) : fallbackActions[0] ? (
          <Button variant="primary" size="lg" disabled={statusMutation.isPending} onClick={() => runAction(fallbackActions[0])}>
            {statusMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            {actionLabel(fallbackActions[0])}
          </Button>
        ) : undefined
      }
    >
      {actionError && (
        <p className="rounded-lg border border-danger/30 bg-danger/8 px-3 py-2 text-xs font-medium text-danger">
          {actionError}
        </p>
      )}

      {/* Review acknowledgement — gates Start Processing */}
      {ack && (
        <ReviewAckBanner ack={ack} onAcknowledge={() => ackMutation.mutate()} pending={ackMutation.isPending} />
      )}

      {/* Critical notes — full width, above the columns */}
      {view && view.critical_notes.length > 0 && <CriticalNotesBanner notes={view.critical_notes} />}

      <DetailColumns
        main={
          <>
            {/* 1 — Required Work (first operational section) */}
            <DetailSectionCard title="Required Work" icon={ListChecks}>
              <RequiredWorkList items={view?.order.required_work_summary ?? order.required_work_summary ?? []} />
              {order.instructions && (
                <div className="mt-4 rounded-lg border border-border/60 bg-surface-2 px-3.5 py-3">
                  <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Customer instruction</p>
                  <p className="mt-1 text-sm text-ink">{order.instructions}</p>
                </div>
              )}
            </DetailSectionCard>

            {/* 2 — Important Notes (grouped, prioritised) */}
            {view ? (
              <ImportantNotes notes={view.notes} />
            ) : (
              order.additional_notes && Object.keys(order.additional_notes).length > 0 && (
                <DetailSectionCard title="Important Notes" icon={StickyNote}>
                  <div className="space-y-3.5">
                    {Object.entries(order.additional_notes).map(([cat, texts]) => (
                      <div key={cat}>
                        <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">{cat}</p>
                        <ul className="mt-1 space-y-1">
                          {texts.map((t, i) => (
                            <li key={i} className="text-sm text-ink">• {t}</li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                </DetailSectionCard>
              )
            )}

            {/* 3 — Photos: customer/general view photos + facility proof uploader */}
            {view && view.photos.count > 0 && (
              <DetailSectionCard title="Photos" icon={Camera}>
                {view.photos.general.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">General order photos</p>
                    <PhotoGallery orderId={orderId} photos={view.photos.general} />
                    {canManage && view.items.length > 0 && (
                      <GeneralPhotoLinker orderId={orderId} photos={view.photos.general} items={view.items} />
                    )}
                  </div>
                )}
                {Object.entries(view.photos.by_item).map(([itemId, photos]) => (
                  <div key={itemId} className="mt-4 space-y-2">
                    <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">
                      {view.items.find((it) => it.id === itemId)?.name ?? "Item"} photos
                    </p>
                    <PhotoGallery orderId={orderId} photos={photos} />
                  </div>
                ))}
              </DetailSectionCard>
            )}
            <OrderPhotosSection orderId={orderId} status={order.status} canManage={canManage} />

            {/* 4 — Items & quantities */}
            {view && view.items.length > 0 && <ItemsBreakdown items={view.items} />}

            {/* Cleaning details */}
            {order.cleaning_details && Object.keys(order.cleaning_details).length > 0 && (
              <DetailSectionCard title="Cleaning Details" icon={Sparkles}>
                <FieldGrid>
                  {Object.entries(order.cleaning_details).map(([k, v]) => (
                    <Field key={k} label={k.replace(/[_-]+/g, " ")} value={v == null ? "—" : String(v)} />
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
                        <p className="text-sm text-ink">{e.label ?? orderStatusLabel(e.event_type)}</p>
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

            {/* Facility team notes */}
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
            {/* Order summary */}
            <DetailSectionCard title="Order" icon={Package}>
              <FieldGrid cols={2}>
                <Field label="Service" value={service} />
                <Field label="Items" value={view?.order.item_count ?? order.item_count ?? "—"} />
                <Field label="Turnaround" value={view?.order.turnaround_text ?? order.turnaround ?? "—"} />
                <Field
                  label="Due"
                  value={
                    view?.order.expected_completion_at || order.expected_completion_at ? (
                      <span className="inline-flex items-center gap-1">
                        <Clock className="h-3.5 w-3.5 text-ink-faint" />
                        {formatRelativeTime((view?.order.expected_completion_at ?? order.expected_completion_at) as string)}
                      </span>
                    ) : (
                      view?.order.expected_completion_text ?? "—"
                    )
                  }
                />
              </FieldGrid>
              {view?.order.pickup_window?.label && (
                <p className="mt-3 text-xxs text-ink-faint">
                  Pickup: {view.order.pickup_window.date ? `${view.order.pickup_window.date} · ` : ""}
                  {view.order.pickup_window.label}
                </p>
              )}
            </DetailSectionCard>

            {/* Facility fee */}
            {view && <FacilityFeeBlock finance={view.facility_finance} />}

            {/* Revised quote — submit + track */}
            {view && (view.quote_revisions.length > 0 || order.status !== "completed") && (
              <QuoteRevisionPanel orderId={orderId} revisions={view.quote_revisions} items={view.items} />
            )}

            {/* Pickup / delivery — area only (privacy firewall) */}
            <DetailSectionCard title="Pickup & Delivery" icon={MapPin}>
              <FieldGrid cols={2}>
                <Field
                  label="Pickup area"
                  value={view?.location.area ?? view?.location.typed_address?.pickup_area ?? order.pickup_area ?? "—"}
                />
                <Field label="Delivery area" value={order.delivery_area ?? "—"} />
              </FieldGrid>
              <p className="mt-3 text-xxs text-ink-faint">
                Exact customer contact and address are handled by LaundryKhalas operations.
              </p>
            </DetailSectionCard>

            {/* Driver */}
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
                        <p className="truncate font-mono text-xxs text-ink-muted">{order.driver.masked_phone}</p>
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
                          <StatusBadge tone={assignmentStatusTone(order.driver_assignment.status)} dot={false}>
                            {assignmentStatusLabel(order.driver_assignment.status)}
                          </StatusBadge>
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

            {/* Actions */}
            {(viewActions.length > 0 || fallbackActions.length > 0) && (
              <DetailSectionCard title="Actions">
                <div className="space-y-2">
                  {viewActions.length > 0
                    ? viewActions.map((a) => (
                        <div key={a.action}>
                          <Button
                            variant={a.primary ? "primary" : "secondary"}
                            size="lg"
                            className="w-full"
                            disabled={!a.enabled || anyActionPending}
                            onClick={() => runAction(a.action)}
                          >
                            {a.label}
                          </Button>
                          {!a.enabled && a.reason && (
                            <p className="mt-1 text-xxs text-ink-faint">{a.reason}</p>
                          )}
                        </div>
                      ))
                    : fallbackActions.map((a) => (
                        <Button
                          key={a}
                          variant="primary"
                          size="lg"
                          className="w-full"
                          disabled={statusMutation.isPending}
                          onClick={() => runAction(a)}
                        >
                          {actionLabel(a)}
                        </Button>
                      ))}
                </div>
              </DetailSectionCard>
            )}

            {/* Issues */}
            <DetailSectionCard title="Issues" icon={AlertTriangle}>
              {view && view.issues.length > 0 && (
                <ul className="mb-3 space-y-2">
                  {view.issues.map((iss) => (
                    <li key={iss.id} className="rounded-lg border border-border/60 bg-surface-2 px-3 py-2">
                      <p className="text-sm font-medium text-ink">{iss.title ?? iss.issue_type ?? "Issue"}</p>
                      {iss.message && <p className="mt-0.5 text-xxs text-ink-muted">{iss.message}</p>}
                    </li>
                  ))}
                </ul>
              )}

              {issueOpen ? (
                <RaiseIssueForm
                  orderId={orderId}
                  items={view?.items ?? []}
                  onCancel={() => setIssueOpen(false)}
                  onDone={() => setIssueOpen(false)}
                />
              ) : (
                <Button variant="danger" size="lg" className="w-full" onClick={() => setIssueOpen(true)}>
                  <AlertTriangle className="h-4 w-4" /> Report an issue
                </Button>
              )}
            </DetailSectionCard>

            <DetailSectionCard title="Need help?">
              <p className="text-sm text-ink-muted">For anything urgent, contact LaundryKhalas operations directly.</p>
            </DetailSectionCard>
          </>
        }
      />

      {canManage && <AssignDriverModal open={assignOpen} onClose={() => setAssignOpen(false)} orderId={orderId} />}
    </DetailPageShell>
  );
}
