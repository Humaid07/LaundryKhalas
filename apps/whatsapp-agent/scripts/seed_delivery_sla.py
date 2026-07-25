"""Import the delivery SLA rules into Supabase (task spec §§23-25).

Reads config/delivery_sla.json and upserts `delivery_sla_rules` by stable
``code``. IDEMPOTENT: running twice creates no duplicates; it updates values in
place and deactivates rules no longer in the JSON (never deletes — a historical
order may reference a rule code). Never inserts customers/orders/conversations.

Usage (from apps/whatsapp-agent):
    python scripts/seed_delivery_sla.py            # apply DDL + seed
    python scripts/seed_delivery_sla.py --no-ddl   # seed only (table must exist)

Guards: refuses production; requires DATABASE_MODE=supabase.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import database  # noqa: E402
from scripts._safety import _base_problems  # noqa: E402
from services import delivery  # noqa: E402
from settings import get_settings  # noqa: E402

_MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "supabase" / "migrations" / "20260723_000010_delivery_sla.sql"
)
_SOURCE = "Laundry Khalas standard turnaround rules (task spec §23)"


async def seed(conn, apply_ddl: bool) -> int:
    raw_verified = delivery.meta().get("verified_at")
    verified_at = _dt.date.fromisoformat(raw_verified) if raw_verified else None

    if apply_ddl:
        await conn.execute(_MIGRATION.read_text(encoding="utf-8"))
        print(f"  applied DDL: {_MIGRATION.name}")

    all_rules = list(delivery.rules()) + [delivery.default_rule()]
    seen: list[str] = []
    for r in all_rules:
        m = r.get("match", {})
        await conn.execute(
            """
            insert into delivery_sla_rules
                (code, match_category_code, match_item_codes, min_hours, max_hours,
                 day_type, express_eligible, priority, display_text, active, source, source_verified_at)
            values ($1,$2,$3,$4,$5,$6,$7,$8,$9,true,$10,$11)
            on conflict (code) do update set
                match_category_code=excluded.match_category_code,
                match_item_codes=excluded.match_item_codes,
                min_hours=excluded.min_hours, max_hours=excluded.max_hours,
                day_type=excluded.day_type, express_eligible=excluded.express_eligible,
                priority=excluded.priority, display_text=excluded.display_text,
                active=true, source=excluded.source, source_verified_at=excluded.source_verified_at
            """,
            r["code"], m.get("category_code"), m.get("item_codes"),
            r["min_hours"], r["max_hours"], r.get("day_type", "CALENDAR"),
            bool(r.get("express_eligible")), r.get("priority", 0), r["display_text"],
            _SOURCE, verified_at,
        )
        seen.append(r["code"])

    deactivated = await conn.fetchval(
        "with d as (update delivery_sla_rules set active = false "
        "where active = true and code <> all($1::text[]) returning 1) "
        "select count(*) from d",
        seen,
    )
    print(f"  rules={len(seen)} deactivated={deactivated or 0}")
    return len(seen)


async def _main(apply_ddl: bool) -> int:
    settings = get_settings()
    problems = _base_problems(settings)
    if problems:
        print("Refusing to seed the SLA rules:")
        for p in problems:
            print(f"  - {p}")
        return 2
    print(f"Seeding delivery SLA rules into {settings.database_mode} ({settings.database_env})")
    pool = await database.get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await seed(conn, apply_ddl)
    finally:
        await database.close_pool()
    print("Done. DB is the runtime source of truth for delivery SLA.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Seed the Laundry Khalas delivery SLA rules.")
    ap.add_argument("--no-ddl", action="store_true", help="Skip the migration DDL (table must exist).")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(_main(apply_ddl=not args.no_ddl)))
