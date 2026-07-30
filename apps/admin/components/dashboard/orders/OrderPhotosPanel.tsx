"use client";

import { useEffect, useState } from "react";
import { Camera, ImageOff } from "lucide-react";
import { Panel, PanelHeader } from "@/components/dashboard/ui/primitives";
import { Skeleton } from "@/components/dashboard/ui/states";
import {
  agentApi,
  type OrderPhotoDTO,
  type OrderPhotosResponseDTO,
} from "@/lib/dashboard/whatsapp-agent-api";
import { cn } from "@/lib/utils";

/**
 * OrderPhotosPanel — READ-ONLY internal (ops/admin) view of an order's facility
 * proof photos (intake + pre-dispatch). Ops can view any facility's order photos;
 * uploading/deleting stays on the facility side. Bytes are Bearer-guarded, so each
 * thumbnail fetches its own blob: URL (an <img src> can't send the token) and
 * revokes it on unmount. Degrades to a quiet empty state (safe for orders with no
 * photos and when the backend is briefly unavailable).
 */
const STAGE_LABEL: Record<string, string> = {
  intake: "Intake · received at facility",
  pre_dispatch: "Pre-dispatch · before handoff",
};

function fmt(v?: string | null): string {
  if (!v) return "";
  const d = new Date(v);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleString("en-GB", { timeZone: "Asia/Dubai", dateStyle: "medium", timeStyle: "short" });
}

function Thumb({ orderId, photo }: { orderId: string; photo: OrderPhotoDTO }) {
  const [src, setSrc] = useState<string | null>(null);
  const [errored, setErrored] = useState(false);

  useEffect(() => {
    let alive = true;
    let url: string | null = null;
    agentApi
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
    <figure className="relative overflow-hidden rounded-lg border border-border/70 bg-surface-2">
      <div className="aspect-square w-full">
        {errored ? (
          <div className="flex h-full w-full items-center justify-center text-ink-faint">
            <ImageOff className="h-4 w-4" />
          </div>
        ) : src ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={src} alt={`${photo.stage} photo`} className="h-full w-full object-cover" loading="lazy" />
        ) : (
          <Skeleton className="h-full w-full" />
        )}
      </div>
      {photo.created_at && (
        <figcaption className="pointer-events-none absolute inset-x-0 bottom-0 truncate bg-gradient-to-t from-ink/70 to-transparent px-1.5 py-1 text-[0.6rem] font-medium text-white">
          {fmt(photo.created_at)}
          {photo.uploaded_by ? ` · ${photo.uploaded_by}` : ""}
        </figcaption>
      )}
    </figure>
  );
}

function StageBlock({ orderId, stage, photos }: { orderId: string; stage: string; photos: OrderPhotoDTO[] }) {
  if (photos.length === 0) return null;
  return (
    <div>
      <p className="mb-1.5 text-xxs font-semibold uppercase tracking-wide text-ink-faint">
        {STAGE_LABEL[stage] ?? stage} · {photos.length}
      </p>
      <div className="grid grid-cols-3 gap-2">
        {photos.map((p) => (
          <Thumb key={p.id} orderId={orderId} photo={p} />
        ))}
      </div>
    </div>
  );
}

export function OrderPhotosPanel({ orderId, className }: { orderId: string; className?: string }) {
  const [data, setData] = useState<OrderPhotosResponseDTO | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    agentApi
      .getOrderPhotos(orderId)
      .then((res) => alive && setData(res))
      .catch(() => alive && setData({ photos: [], counts: { intake: 0, pre_dispatch: 0 } }))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [orderId]);

  const photos = data?.photos ?? [];
  const total = photos.length;
  const intake = photos.filter((p) => p.stage === "intake");
  const preDispatch = photos.filter((p) => p.stage === "pre_dispatch");

  return (
    <Panel padded className={cn("!rounded-xl", className)}>
      <PanelHeader
        title="Order photos"
        subtitle={loading ? "Loading…" : `${total} photo${total === 1 ? "" : "s"} · read-only`}
      />
      {loading ? (
        <div className="grid grid-cols-3 gap-2">
          <Skeleton className="aspect-square rounded-lg" />
          <Skeleton className="aspect-square rounded-lg" />
          <Skeleton className="aspect-square rounded-lg" />
        </div>
      ) : total === 0 ? (
        <p className="flex items-center gap-1.5 text-xs text-ink-muted">
          <Camera className="h-3.5 w-3.5 text-ink-faint" />
          No photos uploaded for this order yet.
        </p>
      ) : (
        <div className="space-y-3">
          <StageBlock orderId={orderId} stage="intake" photos={intake} />
          <StageBlock orderId={orderId} stage="pre_dispatch" photos={preDispatch} />
        </div>
      )}
    </Panel>
  );
}
