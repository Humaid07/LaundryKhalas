"""Cross-surface service-taxonomy consistency check.

Compares the service taxonomy across the four surfaces that must agree:

  1. backend catalog     — config/laundry_services.json (single source of truth)
  2. WhatsApp options    — the service-selection options the agent offers
  3. SEO taxonomy        — seo_agents/taxonomy.py content clusters
  4. dashboard mirror    — apps/admin/lib/dashboard/service-catalog.ts

Surfaces 2 and 3 are DERIVED from surface 1 in code, so they can only drift if
someone edits them by hand; surface 4 is a separate checked-in TS file that a
human must keep in sync. ``check_taxonomy_sync`` returns a machine-readable
report the ``/api/service-taxonomy/health`` endpoint serves (so the dashboard can
show a "Service taxonomy mismatch detected." warning) and the
``scripts/verify_service_taxonomy.py`` CLI exits non-zero on.
"""
from __future__ import annotations

import re
from pathlib import Path

from rules import service_ids, service_labels, service_options
from seo_agents.taxonomy import taxonomy_service_ids

# apps/whatsapp-agent/services/taxonomy_sync.py -> repo root is 3 parents up.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DASHBOARD_MIRROR = (
    _REPO_ROOT / "apps" / "admin" / "lib" / "dashboard" / "service-catalog.ts"
)


def _parse_dashboard_mirror(path: Path = _DASHBOARD_MIRROR) -> dict:
    """Extract {service_id -> display_name} from the SERVICE_CATALOG entries in
    the dashboard's TS mirror. Returns ``{}`` if the file is missing (reported as
    a mismatch by the caller, not an exception)."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    ids = re.findall(r"service_id:\s*[\"']([^\"']+)[\"']", text)
    names = re.findall(r"display_name:\s*[\"']([^\"']+)[\"']", text)
    return dict(zip(ids, names))


def check_taxonomy_sync() -> dict:
    """Compare all surfaces. Returns::

        {
          "in_sync": bool,
          "mismatches": [ {"surface": str, "detail": str}, ... ],
          "surfaces": { "backend": [...ids...], "whatsapp": [...], "seo": [...], "dashboard": [...] },
        }
    """
    backend_ids = list(service_ids())
    backend_set = set(backend_ids)
    labels = service_labels()

    whatsapp_ids = [o["id"] for o in service_options() if o["id"] != "help_me_choose"]
    seo_ids = taxonomy_service_ids()
    dashboard_map = _parse_dashboard_mirror()

    mismatches: list[dict] = []

    if set(whatsapp_ids) != backend_set:
        mismatches.append({
            "surface": "whatsapp_agent",
            "detail": f"WhatsApp service options {sorted(set(whatsapp_ids))} != backend {sorted(backend_set)}",
        })

    if seo_ids != backend_set:
        missing = backend_set - seo_ids
        extra = seo_ids - backend_set
        mismatches.append({
            "surface": "seo_agents",
            "detail": f"SEO taxonomy drift — missing={sorted(missing)} extra={sorted(extra)}",
        })

    if not dashboard_map:
        mismatches.append({
            "surface": "dashboard",
            "detail": f"Dashboard mirror not found or empty at {_DASHBOARD_MIRROR}",
        })
    else:
        dash_ids = set(dashboard_map)
        if dash_ids != backend_set:
            missing = backend_set - dash_ids
            extra = dash_ids - backend_set
            mismatches.append({
                "surface": "dashboard",
                "detail": f"Dashboard service ids drift — missing={sorted(missing)} extra={sorted(extra)}",
            })
        else:
            # ids match — verify the display names match too.
            name_diffs = [
                f"{sid}: backend='{labels.get(sid)}' dashboard='{dashboard_map[sid]}'"
                for sid in backend_ids
                if labels.get(sid) != dashboard_map[sid]
            ]
            if name_diffs:
                mismatches.append({
                    "surface": "dashboard",
                    "detail": "Display-name drift — " + "; ".join(name_diffs),
                })

    return {
        "in_sync": not mismatches,
        "mismatches": mismatches,
        "surfaces": {
            "backend": backend_ids,
            "whatsapp": whatsapp_ids,
            "seo": sorted(seo_ids),
            "dashboard": list(dashboard_map),
        },
    }
