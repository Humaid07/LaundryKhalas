"""Activate due scheduled price publishes and expire ended promotions.

Idempotent — safe to run repeatedly. There is no scheduler infrastructure in the
repo yet, so run this from cron / Celery-beat / a Cloudflare Cron Trigger in
production (e.g. every 5 minutes). It invalidates the runtime price cache so the
WhatsApp agent and public API pick up any activated version immediately.

    python scripts/apply_scheduled_pricing.py [--market AE]
"""
from __future__ import annotations

import argparse
import asyncio


async def _run(market: str) -> None:
    from db import AsyncSessionLocal, init_db
    from services import pricing_management as pm
    from services import price_resolver as resolver

    await init_db()
    async with AsyncSessionLocal() as session:
        result = await pm.apply_scheduled(session, market=market)
        await session.commit()
    resolver.invalidate(market)
    print(f"scheduled pricing applied for {market}: "
          f"activated={result['activated_versions']} "
          f"expired_promotions={len(result['expired_promotions'])}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Apply scheduled pricing changes (idempotent).")
    ap.add_argument("--market", default="AE")
    args = ap.parse_args()
    asyncio.run(_run(args.market))


if __name__ == "__main__":
    main()
