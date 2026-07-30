"use client";

import { useState } from "react";
import { Camera, ImagePlus } from "lucide-react";
import type { FacilityOrderPhoto, OrderPhotoStage } from "@/lib/api-client";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";
import { OrderPhotoGrid } from "./OrderPhotoGrid";
import { OrderPhotoUploader } from "./OrderPhotoUploader";

/**
 * OrderPhotoStageCard — one stage (Intake or Pre-dispatch): a header with the
 * photo count, a short description, an upload button, and the thumbnail grid (or
 * an empty state). `highlighted` gives the stage that matches the order's current
 * status a subtle Orders-accent ring so staff know which to capture next.
 */
export function OrderPhotoStageCard({
  orderId,
  stage,
  title,
  description,
  buttonLabel,
  photos,
  canManage,
  highlighted,
  onChanged,
}: {
  orderId: string;
  stage: OrderPhotoStage;
  title: string;
  description: string;
  buttonLabel: string;
  photos: FacilityOrderPhoto[];
  canManage: boolean;
  highlighted: boolean;
  onChanged: () => void;
}) {
  const [uploadOpen, setUploadOpen] = useState(false);
  const count = photos.length;

  return (
    <div
      className={cn(
        "rounded-xl border bg-surface-2 p-4",
        highlighted ? "border-accent-sky/40 ring-1 ring-accent-sky/20" : "border-border/60",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Camera className="h-4 w-4 text-accent-sky" />
            <h4 className="text-sm font-semibold text-ink">{title}</h4>
            <span className="rounded-full bg-surface px-1.5 py-0.5 text-xxs font-medium text-ink-muted tnum">
              {count}
            </span>
          </div>
          <p className="mt-1 text-xxs text-ink-muted">{description}</p>
        </div>
      </div>

      <Button
        variant={highlighted ? "primary" : "secondary"}
        size="md"
        className="mt-3 w-full sm:w-auto"
        onClick={() => setUploadOpen(true)}
      >
        <ImagePlus className="h-4 w-4" /> {buttonLabel}
      </Button>

      {count > 0 ? (
        <div className="mt-3">
          <OrderPhotoGrid orderId={orderId} photos={photos} canManage={canManage} onChanged={onChanged} />
        </div>
      ) : (
        <p className="mt-3 rounded-lg border border-dashed border-border/70 bg-surface px-3 py-4 text-center text-xxs text-ink-faint">
          No photos yet for this stage.
        </p>
      )}

      <OrderPhotoUploader
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        orderId={orderId}
        stage={stage}
        stageLabel={buttonLabel}
        existingCount={count}
        onUploaded={onChanged}
      />
    </div>
  );
}
