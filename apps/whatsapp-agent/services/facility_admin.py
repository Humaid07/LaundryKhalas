"""Facility management writes — validated, audited create / update / status.

The single choke point for facility mutations from the internal dashboard, the
partner portal and (for status only) the agent. Every write is validated, records
a ``facility_audit_log`` entry with before/after + actor/source, and invalidates
the facility matching cache so downstream reads (including the agent) never see
stale availability. quality_score + internal rates are only writable by internal
callers — the partner API/schema never lets them through (CLAUDE.md §5/§6/§7).
"""
from __future__ import annotations

from db.repositories import (
    catalogue_repo,
    facilities_repo,
    facility_audit_repo,
    facility_pricing_repo,
)
from services import facility_matching

EMIRATES = frozenset({
    "Abu Dhabi", "Dubai", "Sharjah", "Ajman",
    "Umm Al Quwain", "Ras Al Khaimah", "Fujairah",
})
STATUSES = frozenset({"open", "busy", "paused", "closed"})
CAPACITY_UNITS = frozenset({"orders_per_day", "kg_per_day", "pieces_per_day"})


class FacilityValidationError(ValueError):
    """Raised on invalid facility input (mapped to HTTP 422 at the API layer)."""


def _range(errors, fields, key, lo, hi, label):
    if key in fields and fields[key] is not None:
        try:
            v = float(fields[key])
        except (TypeError, ValueError):
            errors.append(f"{label} must be a number.")
            return
        if not (lo <= v <= hi):
            errors.append(f"{label} must be between {lo} and {hi}.")


def _validate(fields: dict, *, partial: bool) -> None:
    errors: list[str] = []
    if not partial and not (fields.get("name") or "").strip():
        errors.append("name is required.")
    _range(errors, fields, "latitude", -90, 90, "latitude")
    _range(errors, fields, "longitude", -180, 180, "longitude")
    _range(errors, fields, "quality_score", 0, 100, "quality_score")
    if fields.get("service_radius_km") is not None:
        try:
            if float(fields["service_radius_km"]) <= 0:
                errors.append("service_radius_km must be positive.")
        except (TypeError, ValueError):
            errors.append("service_radius_km must be a number.")
    if fields.get("capacity_daily") is not None:
        try:
            if int(fields["capacity_daily"]) <= 0:
                errors.append("capacity must be a positive whole number.")
        except (TypeError, ValueError):
            errors.append("capacity must be a whole number.")
    if fields.get("capacity_unit") is not None and fields["capacity_unit"] not in CAPACITY_UNITS:
        errors.append(f"capacity_unit must be one of {sorted(CAPACITY_UNITS)}.")
    if fields.get("operating_status") is not None and fields["operating_status"] not in STATUSES:
        errors.append(f"operating_status must be one of {sorted(STATUSES)}.")
    if fields.get("emirate") is not None and fields["emirate"] not in EMIRATES:
        errors.append("emirate must be one of the seven UAE emirates.")
    if errors:
        raise FacilityValidationError(" ".join(errors))


async def _check_services(codes: list[str]) -> None:
    if not codes:
        return
    valid = {c["code"] for c in await catalogue_repo.list_categories()}
    bad = [c for c in codes if c not in valid]
    if bad:
        raise FacilityValidationError(
            f"Accepted services must exist in the catalogue; unknown: {', '.join(bad)}."
        )


async def create_facility(
    fields: dict, *, actor_id: str | None = None,
    actor_type: str = "internal", source_app: str = "admin_dashboard",
) -> dict | None:
    fields = dict(fields)
    services = fields.pop("services", None)
    _validate(fields, partial=False)
    if services is not None:
        await _check_services(services)
    fac = await facilities_repo.create(fields, actor_id=actor_id)
    if fac and services is not None:
        await facilities_repo.set_services(fac["id"], services)
        fac["service_codes"] = await facilities_repo.get_services(fac["id"])
    if fac:
        await facility_audit_repo.create(
            facility_id=fac["id"], action="facility_created", actor_id=actor_id,
            actor_type=actor_type, source_app=source_app, before=None, after=fac,
        )
        facility_matching.invalidate()
    return fac


async def update_facility(
    facility_id: str, patch: dict, *, actor_id: str | None = None,
    actor_type: str = "internal", source_app: str = "admin_dashboard",
) -> dict | None:
    patch = dict(patch)
    services = patch.pop("services", None)
    _validate(patch, partial=True)
    if services is not None:
        await _check_services(services)
    before = await facilities_repo.get_admin(facility_id)
    if before is None:
        return None
    fac = await facilities_repo.update(facility_id, patch, actor_id=actor_id)
    if services is not None:
        await facilities_repo.set_services(facility_id, services)
        if fac:
            fac["service_codes"] = await facilities_repo.get_services(facility_id)
    await facility_audit_repo.create(
        facility_id=facility_id, action="facility_updated", actor_id=actor_id,
        actor_type=actor_type, source_app=source_app, before=before, after=fac,
    )
    facility_matching.invalidate()
    return fac


async def change_status(
    facility_id: str, status: str, *, actor_id: str | None = None,
    actor_type: str = "internal", source_app: str = "admin_dashboard",
) -> dict | None:
    if status not in STATUSES:
        raise FacilityValidationError(f"operating_status must be one of {sorted(STATUSES)}.")
    before = await facilities_repo.get_admin(facility_id)
    if before is None:
        return None
    fac = await facilities_repo.set_status(facility_id, status, actor_id=actor_id)
    await facility_audit_repo.create(
        facility_id=facility_id, action="status_changed", actor_id=actor_id,
        actor_type=actor_type, source_app=source_app,
        before={"operating_status": before.get("operating_status")},
        after={"operating_status": status},
    )
    facility_matching.invalidate()
    return fac


async def set_rate(
    facility_id: str, service_code: str, rate, *, currency: str = "AED",
    actor_id: str | None = None, source_app: str = "admin_dashboard",
) -> dict | None:
    """INTERNAL ONLY. Set/upsert a facility's internal (payable) rate for a service."""
    valid = {c["code"] for c in await catalogue_repo.list_categories()}
    if service_code not in valid:
        raise FacilityValidationError(f"Unknown service code: {service_code}.")
    try:
        if float(rate) < 0:
            raise FacilityValidationError("rate must be zero or positive.")
    except (TypeError, ValueError):
        raise FacilityValidationError("rate must be a number.")
    before = await facility_pricing_repo.list_rates(facility_id)
    row = await facility_pricing_repo.upsert_rate(
        facility_id, service_code, rate=rate, currency=currency
    )
    await facility_audit_repo.create(
        facility_id=facility_id, action="rates_changed", actor_id=actor_id,
        actor_type="internal", source_app=source_app,
        before={"rates": before},
        after={"service_code": service_code, "rate": float(rate), "currency": currency},
    )
    facility_matching.invalidate()
    return row
