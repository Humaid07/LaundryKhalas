"""Dashboard table fixtures for the SEO subsections (GSC/indexing/hyperlocal/
technical/competitors/AI-search).

These are served in the EXACT shapes the admin subsection tables render, so
wiring the dashboard to the API is a drop-in (no visual change). Values mirror
the previous static `seo-data.ts` mock, with `market`/`service` added so the
global geo/service filters slice them. Site-wide rows keep `scope="global"`.

Separate from `mock_sources.py` (which feeds the agent RUN output); this module
feeds the subsection TABLES. Both are mock-only, no live calls.
"""
from __future__ import annotations

_CITY_MARKET = {
    "Dubai": "UAE",
    "Abu Dhabi": "UAE",
    "Sharjah": "UAE",
    "Doha": "Qatar",
    "Riyadh": "Saudi Arabia",
}


def _mk(city: str) -> str:
    return _CITY_MARKET.get(city, "UAE")


GSC_PAGES = [
    {"page": "/laundry-service-dubai-marina", "clicks": 412, "impressions": 9800, "ctr": 4.2, "position": 3.1, "delta": -4, "city": "Dubai", "market": _mk("Dubai"), "service": "Laundry"},
    {"page": "/dry-cleaning-abu-dhabi", "clicks": 318, "impressions": 7200, "ctr": 4.4, "position": 2.6, "delta": 2, "city": "Abu Dhabi", "market": _mk("Abu Dhabi"), "service": "Dry Cleaning"},
    {"page": "/wash-and-fold-doha", "clicks": 265, "impressions": 6100, "ctr": 4.3, "position": 4.0, "delta": 1, "city": "Doha", "market": _mk("Doha"), "service": "Wash & Fold"},
    {"page": "/curtain-cleaning-sharjah", "clicks": 148, "impressions": 5200, "ctr": 2.8, "position": 6.2, "delta": -1, "city": "Sharjah", "market": _mk("Sharjah"), "service": "Curtain Cleaning"},
    {"page": "/business-laundry-riyadh", "clicks": 121, "impressions": 4400, "ctr": 2.7, "position": 7.1, "delta": 3, "city": "Riyadh", "market": _mk("Riyadh"), "service": "Commercial Laundry"},
]

INDEXING_QUEUE = [
    {"url": "/dry-cleaning-al-nahda-sharjah", "state": "Submitted", "lastChecked": "2026-07-20", "action": "Awaiting Google", "city": "Sharjah", "market": _mk("Sharjah"), "service": "Dry Cleaning"},
    {"url": "/laundry-jumeirah-village", "state": "Crawled — not indexed", "lastChecked": "2026-07-19", "action": "Improve content depth", "city": "Dubai", "market": _mk("Dubai"), "service": "Laundry"},
    {"url": "/duvet-cleaning-al-rayyan", "state": "Failed", "lastChecked": "2026-07-19", "action": "Resubmit for indexing", "city": "Doha", "market": _mk("Doha"), "service": "Laundry"},
    {"url": "/ironing-service-olaya", "state": "Indexed", "lastChecked": "2026-07-18", "action": "—", "city": "Riyadh", "market": _mk("Riyadh"), "service": "Ironing / Pressing"},
    {"url": "/business-laundry-west-bay", "state": "Submitted", "lastChecked": "2026-07-20", "action": "Awaiting Google", "city": "Doha", "market": _mk("Doha"), "service": "Commercial Laundry"},
]

HYPERLOCAL_PAGES = [
    {"area": "Dubai Marina", "city": "Dubai", "market": _mk("Dubai"), "status": "Published", "wordCount": 940, "duplicateScore": 4, "service": "Laundry"},
    {"area": "Al Nahda", "city": "Sharjah", "market": _mk("Sharjah"), "status": "Awaiting Approval", "wordCount": 820, "duplicateScore": 8, "service": "Dry Cleaning"},
    {"area": "West Bay", "city": "Doha", "market": _mk("Doha"), "status": "Draft", "wordCount": 610, "duplicateScore": 12, "service": "Laundry"},
    {"area": "Jumeirah Village", "city": "Dubai", "market": _mk("Dubai"), "status": "Duplicate Risk", "wordCount": 540, "duplicateScore": 41, "service": "Laundry"},
    {"area": "Olaya", "city": "Riyadh", "market": _mk("Riyadh"), "status": "Published", "wordCount": 880, "duplicateScore": 6, "service": "Ironing / Pressing"},
]

TECH_SEO_ISSUES = [
    {"issue": "Two pages target 'laundry dubai marina'", "type": "Cannibalization", "affected": 2, "severity": "High", "status": "Open", "city": "Dubai", "market": _mk("Dubai")},
    {"issue": "5 pages losing impressions 3 weeks running", "type": "Decay", "affected": 5, "severity": "Medium", "status": "Monitoring", "scope": "global"},
    {"issue": "Orphan pages with no internal links", "type": "Internal Linking", "affected": 7, "severity": "Medium", "status": "Open", "scope": "global"},
    {"issue": "Soft 404 on 3 old area pages", "type": "Crawl", "affected": 3, "severity": "Low", "status": "Open", "scope": "global"},
    {"issue": "Duplicate meta descriptions", "type": "Crawl", "affected": 9, "severity": "Low", "status": "Monitoring", "scope": "global"},
]

COMPETITORS = [
    {"name": "washmen.com", "change": "+3 positions", "movement": "up", "detail": "Refreshed Dubai Marina landing page", "city": "Dubai", "market": _mk("Dubai")},
    {"name": "justclean.com", "change": "New page", "movement": "flat", "detail": "Published Doha hyperlocal cluster", "city": "Doha", "market": _mk("Doha")},
    {"name": "laundryheap.ae", "change": "−2 positions", "movement": "down", "detail": "Lost featured snippet on 'dry cleaning dubai'", "city": "Dubai", "market": _mk("Dubai")},
    {"name": "cleanly.ae", "change": "+12 backlinks", "movement": "up", "detail": "PR mention in Gulf News", "scope": "global"},
]

AI_SEARCH = [
    {"query": "best laundry service in Dubai", "presence": "Mentioned", "engine": "AI Overviews", "opportunity": "Add FAQ schema", "city": "Dubai", "market": _mk("Dubai")},
    {"query": "same day dry cleaning Dubai", "presence": "Absent", "engine": "AI Overviews", "opportunity": "Create comparison content", "city": "Dubai", "market": _mk("Dubai")},
    {"query": "how much does wash and fold cost UAE", "presence": "Cited", "engine": "Perplexity", "opportunity": "Keep pricing table fresh", "market": "UAE"},
    {"query": "laundry pickup and delivery Doha", "presence": "Absent", "engine": "AI Overviews", "opportunity": "Build Doha service page", "city": "Doha", "market": _mk("Doha")},
]
