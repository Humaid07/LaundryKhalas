"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Camera, ImagePlus, Loader2, UploadCloud, X } from "lucide-react";
import { facilityApi, type OrderPhotoStage } from "@/lib/api-client";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

const ACCEPT = "image/jpeg,image/png,image/webp";
const ALLOWED = new Set(["image/jpeg", "image/png", "image/webp"]);
const MAX_BYTES = 5 * 1024 * 1024; // mirrors the backend 5MB ceiling
const MAX_FILES = 10; // mirrors FACILITY_ORDER_PHOTO_MAX_PER_STAGE

interface Picked {
  file: File;
  url: string; // object URL for the preview
}

/**
 * OrderPhotoUploader — a mobile-first upload sheet (bottom sheet on phones,
 * centered dialog on desktop) mirroring AssignDriverModal. Select or drop one or
 * more images, preview + remove before submit, then upload as multipart.
 * Client-side validation mirrors the server (type/size/count) for fast feedback;
 * the server re-validates authoritatively.
 */
export function OrderPhotoUploader({
  open,
  onClose,
  orderId,
  stage,
  stageLabel,
  existingCount,
  onUploaded,
}: {
  open: boolean;
  onClose: () => void;
  orderId: string;
  stage: OrderPhotoStage;
  stageLabel: string;
  existingCount: number;
  onUploaded?: () => void;
}) {
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [picked, setPicked] = useState<Picked[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const remaining = Math.max(0, MAX_FILES - existingCount);

  // Reset + Escape-to-close when opened; revoke preview URLs on teardown.
  useEffect(() => {
    if (!open) return;
    setError(null);
    setDragging(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => {
    // Revoke object URLs whenever the picked set is replaced or on unmount.
    return () => picked.forEach((p) => URL.revokeObjectURL(p.url));
  }, [picked]);

  function addFiles(list: FileList | null) {
    if (!list) return;
    const incoming = Array.from(list);
    const errors: string[] = [];
    const accepted: Picked[] = [];
    for (const file of incoming) {
      if (!ALLOWED.has(file.type)) {
        errors.push(`${file.name}: unsupported type`);
        continue;
      }
      if (file.size > MAX_BYTES) {
        errors.push(`${file.name}: over 5MB`);
        continue;
      }
      accepted.push({ file, url: URL.createObjectURL(file) });
    }
    setPicked((prev) => {
      const room = Math.max(0, remaining - prev.length);
      if (accepted.length > room) {
        errors.push(`Only ${remaining} more photo${remaining === 1 ? "" : "s"} allowed for this stage.`);
      }
      const next = [...prev, ...accepted.slice(0, room)];
      // Revoke any previews we rejected for room.
      accepted.slice(room).forEach((p) => URL.revokeObjectURL(p.url));
      return next;
    });
    setError(errors.length ? errors.join(" · ") : null);
  }

  function removeAt(i: number) {
    setPicked((prev) => {
      const target = prev[i];
      if (target) URL.revokeObjectURL(target.url);
      return prev.filter((_, idx) => idx !== i);
    });
  }

  const upload = useMutation({
    mutationFn: () => facilityApi.uploadOrderPhotos(orderId, stage, picked.map((p) => p.file)),
    onSuccess: () => {
      setError(null);
      setPicked([]);
      qc.invalidateQueries({ queryKey: ["facility", "order-photos", orderId] });
      qc.invalidateQueries({ queryKey: ["facility", "order", orderId] });
      qc.invalidateQueries({ queryKey: ["facility", "orders"] });
      onUploaded?.();
      onClose();
    },
    onError: (e: unknown) => setError(e instanceof Error ? e.message : "Upload failed. Please try again."),
  });

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center sm:items-center">
      <div onClick={onClose} className="absolute inset-0 bg-ink/40 backdrop-blur-sm" />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Upload ${stageLabel.toLowerCase()}`}
        className="relative flex max-h-[90vh] w-full max-w-md flex-col rounded-t-2xl border border-border bg-surface shadow-pop sm:rounded-2xl"
      >
        <header className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-sky/12 text-accent-sky">
              <Camera className="h-4 w-4" />
            </span>
            <h2 className="font-display text-lg font-semibold text-ink">{stageLabel}</h2>
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

        <div className="space-y-4 overflow-y-auto px-5 py-4">
          {/* Drop / tap zone */}
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              addFiles(e.dataTransfer.files);
            }}
            className={cn(
              "flex w-full flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-4 py-8 text-center transition-colors",
              dragging
                ? "border-accent-sky bg-accent-sky/[0.06]"
                : "border-border hover:border-border-strong hover:bg-surface-2",
            )}
          >
            <UploadCloud className="h-7 w-7 text-ink-faint" />
            <span className="text-sm font-medium text-ink">Tap to choose photos</span>
            <span className="text-xxs text-ink-muted">
              or drag &amp; drop · JPG, PNG, WEBP · up to 5MB each
            </span>
          </button>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            multiple
            className="hidden"
            onChange={(e) => {
              addFiles(e.target.files);
              e.target.value = ""; // allow re-selecting the same file
            }}
          />

          {/* Selected previews */}
          {picked.length > 0 && (
            <div className="grid grid-cols-3 gap-2">
              {picked.map((p, i) => (
                <div key={p.url} className="group relative aspect-square overflow-hidden rounded-lg border border-border/70">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={p.url} alt={p.file.name} className="h-full w-full object-cover" />
                  <button
                    type="button"
                    onClick={() => removeAt(i)}
                    aria-label={`Remove ${p.file.name}`}
                    className="absolute right-1 top-1 flex h-6 w-6 items-center justify-center rounded-md bg-ink/60 text-white transition-colors hover:bg-danger"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {error && (
            <p className={cn("rounded-lg border border-danger/30 bg-danger/8 px-3 py-2 text-xs font-medium text-danger")}>
              {error}
            </p>
          )}
          <p className="text-xxs text-ink-faint">
            Photograph the garments/items only — no personal documents. {remaining} more allowed for this stage.
          </p>
        </div>

        <footer className="flex gap-2 border-t border-border px-5 py-4">
          <Button
            variant="primary"
            size="lg"
            className="flex-1"
            disabled={picked.length === 0 || upload.isPending}
            onClick={() => upload.mutate()}
          >
            {upload.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ImagePlus className="h-4 w-4" />}
            Upload {picked.length > 0 ? `${picked.length} photo${picked.length === 1 ? "" : "s"}` : ""}
          </Button>
          <Button variant="ghost" size="lg" onClick={onClose}>
            Cancel
          </Button>
        </footer>
      </div>
    </div>
  );
}
