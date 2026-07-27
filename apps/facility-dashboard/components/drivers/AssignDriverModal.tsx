"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, X, Truck } from "lucide-react";
import {
  facilityApi,
  type FacilityDriver,
  type AssignmentResult,
} from "@/lib/api-client";
import { driverStatusLabel } from "@/lib/status";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

const TASK_OPTIONS = [
  { value: "pickup", label: "Pickup" },
  { value: "facility_handoff", label: "Facility Handoff" },
  { value: "delivery", label: "Delivery" },
  { value: "return", label: "Return" },
];

/**
 * AssignDriverModal — assigns work in one of two modes:
 *  • `orderId` set  → pick a driver for this order (POST /orders/{id}/assign-driver).
 *  • `driver` set   → attach an order to this driver (POST /driver-assignments).
 * Manage-role only; the caller gates rendering. Never surfaces customer PII.
 */
export function AssignDriverModal({
  open,
  onClose,
  orderId,
  driver,
  onAssigned,
}: {
  open: boolean;
  onClose: () => void;
  orderId?: string;
  driver?: FacilityDriver;
  onAssigned?: (result: AssignmentResult) => void;
}) {
  const qc = useQueryClient();
  const [driverId, setDriverId] = useState("");
  const [orderRef, setOrderRef] = useState("");
  const [taskType, setTaskType] = useState("pickup");
  const [expected, setExpected] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Driver list — only needed when assigning to a known order.
  const driversQuery = useQuery({
    queryKey: ["facility", "drivers"],
    queryFn: () => facilityApi.drivers(),
    enabled: open && !!orderId,
  });

  useEffect(() => {
    if (!open) return;
    setDriverId("");
    setOrderRef("");
    setTaskType("pickup");
    setExpected("");
    setNotes("");
    setError(null);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const mutation = useMutation({
    mutationFn: (): Promise<AssignmentResult> => {
      const expectedIso = expected ? new Date(expected).toISOString() : undefined;
      if (orderId) {
        return facilityApi.assignDriverToOrder(orderId, {
          driver_id: driverId,
          task_type: taskType,
          expected_completion_at: expectedIso,
          notes: notes.trim() || undefined,
        });
      }
      return facilityApi.createDriverAssignment({
        driver_id: driver!.id,
        order_id: orderRef.trim(),
        task_type: taskType,
        expected_completion_at: expectedIso,
        notes: notes.trim() || undefined,
      });
    },
    onSuccess: (result) => {
      setError(null);
      qc.invalidateQueries({ queryKey: ["facility", "drivers"] });
      qc.invalidateQueries({ queryKey: ["facility", "driver"] });
      if (orderId) qc.invalidateQueries({ queryKey: ["facility", "order", orderId] });
      onAssigned?.(result);
      onClose();
    },
    onError: (e: unknown) => setError(e instanceof Error ? e.message : "Could not assign."),
  });

  if (!open) return null;

  const drivers = driversQuery.data?.drivers ?? [];
  const canSubmit = orderId ? driverId !== "" : orderRef.trim() !== "";

  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center sm:items-center">
      <div onClick={onClose} className="absolute inset-0 bg-ink/40 backdrop-blur-sm" />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Assign driver"
        className="relative flex w-full max-w-md flex-col rounded-t-2xl border border-border bg-surface shadow-pop sm:rounded-2xl"
      >
        <header className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-rose/12 text-rose">
              <Truck className="h-4 w-4" />
            </span>
            <h2 className="font-display text-lg font-semibold text-ink">
              {orderId ? "Assign a driver" : "Assign an order"}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="flex h-9 w-9 items-center justify-center rounded-lg text-ink-muted transition-colors hover:bg-surface-2 hover:text-ink"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="space-y-4 px-5 py-4">
          {driver && !orderId && (
            <p className="text-sm text-ink-muted">
              Assigning to <span className="font-medium text-ink">{driver.name}</span>.
            </p>
          )}

          {orderId ? (
            <label className="block">
              <span className="mb-1.5 block text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">
                Driver
              </span>
              <select
                value={driverId}
                onChange={(e) => setDriverId(e.target.value)}
                disabled={driversQuery.isLoading}
                className="h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink focus:border-rose focus-visible:outline-none"
              >
                <option value="">
                  {driversQuery.isLoading ? "Loading drivers…" : "Select a driver"}
                </option>
                {drivers.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} · {driverStatusLabel(d.effective_status ?? d.status)}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <label className="block">
              <span className="mb-1.5 block text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">
                Order reference
              </span>
              <input
                value={orderRef}
                onChange={(e) => setOrderRef(e.target.value)}
                placeholder="Order ID or reference"
                className="h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none"
              />
            </label>
          )}

          <label className="block">
            <span className="mb-1.5 block text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">
              Task type
            </span>
            <select
              value={taskType}
              onChange={(e) => setTaskType(e.target.value)}
              className="h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink focus:border-rose focus-visible:outline-none"
            >
              {TASK_OPTIONS.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="mb-1.5 block text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">
              Expected completion (optional)
            </span>
            <input
              type="datetime-local"
              value={expected}
              onChange={(e) => setExpected(e.target.value)}
              className="h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink focus:border-rose focus-visible:outline-none"
            />
          </label>

          <label className="block">
            <span className="mb-1.5 block text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">
              Notes (optional)
            </span>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="Anything the driver should know…"
              className="w-full rounded-lg border border-border bg-canvas px-3 py-2.5 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none"
            />
          </label>

          {error && (
            <p className={cn("rounded-lg border border-danger/30 bg-danger/8 px-3 py-2 text-xs font-medium text-danger")}>
              {error}
            </p>
          )}
        </div>

        <footer className="flex gap-2 border-t border-border px-5 py-4">
          <Button
            variant="primary"
            size="lg"
            className="flex-1"
            disabled={!canSubmit || mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            Assign
          </Button>
          <Button variant="ghost" size="lg" onClick={onClose}>
            Cancel
          </Button>
        </footer>
      </div>
    </div>
  );
}
