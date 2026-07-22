"""Deterministic mock data sources for the SEO agents (Phase 1).

NO live web/Google/LinkedIn/GSC/Ahrefs/Semrush calls exist anywhere. These are
fixed, realistic-looking fixtures the runners read so the dashboard has stable,
filterable data. All values are illustrative product data — never presented as
real rankings/reviews/stats in the operator UI.

Markets/cities/services intentionally span UAE (Dubai/Abu Dhabi/Sharjah),
Qatar (Doha) and Saudi (Riyadh) so global filters have something to bite on.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Fixed clock so seeded runs/findings are stable across restarts and tests.
MOCK_NOW = datetime(2026, 7, 22, 6, 0, tzinfo=timezone.utc)


def ago(hours: float = 0, days: float = 0) -> datetime:
    return MOCK_NOW - timedelta(hours=hours, days=days)


# Region every GCC market rolls up to (matches the admin region filter).
REGION = "Middle East"

# Controlled service vocabulary — DERIVED from the canonical catalog (single
# source of truth), so SEO targets the real LaundryKhalas services. See
# seo_agents/taxonomy.py. "Personal Laundry Pickup & Delivery" is an umbrella
# topic kept for the illustrative competitor/GSC rows below.
from seo_agents.taxonomy import service_names as _canonical_service_names

SERVICES = [*_canonical_service_names(), "Personal Laundry Pickup & Delivery"]

MARKETS = [
    {"market": "UAE", "country": "UAE", "city": "Dubai"},
    {"market": "UAE", "country": "UAE", "city": "Abu Dhabi"},
    {"market": "UAE", "country": "UAE", "city": "Sharjah"},
    {"market": "Qatar", "country": "Qatar", "city": "Doha"},
    {"market": "Saudi Arabia", "country": "Saudi Arabia", "city": "Riyadh"},
]

# --- SEO-01 Competitor Monitor: 5 competitor pages ------------------------
COMPETITOR_PAGES = [
    {"competitor_url": "https://competitor-a.ae/dry-cleaning-dubai", "market": "UAE", "city": "Dubai",
     "service": "Dry Cleaning", "change_type": "faq_changed", "detail": "Added 3 FAQs about same-day turnaround", "priority": "high"},
    {"competitor_url": "https://competitor-b.ae/laundry-abu-dhabi", "market": "UAE", "city": "Abu Dhabi",
     "service": "Laundry", "change_type": "new_page", "detail": "New area landing page for Al Reem Island", "priority": "high"},
    {"competitor_url": "https://competitor-c.ae/carpet-cleaning", "market": "UAE", "city": "Sharjah",
     "service": "Carpet Cleaning", "change_type": "content_changed", "detail": "Rewrote hero + added price table", "priority": "medium"},
    {"competitor_url": "https://competitor-d.qa/laundry-doha", "market": "Qatar", "city": "Doha",
     "service": "Laundry", "change_type": "internal_links_changed", "detail": "Added links from blog to money page", "priority": "medium"},
    {"competitor_url": "https://competitor-e.sa/wash-and-fold-riyadh", "market": "Saudi Arabia", "city": "Riyadh",
     "service": "Wash & Fold", "change_type": "new_blog_post", "detail": "Published 'How often to wash winter coats'", "priority": "low"},
]

BACKLINK_OPPORTUNITIES = [  # SEO-09 (6)
    {"source": "uae-business-directory.ae", "type": "directory", "authority": 71, "cost": "free", "market": "UAE", "city": "Dubai", "service": "Laundry", "priority": "high"},
    {"source": "dubai-expat-guide.com/resources", "type": "resource_page", "authority": 63, "cost": "free", "market": "UAE", "city": "Dubai", "service": "Dry Cleaning", "priority": "high"},
    {"source": "gulf-living-blog.com", "type": "guest_post", "authority": 58, "cost": "paid", "market": "UAE", "city": "Abu Dhabi", "service": "Laundry", "priority": "medium"},
    {"source": "qatar-directory.qa", "type": "citation", "authority": 49, "cost": "free", "market": "Qatar", "city": "Doha", "service": "Laundry", "priority": "medium"},
    {"source": "riyadh-services-hub.sa", "type": "directory", "authority": 44, "cost": "free", "market": "Saudi Arabia", "city": "Riyadh", "service": "Wash & Fold", "priority": "medium"},
    {"source": "home-care-mentions.com", "type": "mention", "authority": 52, "cost": "paid", "market": "UAE", "city": "Sharjah", "service": "Carpet Cleaning", "priority": "low"},
]

# --- SEO-03 GSC Monitor: 10 page rows -------------------------------------
GSC_PAGES = [
    {"page_url": "/laundry-service-dubai-marina", "clicks": 412, "impressions": 9800, "ctr": 4.2, "position": 6.1, "delta": 38, "market": "UAE", "city": "Dubai", "service": "Laundry"},
    {"page_url": "/dry-cleaning-dubai", "clicks": 388, "impressions": 12400, "ctr": 3.1, "position": 4.4, "delta": -22, "market": "UAE", "city": "Dubai", "service": "Dry Cleaning"},
    {"page_url": "/wash-and-fold-abu-dhabi", "clicks": 201, "impressions": 6100, "ctr": 3.3, "position": 7.9, "delta": 14, "market": "UAE", "city": "Abu Dhabi", "service": "Wash & Fold"},
    {"page_url": "/laundry-sharjah", "clicks": 164, "impressions": 5200, "ctr": 3.2, "position": 9.2, "delta": -31, "market": "UAE", "city": "Sharjah", "service": "Laundry"},
    {"page_url": "/curtain-cleaning-dubai", "clicks": 143, "impressions": 4300, "ctr": 3.3, "position": 8.1, "delta": 9, "market": "UAE", "city": "Dubai", "service": "Curtain Cleaning"},
    {"page_url": "/carpet-cleaning-dubai", "clicks": 132, "impressions": 4800, "ctr": 2.8, "position": 10.4, "delta": -18, "market": "UAE", "city": "Dubai", "service": "Carpet Cleaning"},
    {"page_url": "/laundry-doha", "clicks": 98, "impressions": 3600, "ctr": 2.7, "position": 11.8, "delta": 27, "market": "Qatar", "city": "Doha", "service": "Laundry"},
    {"page_url": "/shoe-cleaning-dubai", "clicks": 76, "impressions": 2100, "ctr": 3.6, "position": 7.2, "delta": 5, "market": "UAE", "city": "Dubai", "service": "Shoe Cleaning"},
    {"page_url": "/wash-and-fold-riyadh", "clicks": 61, "impressions": 2900, "ctr": 2.1, "position": 13.5, "delta": 19, "market": "Saudi Arabia", "city": "Riyadh", "service": "Wash & Fold"},
    {"page_url": "/commercial-laundry-dubai", "clicks": 54, "impressions": 1800, "ctr": 3.0, "position": 9.6, "delta": -12, "market": "UAE", "city": "Dubai", "service": "Commercial Laundry"},
]

# --- SEO-04 Indexing & Sitemap: 10 URL rows -------------------------------
INDEXING_ROWS = [
    {"page_url": "/laundry-service-dubai-marina", "state": "indexed", "market": "UAE", "city": "Dubai", "service": "Laundry"},
    {"page_url": "/dry-cleaning-dubai", "state": "indexed", "market": "UAE", "city": "Dubai", "service": "Dry Cleaning"},
    {"page_url": "/laundry-al-reem-abu-dhabi", "state": "crawled_not_indexed", "market": "UAE", "city": "Abu Dhabi", "service": "Laundry"},
    {"page_url": "/wash-and-fold-abu-dhabi", "state": "indexed", "market": "UAE", "city": "Abu Dhabi", "service": "Wash & Fold"},
    {"page_url": "/laundry-sharjah-al-nahda", "state": "pending", "market": "UAE", "city": "Sharjah", "service": "Laundry"},
    {"page_url": "/curtain-cleaning-dubai", "state": "indexed", "market": "UAE", "city": "Dubai", "service": "Curtain Cleaning"},
    {"page_url": "/laundry-doha-west-bay", "state": "excluded", "market": "Qatar", "city": "Doha", "service": "Laundry"},
    {"page_url": "/wash-and-fold-riyadh", "state": "crawled_not_indexed", "market": "Saudi Arabia", "city": "Riyadh", "service": "Wash & Fold"},
    {"page_url": "/shoe-cleaning-dubai", "state": "indexed", "market": "UAE", "city": "Dubai", "service": "Shoe Cleaning"},
    {"page_url": "/commercial-laundry-dubai", "state": "pending", "market": "UAE", "city": "Dubai", "service": "Commercial Laundry"},
]

# --- SEO-05 Content Research: 10 opportunities ----------------------------
CONTENT_OPPORTUNITIES = [
    {"title": "How to remove oud/perfume stains from abaya", "intent": "informational", "market": "UAE", "city": "Dubai", "service": "Dry Cleaning", "priority": "high"},
    {"title": "Same-day laundry pickup in Dubai Marina — how it works", "intent": "commercial", "market": "UAE", "city": "Dubai", "service": "Laundry", "priority": "high"},
    {"title": "Wash & fold vs laundry service — which is cheaper in Abu Dhabi", "intent": "commercial", "market": "UAE", "city": "Abu Dhabi", "service": "Wash & Fold", "priority": "medium"},
    {"title": "How often should you dry clean winter coats in the GCC", "intent": "informational", "market": "UAE", "city": "Dubai", "service": "Dry Cleaning", "priority": "medium"},
    {"title": "Carpet cleaning cost guide Sharjah", "intent": "commercial", "market": "UAE", "city": "Sharjah", "service": "Carpet Cleaning", "priority": "medium"},
    {"title": "Curtain cleaning without taking them down — is it possible", "intent": "informational", "market": "UAE", "city": "Dubai", "service": "Curtain Cleaning", "priority": "low"},
    {"title": "Laundry service for villas in Doha", "intent": "commercial", "market": "Qatar", "city": "Doha", "service": "Laundry", "priority": "medium"},
    {"title": "Best way to care for thobes — washing guide", "intent": "informational", "market": "Saudi Arabia", "city": "Riyadh", "service": "Wash & Fold", "priority": "high"},
    {"title": "Shoe cleaning for sneakers vs leather — Dubai", "intent": "informational", "market": "UAE", "city": "Dubai", "service": "Shoe Cleaning", "priority": "low"},
    {"title": "Commercial laundry for Dubai hotels — turnaround SLAs", "intent": "commercial", "market": "UAE", "city": "Dubai", "service": "Commercial Laundry", "priority": "high"},
]

# --- SEO-08 Internal Linking: 8 opportunities -----------------------------
INTERNAL_LINK_OPPS = [
    {"page_url": "/blog/remove-perfume-stains", "target_money_page": "/dry-cleaning-dubai", "reason": "orphan blog, strong topical match", "market": "UAE", "city": "Dubai", "service": "Dry Cleaning", "priority": "high", "orphan": True},
    {"page_url": "/blog/winter-coat-care", "target_money_page": "/dry-cleaning-dubai", "reason": "no internal links to money page", "market": "UAE", "city": "Dubai", "service": "Dry Cleaning", "priority": "medium", "orphan": True},
    {"page_url": "/blog/laundry-tips-marina", "target_money_page": "/laundry-service-dubai-marina", "reason": "boost money page support", "market": "UAE", "city": "Dubai", "service": "Laundry", "priority": "high", "orphan": False},
    {"page_url": "/wash-and-fold-abu-dhabi", "target_money_page": "/laundry-service-abu-dhabi", "reason": "cross-link sibling services", "market": "UAE", "city": "Abu Dhabi", "service": "Wash & Fold", "priority": "medium", "orphan": False},
    {"page_url": "/blog/carpet-care", "target_money_page": "/carpet-cleaning-dubai", "reason": "orphan blog", "market": "UAE", "city": "Dubai", "service": "Carpet Cleaning", "priority": "medium", "orphan": True},
    {"page_url": "/blog/thobe-care", "target_money_page": "/wash-and-fold-riyadh", "reason": "orphan, GCC expansion support", "market": "Saudi Arabia", "city": "Riyadh", "service": "Wash & Fold", "priority": "medium", "orphan": True},
    {"page_url": "/laundry-doha", "target_money_page": "/commercial-laundry-doha", "reason": "support B2B money page", "market": "Qatar", "city": "Doha", "service": "Commercial Laundry", "priority": "low", "orphan": False},
    {"page_url": "/blog/shoe-care", "target_money_page": "/shoe-cleaning-dubai", "reason": "orphan blog", "market": "UAE", "city": "Dubai", "service": "Shoe Cleaning", "priority": "low", "orphan": True},
]

# --- SEO-10 Duplicate/Cannibalization: 6 findings -------------------------
DUPLICATE_FINDINGS = [
    {"page_url": "/laundry-dubai", "other_url": "/laundry-service-dubai", "overlap": "high intent overlap", "recommendation": "merge", "market": "UAE", "city": "Dubai", "service": "Laundry", "priority": "high"},
    {"page_url": "/dry-cleaning-dubai", "other_url": "/dry-clean-dubai", "overlap": "near-duplicate", "recommendation": "canonical", "market": "UAE", "city": "Dubai", "service": "Dry Cleaning", "priority": "high"},
    {"page_url": "/wash-fold-abu-dhabi", "other_url": "/wash-and-fold-abu-dhabi", "overlap": "duplicate", "recommendation": "consolidate", "market": "UAE", "city": "Abu Dhabi", "service": "Wash & Fold", "priority": "medium"},
    {"page_url": "/carpet-cleaning", "other_url": "/carpet-cleaning-dubai", "overlap": "partial, keep both", "recommendation": "rephrase", "market": "UAE", "city": "Dubai", "service": "Carpet Cleaning", "priority": "low"},
    {"page_url": "/laundry-doha", "other_url": "/laundry-service-doha", "overlap": "high intent overlap", "recommendation": "merge", "market": "Qatar", "city": "Doha", "service": "Laundry", "priority": "medium"},
    {"page_url": "/curtain-cleaning", "other_url": "/curtain-cleaning-dubai", "overlap": "partial", "recommendation": "rephrase", "market": "UAE", "city": "Dubai", "service": "Curtain Cleaning", "priority": "low"},
]

# --- SEO-11 Money Page Optimization: 8 recommendations --------------------
MONEY_PAGE_RECS = [
    {"page_url": "/laundry-service-dubai-marina", "gap": "missing primary keyword in H1", "suggestion": "Add 'Laundry Service Dubai Marina' to H1", "market": "UAE", "city": "Dubai", "service": "Laundry", "priority": "high"},
    {"page_url": "/dry-cleaning-dubai", "gap": "thin entity coverage", "suggestion": "Cover fabric types, turnaround, pricing attributes", "market": "UAE", "city": "Dubai", "service": "Dry Cleaning", "priority": "high"},
    {"page_url": "/wash-and-fold-abu-dhabi", "gap": "no FAQ section", "suggestion": "Add 5 FAQs (turnaround, min order, pickup)", "market": "UAE", "city": "Abu Dhabi", "service": "Wash & Fold", "priority": "medium"},
    {"page_url": "/carpet-cleaning-dubai", "gap": "missing LSI terms", "suggestion": "Add stain, deep-clean, upholstery attributes", "market": "UAE", "city": "Dubai", "service": "Carpet Cleaning", "priority": "medium"},
    {"page_url": "/curtain-cleaning-dubai", "gap": "readability low", "suggestion": "Shorten sentences, add bullets", "market": "UAE", "city": "Dubai", "service": "Curtain Cleaning", "priority": "low"},
    {"page_url": "/laundry-doha", "gap": "no schema", "suggestion": "Add Service + LocalBusiness schema", "market": "Qatar", "city": "Doha", "service": "Laundry", "priority": "medium"},
    {"page_url": "/wash-and-fold-riyadh", "gap": "missing headings", "suggestion": "Add H2s for pricing and coverage", "market": "Saudi Arabia", "city": "Riyadh", "service": "Wash & Fold", "priority": "medium"},
    {"page_url": "/commercial-laundry-dubai", "gap": "weak value props", "suggestion": "Add SLA, volume pricing, hotel case study slots", "market": "UAE", "city": "Dubai", "service": "Commercial Laundry", "priority": "high"},
]

# --- SEO-12 Local & Area Page: 8 recommendations --------------------------
AREA_PAGE_RECS = [
    {"page_url": "/laundry-service-dubai-marina", "gap": "no local landmarks/context", "suggestion": "Reference Marina Walk, JBR, towers served", "market": "UAE", "city": "Dubai", "service": "Laundry", "priority": "high"},
    {"page_url": "/laundry-al-reem-abu-dhabi", "gap": "missing LocalBusiness schema", "suggestion": "Add LocalBusiness + areaServed schema", "market": "UAE", "city": "Abu Dhabi", "service": "Laundry", "priority": "high"},
    {"page_url": "/laundry-sharjah-al-nahda", "gap": "no reviews/E-E-A-T", "suggestion": "Add verified review block + author bio", "market": "UAE", "city": "Sharjah", "service": "Laundry", "priority": "medium"},
    {"page_url": "/dry-cleaning-dubai", "gap": "no neighborhood FAQs", "suggestion": "Add area-specific pickup FAQs", "market": "UAE", "city": "Dubai", "service": "Dry Cleaning", "priority": "medium"},
    {"page_url": "/laundry-doha-west-bay", "gap": "thin local content", "suggestion": "Add West Bay coverage + timings", "market": "Qatar", "city": "Doha", "service": "Laundry", "priority": "medium"},
    {"page_url": "/wash-and-fold-riyadh", "gap": "missing Service schema", "suggestion": "Add Service schema + areaServed", "market": "Saudi Arabia", "city": "Riyadh", "service": "Wash & Fold", "priority": "medium"},
    {"page_url": "/carpet-cleaning-dubai", "gap": "no local proof", "suggestion": "Add local reviews + service radius", "market": "UAE", "city": "Dubai", "service": "Carpet Cleaning", "priority": "low"},
    {"page_url": "/curtain-cleaning-dubai", "gap": "no FAQs", "suggestion": "Add 4 curtain-care FAQs", "market": "UAE", "city": "Dubai", "service": "Curtain Cleaning", "priority": "low"},
]

# --- SEO-14 AI Search Visibility: 6 recommendations -----------------------
AI_VISIBILITY_RECS = [
    {"page_url": "/dry-cleaning-dubai", "gap": "no direct-answer block", "suggestion": "Add a 40-60 word answer to 'how much is dry cleaning in Dubai'", "market": "UAE", "city": "Dubai", "service": "Dry Cleaning", "priority": "high"},
    {"page_url": "/laundry-service-dubai-marina", "gap": "no FAQ schema", "suggestion": "Add extractable FAQ block + FAQ schema", "market": "UAE", "city": "Dubai", "service": "Laundry", "priority": "high"},
    {"page_url": "/wash-and-fold-abu-dhabi", "gap": "entities not explicit", "suggestion": "State service, area, price, turnaround as facts", "market": "UAE", "city": "Abu Dhabi", "service": "Wash & Fold", "priority": "medium"},
    {"page_url": "/carpet-cleaning-dubai", "gap": "unstructured pricing", "suggestion": "Add a clear price/attribute table", "market": "UAE", "city": "Dubai", "service": "Carpet Cleaning", "priority": "medium"},
    {"page_url": "/laundry-doha", "gap": "no summary answer", "suggestion": "Add a lead summary answering the core query", "market": "Qatar", "city": "Doha", "service": "Laundry", "priority": "low"},
    {"page_url": "/commercial-laundry-dubai", "gap": "no comparison facts", "suggestion": "Add extractable B2B SLA/volume facts", "market": "UAE", "city": "Dubai", "service": "Commercial Laundry", "priority": "low"},
]

# --- SEO-02 News/Trend alerts (illustrative) ------------------------------
TREND_ALERTS = [
    {"title": "Rising searches: eco-friendly dry cleaning in UAE", "urgency": "high", "market": "UAE", "city": "Dubai", "service": "Dry Cleaning"},
    {"title": "GCC hotels increasing outsourced commercial laundry", "urgency": "medium", "market": "UAE", "city": "Dubai", "service": "Commercial Laundry"},
    {"title": "Seasonal spike: winter coat & thobe care queries", "urgency": "medium", "market": "Saudi Arabia", "city": "Riyadh", "service": "Wash & Fold"},
]

# --- SEO-07 Topical clusters / SEO-15 GCC expansion (illustrative) --------
# Clusters use the canonical service names (see seo_agents/taxonomy.py) so the
# content plan targets the real live services.
TOPICAL_GAPS = [
    {"cluster": "dry cleaning / clean and press", "missing_subtopic": "leather & suede care", "market": "UAE", "city": "Dubai", "service": "Boutique Clean & Press", "priority": "medium"},
    {"cluster": "carpet and curtain cleaning", "missing_subtopic": "pet stain & odour removal", "market": "UAE", "city": "Sharjah", "service": "Deep Carpet & Curtain Care", "priority": "medium"},
    {"cluster": "shoe cleaning and restoration", "missing_subtopic": "sneaker sole whitening", "market": "UAE", "city": "Dubai", "service": "Artisan Shoe Restoration", "priority": "high"},
    {"cluster": "tailoring and alterations", "missing_subtopic": "same-day zipper repair", "market": "UAE", "city": "Dubai", "service": "Tailoring & Alterations", "priority": "medium"},
]

GCC_EXPANSION_OPPS = [
    {"title": "Create /sa/ laundry service Jeddah page", "market": "Saudi Arabia", "city": "Jeddah", "service": "Laundry", "priority": "high"},
    {"title": "Create /kw/ wash & fold Kuwait City page", "market": "Kuwait", "city": "Kuwait City", "service": "Wash & Fold", "priority": "medium"},
    {"title": "Create /qa/ commercial laundry Doha page", "market": "Qatar", "city": "Doha", "service": "Commercial Laundry", "priority": "medium"},
]

# --- SEO-13 Content decay (illustrative, derived from GSC losers) ---------
DECAY_PAGES = [row for row in GSC_PAGES if row["delta"] < -15]
