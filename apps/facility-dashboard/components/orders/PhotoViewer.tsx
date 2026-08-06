"use client";

import { useEffect, useState, useCallback } from "react";
import { createPortal } from "react-dom";
import { ImageOff, Loader2, X, ChevronLeft, ChevronRight } from "lucide-react";
import { facilityApi, type FacilityViewPhoto } from "@/lib/api-client";
import { formatDateTime } from "@/lib/formatters";
import { photoSourceLabel } from "@/lib/note-format";
import { cn } from "@/lib/utils";

/** Fetch a Bearer-guarded photo's bytes into a revocable blob: URL (revoked on
 *  unmount). The content endpoint can't be hit by a bare <img src> because it
 *  needs the auth header, so every thumbnail streams bytes then swaps them in. */
function usePhotoBlob(orderId: string, photoId: string) {
  const [src, setSrc] = useState<string | null>(null);
  const [errored, setErrored] = useState(false);
  useEffect(() => {
    let alive = true;
    let url: string | null = null;
    setSrc(null);
    setErrored(false);
    facilityApi
      .orderPhotoObjectUrl(orderId, photoId)
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
  }, [orderId, photoId]);
  return { src, errored };
}

/** A plain (non-interactive) image that streams a Bearer-guarded photo by id. */
export function PhotoImage({
  orderId,
  photoId,
  className,
  alt = "",
}: {
  orderId: string;
  photoId: string;
  className?: string;
  alt?: string;
}) {
  const { src, errored } = usePhotoBlob(orderId, photoId);
  if (errored) {
    return (
      <span className={cn("flex items-center justify-center bg-surface-2 text-ink-faint", className)}>
        <ImageOff className="h-4 w-4" />
      </span>
    );
  }
  if (!src) {
    return (
      <span className={cn("flex items-center justify-center bg-surface-2 text-ink-faint", className)}>
        <Loader2 className="h-4 w-4 animate-spin" />
      </span>
    );
  }
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={src} alt={alt} className={cn("object-cover", className)} loading="lazy" />;
}

/** A single clickable thumbnail with an optional caption/source overlay. */
export function PhotoThumb({
  orderId,
  photo,
  onOpen,
  className,
}: {
  orderId: string;
  photo: FacilityViewPhoto;
  onOpen?: () => void;
  className?: string;
}) {
  const { src, errored } = usePhotoBlob(orderId, photo.id);
  const alt = photo.caption || `${photoSourceLabel(photo.source)} photo`;
  return (
    <figure className={cn("group relative overflow-hidden rounded-xl border border-border/70 bg-surface-2", className)}>
      <button
        type="button"
        onClick={onOpen}
        aria-label={`Open ${alt}`}
        className="block aspect-square w-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/50"
      >
        {errored ? (
          <span className="flex h-full w-full items-center justify-center text-ink-faint">
            <ImageOff className="h-5 w-5" />
          </span>
        ) : src ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={src} alt={alt} className="h-full w-full object-cover" loading="lazy" />
        ) : (
          <span className="flex h-full w-full items-center justify-center text-ink-faint">
            <Loader2 className="h-5 w-5 animate-spin" />
          </span>
        )}
      </button>
      {(photo.caption || photo.source) && (
        <figcaption className="pointer-events-none absolute inset-x-0 bottom-0 truncate bg-gradient-to-t from-ink/75 to-transparent px-2 py-1 text-[0.6rem] font-medium text-white">
          {photo.caption || photoSourceLabel(photo.source)}
        </figcaption>
      )}
    </figure>
  );
}

/** Full-size lightbox with keyboard navigation, captions and metadata. */
export function PhotoLightbox({
  orderId,
  photos,
  index,
  onClose,
  onIndex,
}: {
  orderId: string;
  photos: FacilityViewPhoto[];
  index: number;
  onClose: () => void;
  onIndex: (i: number) => void;
}) {
  const photo = photos[index];
  const { src, errored } = usePhotoBlob(orderId, photo?.id ?? "");
  const prev = useCallback(() => onIndex((index - 1 + photos.length) % photos.length), [index, photos.length, onIndex]);
  const next = useCallback(() => onIndex((index + 1) % photos.length), [index, photos.length, onIndex]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowLeft") prev();
      else if (e.key === "ArrowRight") next();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, prev, next]);

  if (typeof document === "undefined" || !photo) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex flex-col bg-ink/85 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="Order photo"
      onClick={onClose}
    >
      <div className="flex items-center justify-between px-4 py-3 text-white">
        <span className="text-xs font-medium">
          {index + 1} / {photos.length}
        </span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/10 hover:bg-white/20"
        >
          <X className="h-5 w-5" />
        </button>
      </div>
      <div className="relative flex flex-1 items-center justify-center px-4" onClick={(e) => e.stopPropagation()}>
        {photos.length > 1 && (
          <button
            type="button"
            onClick={prev}
            aria-label="Previous photo"
            className="absolute left-2 flex h-11 w-11 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/20"
          >
            <ChevronLeft className="h-6 w-6" />
          </button>
        )}
        {errored ? (
          <div className="flex flex-col items-center gap-2 text-white/70">
            <ImageOff className="h-8 w-8" /> Could not load image
          </div>
        ) : src ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={src} alt={photo.caption || "Order photo"} className="max-h-[70vh] max-w-full rounded-lg object-contain" />
        ) : (
          <Loader2 className="h-8 w-8 animate-spin text-white/70" />
        )}
        {photos.length > 1 && (
          <button
            type="button"
            onClick={next}
            aria-label="Next photo"
            className="absolute right-2 flex h-11 w-11 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/20"
          >
            <ChevronRight className="h-6 w-6" />
          </button>
        )}
      </div>
      <div className="space-y-1 px-5 py-4 text-white/90" onClick={(e) => e.stopPropagation()}>
        {photo.caption && <p className="text-sm font-medium">{photo.caption}</p>}
        <p className="text-xs text-white/70">
          {photoSourceLabel(photo.source)}
          {photo.item_id ? ` · linked to item` : " · general order photo"}
          {photo.created_at ? ` · ${formatDateTime(photo.created_at)}` : ""}
          {photo.uploaded_by ? ` · ${photo.uploaded_by}` : ""}
        </p>
      </div>
    </div>,
    document.body,
  );
}

/** Small NON-interactive thumbnail (plain <img>) for the order-list card, where
 *  the whole card is a <Link> and nested buttons would be invalid. */
function StripThumb({ orderId, photoId }: { orderId: string; photoId: string }) {
  const { src, errored } = usePhotoBlob(orderId, photoId);
  return (
    <span className="block h-12 w-12 shrink-0 overflow-hidden rounded-lg border border-border/70 bg-surface-2">
      {errored ? (
        <span className="flex h-full w-full items-center justify-center text-ink-faint">
          <ImageOff className="h-4 w-4" />
        </span>
      ) : src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt="" className="h-full w-full object-cover" loading="lazy" />
      ) : (
        <span className="flex h-full w-full items-center justify-center text-ink-faint">
          <Loader2 className="h-4 w-4 animate-spin" />
        </span>
      )}
    </span>
  );
}

/** A compact strip of card thumbnails from photo ids (no interactivity). */
export function CardPhotoStrip({
  orderId,
  photoIds,
  totalCount,
}: {
  orderId: string;
  photoIds: string[];
  totalCount?: number | null;
}) {
  if (!photoIds || photoIds.length === 0) return null;
  const extra = (totalCount ?? photoIds.length) - photoIds.length;
  return (
    <div className="flex items-center gap-1.5">
      {photoIds.map((id) => (
        <StripThumb key={id} orderId={orderId} photoId={id} />
      ))}
      {extra > 0 && (
        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg border border-border/70 bg-surface-2 text-xs font-medium text-ink-muted">
          +{extra}
        </span>
      )}
    </div>
  );
}

/** A responsive gallery of view photos with an integrated lightbox. */
export function PhotoGallery({ orderId, photos }: { orderId: string; photos: FacilityViewPhoto[] }) {
  const [openAt, setOpenAt] = useState<number | null>(null);
  if (photos.length === 0) return null;
  return (
    <>
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
        {photos.map((p, i) => (
          <PhotoThumb key={p.id} orderId={orderId} photo={p} onOpen={() => setOpenAt(i)} />
        ))}
      </div>
      {openAt !== null && (
        <PhotoLightbox orderId={orderId} photos={photos} index={openAt} onClose={() => setOpenAt(null)} onIndex={setOpenAt} />
      )}
    </>
  );
}
