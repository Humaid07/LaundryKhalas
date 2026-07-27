"""Campaign eligibility + last-touch attribution (pure, deterministic).

Campaign definitions come from ``config/campaigns.json`` (mock-first — no live
marketing source). The backend validates eligibility/expiry here; the agent must
NEVER grant an expired or ineligible offer. Attribution is last-touch by default:
a confirmed booking is credited to the most recent campaign send within that
campaign's attribution window. Pure + side-effect free.
"""
from __future__ import annotations

import datetime as _dt
import json
from functools import lru_cache
from pathlib import Path

_CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "campaigns.json"

ATTRIBUTION_WINDOWS = (7, 14, 30)


@lru_cache(maxsize=1)
def load_campaigns() -> list[dict]:
    with _CONFIG_FILE.open(encoding="utf-8") as fh:
        return json.load(fh).get("campaigns", [])


def _as_date(value) -> _dt.date | None:
    if value is None:
        return None
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    return _dt.date.fromisoformat(str(value))


def is_eligible(campaign: dict, today: _dt.date, *, market: str | None = None) -> bool:
    """A campaign is usable when it's active, today is within [valid_from, valid_to],
    and (if the campaign targets a market) the market matches."""
    if not campaign.get("active", True):
        return False
    vf = _as_date(campaign.get("valid_from"))
    vt = _as_date(campaign.get("valid_to"))
    if vf and today < vf:
        return False
    if vt and today > vt:
        return False
    camp_market = campaign.get("market")
    if camp_market and market and camp_market != market:
        return False
    return True


def eligible_campaigns(today: _dt.date, *, market: str | None = None) -> list[dict]:
    return [c for c in load_campaigns() if is_eligible(c, today, market=market)]


def find_by_code(code: str | None) -> dict | None:
    if not code:
        return None
    for c in load_campaigns():
        if c.get("code", "").upper() == code.upper():
            return c
    return None


def pick_last_touch(sends: list[dict], booking_dt: _dt.datetime,
                    window_days: int) -> dict | None:
    """Last-touch attribution: the most recent send strictly before the booking and
    within ``window_days``. ``sends`` items have ``sent_at`` (datetime) + ``campaign_id``."""
    best = None
    for s in sends:
        sent = s.get("sent_at")
        if not isinstance(sent, _dt.datetime):
            continue
        if sent > booking_dt:
            continue
        if (booking_dt - sent).days > window_days:
            continue
        if best is None or sent > best["sent_at"]:
            best = s
    return best
