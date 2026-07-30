"use client";

import { useQuery } from "@tanstack/react-query";
import { Camera, Loader2 } from "lucide-react";
import { facilityApi, type FacilityOrderPhoto } from "@/lib/api-client";
import { DetailSectionCard } from "@/components/minimal/DetailSectionCard";
import { OrderPhotoStageCard } from "./OrderPhotoStageCard";

/**
 * OrderPhotosSection — the "Order Photos" block on the order detail page.
 *
 * Two always-accessible stage cards (Intake, Pre-dispatch). Whichever stage
 * matches the order's current status gets a subtle highlight so staff know which
 * to capture next, but both can always be uploaded to. Self-contained: it owns
 * the photos query; child upload/delete mutations invalidate its key.
 *
 * The wrapping div carries id="order-photos" so links can deep-scroll here.
 */
const INTAKE_STATUSES = new Set(["active", "pickup_scheduled", "picked_up", "in_cleaning"]);
const DISPATCH_STATUSES = new Set([
  "in_cleaning",
  "ready_for_delivery",
  "out_for_delivery",
]);

export function OrderPhotosSection({
  orderId,
  status,
  canManage,
}: {
  orderId: string;
  status?: string | null;
  canManage: boolean;
}) {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["facility", "order-photos", orderId],
    queryFn: () => facilityApi.orderPhotos(orderId),
  });

  const photos: FacilityOrderPhoto[] = data?.photos ?? [];
  const intake = photos.filter((p) => p.stage === "intake");
  const preDispatch = photos.filter((p) => p.stage === "pre_dispatch");

  const s = (status ?? "").toLowerCase();
  // Highlight intake while items are moving in/through the facility; switch the
  // emphasis to pre-dispatch once the order is ready for handoff.
  const highlightDispatch = DISPATCH_STATUSES.has(s) && !INTAKE_STATUSES.has(s)
    ? true
    : s === "ready_for_delivery" || s === "out_for_delivery";
  const highlightIntake = !highlightDispatch;

  return (
    <div id="order-photos" className="scroll-mt-24">
      <DetailSectionCard title="Order Photos" icon={Camera}>
        <p className="mb-4 text-xxs text-ink-muted">
          Photo proof for quality control, dispute handling and damage tracking. Capture the garments/items
          only — never personal documents.
        </p>

        {isLoading ? (
          <div className="flex items-center justify-center py-8 text-ink-faint">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        ) : (
          <div className="space-y-3">
            <OrderPhotoStageCard
              orderId={orderId}
              stage="intake"
              title="Intake Photos"
              description="Add photos when items are received at the facility."
              buttonLabel="Upload intake photos"
              photos={intake}
              canManage={canManage}
              highlighted={highlightIntake}
              onChanged={() => refetch()}
            />
            <OrderPhotoStageCard
              orderId={orderId}
              stage="pre_dispatch"
              title="Pre-dispatch Photos"
              description="Add photos before handoff/dispatch."
              buttonLabel="Upload pre-dispatch photos"
              photos={preDispatch}
              canManage={canManage}
              highlighted={highlightDispatch}
              onChanged={() => refetch()}
            />
          </div>
        )}
      </DetailSectionCard>
    </div>
  );
}
