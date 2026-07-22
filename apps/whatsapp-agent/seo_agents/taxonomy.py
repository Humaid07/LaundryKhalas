"""SEO service taxonomy — DERIVED from the canonical service catalog.

The SEO agents must target the SAME services the business actually offers, so the
content clusters and hyperlocal (service x market) page matrix are built from the
single source of truth (``config/laundry_services.json`` via ``rules``) rather
than a hand-maintained list. ``scripts/verify_service_taxonomy.py`` and
``tests/test_seo_agents.py`` assert this stays in lock-step with the backend.

No live SEO/web calls — this is taxonomy/config only.
"""
from __future__ import annotations

from rules import active_service_catalog

# Live UAE markets (customers today) + configured future GCC expansion markets.
# Every service supports an area/city/market variant landing page.
MARKETS = ["Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Ras Al Khaimah"]
FUTURE_MARKETS = ["Doha", "Riyadh"]
ALL_MARKETS = MARKETS + FUTURE_MARKETS

# Human-readable content-cluster name per canonical service category.
_CLUSTER_LABELS = {
    "wash_and_fold": "wash and fold laundry",
    "dry_cleaning": "dry cleaning / clean and press",
    "ironing": "steam pressing / ironing",
    "bed_and_bath": "bed and bath linen cleaning",
    "shoe_care": "shoe cleaning and restoration",
    "bag_care": "luxury bag cleaning and restoration",
    "tailoring": "tailoring and alterations",
    "carpet_curtain": "carpet and curtain cleaning",
}

# Cross-cutting cluster not tied to one service — the pickup/delivery experience.
_UMBRELLA_CLUSTERS = ["personal laundry pickup and delivery"]


def service_clusters() -> list[dict]:
    """One content cluster per active canonical service, carrying the service_id
    so SEO findings/recommendations can join back to the real catalog."""
    out: list[dict] = []
    for s in active_service_catalog():
        sid = s.get("service_id", s.get("key"))
        out.append(
            {
                "service_id": sid,
                "display_name": s["label"],
                "category": s.get("category"),
                "cluster": _CLUSTER_LABELS.get(s.get("category"), s["label"].lower()),
                "unit_type": s.get("unit_type"),
            }
        )
    return out


def cluster_names() -> list[str]:
    """All content-cluster names: per-service clusters + umbrella clusters."""
    names = [c["cluster"] for c in service_clusters()]
    for umbrella in _UMBRELLA_CLUSTERS:
        if umbrella not in names:
            names.append(umbrella)
    return names


def taxonomy_service_ids() -> set[str]:
    """The set of service ids the SEO taxonomy covers — must equal the backend
    catalog's service ids (checked by the sync script / tests)."""
    return {c["service_id"] for c in service_clusters()}


def hyperlocal_pages(include_future: bool = False) -> list[dict]:
    """The service x market landing-page matrix every local-SEO page should
    support: {service_id, cluster, market, slug}. ``include_future`` adds the
    configured future GCC markets (Doha, Riyadh)."""
    markets = ALL_MARKETS if include_future else MARKETS
    pages: list[dict] = []
    for c in service_clusters():
        for market in markets:
            slug = f"{c['cluster'].split(' /')[0].replace(' ', '-')}-{market.lower().replace(' ', '-')}"
            pages.append(
                {
                    "service_id": c["service_id"],
                    "cluster": c["cluster"],
                    "market": market,
                    "slug": slug,
                }
            )
    return pages


def service_names() -> list[str]:
    """Canonical service display names — the SEO 'service' controlled vocabulary."""
    return [c["display_name"] for c in service_clusters()]
