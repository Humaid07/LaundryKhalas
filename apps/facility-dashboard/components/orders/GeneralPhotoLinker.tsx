"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Link2 } from "lucide-react";
import { facilityApi, type FacilityViewPhoto, type FacilityViewItem } from "@/lib/api-client";
import { PhotoImage } from "@/components/orders/PhotoViewer";
import { photoSourceLabel } from "@/lib/note-format";

/**
 * GeneralPhotoLinker — lets an authorized facility user attach an unassigned
 * ("General Order Photos") image to a specific line item. Each photo gets a small
 * thumbnail + an item <select>; choosing an item PATCHes the link and refreshes.
 */
export function GeneralPhotoLinker({
  orderId,
  photos,
  items,
}: {
  orderId: string;
  photos: FacilityViewPhoto[];
  items: FacilityViewItem[];
}) {
  const qc = useQueryClient();
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const link = useMutation({
    mutationFn: ({ photoId, itemId }: { photoId: string; itemId: string }) =>
      facilityApi.linkOrderPhoto(orderId, photoId, itemId),
    onMutate: ({ photoId }) => setPendingId(photoId),
    onSuccess: () => {
      setError(null);
      qc.invalidateQueries({ queryKey: ["facility", "order", orderId] });
    },
    onError: (e: unknown) => setError(e instanceof Error ? e.message : "Could not link the photo."),
    onSettled: () => setPendingId(null),
  });

  if (photos.length === 0 || items.length === 0) return null;

  return (
    <div className="mt-4 rounded-xl border border-border/60 bg-surface-2 p-3">
      <p className="flex items-center gap-1.5 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">
        <Link2 className="h-3.5 w-3.5" /> Link a general photo to an item
      </p>
      <ul className="mt-2.5 space-y-2">
        {photos.map((p) => (
          <li key={p.id} className="flex items-center gap-3">
            <PhotoImage orderId={orderId} photoId={p.id} className="h-11 w-11 shrink-0 rounded-lg border border-border/70" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs text-ink-muted">{p.caption || photoSourceLabel(p.source)}</p>
            </div>
            <div className="flex items-center gap-2">
              {pendingId === p.id && <Loader2 className="h-4 w-4 animate-spin text-ink-faint" />}
              <select
                aria-label={`Assign ${p.caption || "photo"} to an item`}
                defaultValue=""
                disabled={link.isPending}
                onChange={(e) => e.target.value && link.mutate({ photoId: p.id, itemId: e.target.value })}
                className="h-9 rounded-lg border border-border bg-canvas px-2 text-xs text-ink focus:border-rose focus-visible:outline-none"
              >
                <option value="" disabled>
                  Assign to item…
                </option>
                {items.map((it) => (
                  <option key={it.id} value={it.id}>
                    {it.name}
                  </option>
                ))}
              </select>
            </div>
          </li>
        ))}
      </ul>
      {error && <p className="mt-2 text-xxs font-medium text-danger">{error}</p>}
    </div>
  );
}
