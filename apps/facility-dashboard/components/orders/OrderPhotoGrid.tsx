"use client";

import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ImageOff, Loader2, Trash2 } from "lucide-react";
import { facilityApi, type FacilityOrderPhoto } from "@/lib/api-client";
import { formatDateTime } from "@/lib/formatters";
import { cn } from "@/lib/utils";

/**
 * One thumbnail. The content endpoint is Bearer-guarded, so an <img src> can't
 * hit it directly — we fetch the bytes with the token into a blob: URL and
 * revoke it on unmount. Shows a spinner while loading and a placeholder on error.
 */
function Thumb({
  orderId,
  photo,
  canManage,
  onDelete,
  deleting,
}: {
  orderId: string;
  photo: FacilityOrderPhoto;
  canManage: boolean;
  onDelete: () => void;
  deleting: boolean;
}) {
  const [src, setSrc] = useState<string | null>(null);
  const [errored, setErrored] = useState(false);

  useEffect(() => {
    let alive = true;
    let url: string | null = null;
    facilityApi
      .orderPhotoObjectUrl(orderId, photo.id)
      .then((u) => {
        url = u;
        if (alive) setSrc(u);
        else URL.revokeObjectURL(u);
      })
      .catch(() => alive && setErrored(true));
    return () => {
      alive = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [orderId, photo.id]);

  return (
    <figure className="group relative overflow-hidden rounded-xl border border-border/70 bg-surface-2">
      <div className="aspect-square w-full">
        {errored ? (
          <div className="flex h-full w-full items-center justify-center text-ink-faint">
            <ImageOff className="h-5 w-5" />
          </div>
        ) : src ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={src}
            alt={`${photo.stage} photo`}
            className="h-full w-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-ink-faint">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        )}
      </div>
      {photo.created_at && (
        <figcaption className="pointer-events-none absolute inset-x-0 bottom-0 truncate bg-gradient-to-t from-ink/70 to-transparent px-2 py-1 text-[0.6rem] font-medium text-white">
          {formatDateTime(photo.created_at)}
          {photo.uploaded_by ? ` · ${photo.uploaded_by}` : ""}
        </figcaption>
      )}
      {canManage && (
        <button
          type="button"
          onClick={onDelete}
          disabled={deleting}
          aria-label="Remove photo"
          className="absolute right-1.5 top-1.5 flex h-7 w-7 items-center justify-center rounded-lg bg-ink/50 text-white opacity-0 backdrop-blur-sm transition-opacity hover:bg-danger focus-visible:opacity-100 group-hover:opacity-100 disabled:opacity-100"
        >
          {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
        </button>
      )}
    </figure>
  );
}

/**
 * OrderPhotoGrid — responsive thumbnail grid (2-col mobile, 3-col desktop) with
 * an inline delete for facility owners/managers. No horizontal scroll on mobile.
 */
export function OrderPhotoGrid({
  orderId,
  photos,
  canManage,
  onChanged,
}: {
  orderId: string;
  photos: FacilityOrderPhoto[];
  canManage: boolean;
  onChanged: () => void;
}) {
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);

  const del = useMutation({
    mutationFn: (photoId: string) => facilityApi.deleteOrderPhoto(orderId, photoId),
    onMutate: (photoId: string) => setPendingId(photoId),
    onSuccess: () => {
      setError(null);
      qc.invalidateQueries({ queryKey: ["facility", "order-photos", orderId] });
      qc.invalidateQueries({ queryKey: ["facility", "orders"] });
      onChanged();
    },
    onError: (e: unknown) => setError(e instanceof Error ? e.message : "Could not remove photo."),
    onSettled: () => setPendingId(null),
  });

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {photos.map((p) => (
          <Thumb
            key={p.id}
            orderId={orderId}
            photo={p}
            canManage={canManage}
            deleting={del.isPending && pendingId === p.id}
            onDelete={() => {
              if (window.confirm("Remove this photo? This cannot be undone.")) del.mutate(p.id);
            }}
          />
        ))}
      </div>
      {error && (
        <p className={cn("rounded-lg border border-danger/30 bg-danger/8 px-3 py-2 text-xs font-medium text-danger")}>
          {error}
        </p>
      )}
    </div>
  );
}
