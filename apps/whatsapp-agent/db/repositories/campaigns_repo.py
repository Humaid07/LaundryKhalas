"""Campaigns + sends persistence + last-touch attribution (Supabase dev/test).

Definitions are synced from ``config/campaigns.json`` (mock-first). ``attribute_booking``
credits a confirmed order to the most recent campaign send within the campaign's
attribution window (last-touch) and marks the send converted — this is what makes a
customer a ``campaign_responder`` (read back by the CRM engine).
"""
from __future__ import annotations

import datetime as _dt

from db import database
from services import campaign as campaign_svc


def _as_date(value):
    return _dt.date.fromisoformat(value) if isinstance(value, str) and value else value


async def sync_from_config() -> int:
    """Upsert campaign definitions from config (idempotent on code). Returns count."""
    campaigns = campaign_svc.load_campaigns()
    for c in campaigns:
        await database.fetchrow(
            """
            insert into campaigns (code, name, campaign_type, offer, discount_percentage,
                                   market, valid_from, valid_to, attribution_window_days,
                                   active, created_by_seed)
            values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,true)
            on conflict (code) do update set
              name = excluded.name, campaign_type = excluded.campaign_type,
              offer = excluded.offer, discount_percentage = excluded.discount_percentage,
              market = excluded.market, valid_from = excluded.valid_from,
              valid_to = excluded.valid_to,
              attribution_window_days = excluded.attribution_window_days,
              active = excluded.active
            """,
            c["code"], c["name"], c.get("campaign_type", "promo"), c.get("offer"),
            c.get("discount_percentage"), c.get("market"), _as_date(c.get("valid_from")),
            _as_date(c.get("valid_to")), int(c.get("attribution_window_days", 30)),
            bool(c.get("active", True)),
        )
    return len(campaigns)


async def get_by_code(code: str) -> dict | None:
    row = await database.fetchrow("select * from campaigns where code = $1", code)
    return dict(row) if row else None


async def record_send(campaign_id: str, customer_id: str,
                      conversation_id: str | None = None) -> dict | None:
    row = await database.fetchrow(
        """
        insert into campaign_sends (campaign_id, customer_id, conversation_id, status)
        values ($1, $2, $3, 'sent') returning *
        """,
        campaign_id, customer_id, conversation_id,
    )
    return dict(row) if row else None


async def attribute_booking(customer_id: str, order_uuid: str) -> dict | None:
    """Last-touch attribution: credit the confirmed order to the most recent send
    within its campaign's attribution window; mark it converted. Returns the credited
    campaign row or None. Idempotent per (send) — an already-converted send is skipped.
    """
    row = await database.fetchrow(
        """
        with candidate as (
          select s.id as send_id, s.campaign_id, s.sent_at, c.attribution_window_days,
                 c.code, c.name
          from campaign_sends s
          join campaigns c on c.id = s.campaign_id
          where s.customer_id = $1
            and s.booking_confirmed_at is null
            and s.sent_at <= now()
            and now() - s.sent_at <= make_interval(days => c.attribution_window_days)
          order by s.sent_at desc
          limit 1
        )
        update campaign_sends s
           set booking_confirmed_at = now(), order_id = $2, status = 'converted'
          from candidate
         where s.id = candidate.send_id
        returning candidate.code as campaign_code, candidate.name as campaign_name
        """,
        customer_id, order_uuid,
    )
    return dict(row) if row else None


async def has_converted_send(customer_id: str) -> bool:
    val = await database.fetchval(
        "select exists(select 1 from campaign_sends where customer_id = $1 "
        "and booking_confirmed_at is not null)",
        customer_id,
    )
    return bool(val)
