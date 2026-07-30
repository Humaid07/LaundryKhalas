"""Facility order photos — intake + pre-dispatch proof uploads.

Registered under the blanket ``require_facility_scope`` guard (main.py), so the
principal always carries a resolved ``facility_id``. Every route first resolves
the order through the FACILITY-SCOPED lookup (``facility_orders_repo.get_row``);
an order that is not the caller's facility's returns 404 — a facility can never
read or write another facility's order photos.

The content endpoint streams the image bytes back Bearer-authenticated (the
frontend fetches it as a blob), so photos are never exposed on an open URL.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile

from api import deps
from api.facility import _fid, _require_manage, _require_supabase_write
from db import database
from db.repositories import facility_orders_repo
from services import order_photos as photo_svc

router = APIRouter(prefix="/api/facility", tags=["facility"])

_EMPTY_COUNTS = {"intake": 0, "pre_dispatch": 0}


def _actor(principal: dict) -> str:
    return (principal or {}).get("full_name") or (principal or {}).get("email") or "Facility"


async def _resolve_order(fid: str, order_id: str) -> dict:
    """Facility-scoped order row, or 404 (never leaks another facility's order)."""
    row = await facility_orders_repo.get_row(fid, order_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Order not found for this facility.")
    return row


@router.get("/orders/{order_id}/photos")
async def list_order_photos(
    order_id: str,
    stage: str | None = None,
    principal: dict = Depends(deps.require_facility_scope),
):
    if not database.is_supabase_mode():
        return {"photos": [], "counts": dict(_EMPTY_COUNTS)}
    fid = _fid(principal)
    row = await _resolve_order(fid, order_id)
    order_uuid = str(row["id"])
    all_photos = await photo_svc.list_photos(order_uuid)
    counts = dict(_EMPTY_COUNTS)
    for p in all_photos:
        if p["stage"] in counts:
            counts[p["stage"]] += 1
    photos = [p for p in all_photos if not stage or p["stage"] == stage]
    return {"photos": photos, "counts": counts}


@router.post("/orders/{order_id}/photos")
async def upload_order_photos(
    order_id: str,
    stage: str = Form(...),
    files: list[UploadFile] = File(...),
    principal: dict = Depends(deps.require_facility_scope),
):
    _require_supabase_write()
    fid = _fid(principal)
    row = await _resolve_order(fid, order_id)
    incoming = [
        photo_svc.IncomingPhoto(
            filename=f.filename, content_type=f.content_type, data=await f.read()
        )
        for f in files
    ]
    try:
        photos = await photo_svc.add_photos(
            order_uuid=str(row["id"]),
            facility_id=fid,
            stage=stage,
            files=incoming,
            actor_id=(principal or {}).get("id"),
            actor_name=_actor(principal),
        )
    except photo_svc.PhotoValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    return {"photos": photos, "stage": stage, "uploaded": len(photos)}


@router.delete("/orders/{order_id}/photos/{photo_id}")
async def delete_order_photo(
    order_id: str,
    photo_id: str,
    principal: dict = Depends(deps.require_facility_scope),
):
    _require_supabase_write()
    _require_manage(principal)  # remove is owner/manager only
    fid = _fid(principal)
    await _resolve_order(fid, order_id)
    removed = await photo_svc.delete_photo(photo_id, fid, actor_name=_actor(principal))
    if removed is None:
        raise HTTPException(status_code=404, detail="Photo not found for this facility.")
    return {"deleted": True, "id": removed["id"]}


@router.get("/orders/{order_id}/photos/{photo_id}/content")
async def order_photo_content(
    order_id: str,
    photo_id: str,
    principal: dict = Depends(deps.require_facility_scope),
):
    if not database.is_supabase_mode():
        raise HTTPException(status_code=404, detail="Photo not found.")
    fid = _fid(principal)
    await _resolve_order(fid, order_id)
    result = await photo_svc.read_content(photo_id, fid)
    if result is None:
        raise HTTPException(status_code=404, detail="Photo not found.")
    data, content_type, file_name = result
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Cache-Control": "private, max-age=300",
            "Content-Disposition": f'inline; filename="{file_name}"',
        },
    )
