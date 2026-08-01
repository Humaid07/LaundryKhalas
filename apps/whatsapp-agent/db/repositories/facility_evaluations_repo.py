"""Facility performance evaluations persistence (dev/test Supabase schema).

Header rows in ``facility_evaluations`` + per-factor rows in
``facility_evaluation_factors``. Evaluations are append-only history: ``create``
inserts a NEW row every time (a new evaluation never overwrites an old one);
``update`` edits an existing evaluation in place (with audit at the service layer)
and replaces its factor rows. The official ``overall_score`` / ``weighted_score``
are computed in services/ratings.py and passed in — this layer only persists.

Every call is scoped by ``facility_id`` (resolved upstream from the session).
"""
from __future__ import annotations

from db import database

_HDR = (
    "id, facility_id, evaluation_date, evaluation_period_start, evaluation_period_end, "
    "overall_score, partner_visible_summary, internal_notes, status, "
    "created_by_user_id, updated_by_user_id, created_at, updated_at"
)
_FACTOR = "id, evaluation_id, factor_key, factor_label, score, weight, weighted_score"


def _num(row: dict) -> dict:
    """Coerce numeric(x,y) (asyncpg Decimal) → float for JSON responses."""
    d = dict(row)
    for k in ("overall_score", "score", "weight", "weighted_score"):
        if k in d and d[k] is not None:
            d[k] = float(d[k])
    return d


async def _attach_factors(headers: list[dict]) -> list[dict]:
    if not headers:
        return []
    ids = [h["id"] for h in headers]
    rows = await database.fetch(
        f"select {_FACTOR} from facility_evaluation_factors "
        "where evaluation_id = any($1::uuid[]) order by factor_key",
        ids,
    )
    by_eval: dict = {}
    for r in rows:
        by_eval.setdefault(str(r["evaluation_id"]), []).append(_num(r))
    return [{**_num(h), "factors": by_eval.get(str(h["id"]), [])} for h in headers]


async def create(
    facility_id: str, *, overall_score: float, factors: list[dict],
    evaluation_date=None, evaluation_period_start=None, evaluation_period_end=None,
    partner_visible_summary: str | None = None, internal_notes: str | None = None,
    status: str = "published", created_by_user_id: str | None = None,
) -> dict:
    pool = await database.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            hdr = await conn.fetchrow(
                f"""
                insert into facility_evaluations
                    (facility_id, evaluation_date, evaluation_period_start,
                     evaluation_period_end, overall_score, partner_visible_summary,
                     internal_notes, status, created_by_user_id, updated_by_user_id,
                     is_test_data, environment, created_by_seed)
                values ($1, coalesce($2::text::date, current_date), $3::text::date,
                        $4::text::date, $5, $6, $7, $8, $9, $9, true, 'dev', false)
                returning {_HDR}
                """,
                facility_id,
                str(evaluation_date) if evaluation_date else None,
                str(evaluation_period_start) if evaluation_period_start else None,
                str(evaluation_period_end) if evaluation_period_end else None,
                overall_score, partner_visible_summary, internal_notes, status,
                created_by_user_id,
            )
            await _insert_factors(conn, hdr["id"], factors)
    return (await _attach_factors([hdr]))[0]


async def _insert_factors(conn, evaluation_id, factors: list[dict]) -> None:
    if not factors:
        return
    await conn.executemany(
        "insert into facility_evaluation_factors "
        "(evaluation_id, factor_key, factor_label, score, weight, weighted_score) "
        "values ($1,$2,$3,$4,$5,$6)",
        [(evaluation_id, f["factor_key"], f["factor_label"], f["score"],
          f["weight"], f["weighted_score"]) for f in factors],
    )


async def get(evaluation_id: str, *, facility_id: str | None = None) -> dict | None:
    sql = f"select {_HDR} from facility_evaluations where id = $1"
    params = [evaluation_id]
    if facility_id is not None:
        sql += " and facility_id = $2"
        params.append(facility_id)
    hdr = await database.fetchrow(sql, *params)
    if hdr is None:
        return None
    return (await _attach_factors([hdr]))[0]


async def list_for_facility(
    facility_id: str, *, status: str | None = None, limit: int = 50, offset: int = 0,
) -> list[dict]:
    sql = f"select {_HDR} from facility_evaluations where facility_id = $1"
    params: list = [facility_id]
    if status is not None:
        params.append(status)
        sql += f" and status = ${len(params)}"
    sql += f" order by evaluation_date desc, created_at desc limit {int(limit)} offset {int(offset)}"
    return await _attach_factors(await database.fetch(sql, *params))


async def count_for_facility(facility_id: str, *, status: str | None = None) -> int:
    sql = "select count(*) from facility_evaluations where facility_id = $1"
    params: list = [facility_id]
    if status is not None:
        params.append(status)
        sql += f" and status = ${len(params)}"
    return int(await database.fetchval(sql, *params) or 0)


async def published_with_factors(facility_id: str) -> list[dict]:
    """Newest-first published evaluations (with factors) for aggregation."""
    return await list_for_facility(facility_id, status="published", limit=500)


async def update(
    evaluation_id: str, facility_id: str, *, overall_score: float | None = None,
    factors: list[dict] | None = None, evaluation_date=None,
    evaluation_period_start=None, evaluation_period_end=None,
    partner_visible_summary: str | None = None, internal_notes: str | None = None,
    status: str | None = None, updated_by_user_id: str | None = None,
    _set_summary: bool = False, _set_notes: bool = False,
) -> dict | None:
    sets: list[str] = ["updated_by_user_id = $2"]
    params: list = [evaluation_id, updated_by_user_id]

    def add(col, val, cast=""):
        params.append(val)
        sets.append(f"{col} = ${len(params)}{cast}")

    if overall_score is not None:
        add("overall_score", overall_score)
    if evaluation_date is not None:
        add("evaluation_date", str(evaluation_date), "::text::date")
    if evaluation_period_start is not None:
        add("evaluation_period_start", str(evaluation_period_start), "::text::date")
    if evaluation_period_end is not None:
        add("evaluation_period_end", str(evaluation_period_end), "::text::date")
    if _set_summary:
        add("partner_visible_summary", partner_visible_summary)
    if _set_notes:
        add("internal_notes", internal_notes)
    if status is not None:
        add("status", status)

    pool = await database.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            params.append(facility_id)
            hdr = await conn.fetchrow(
                f"update facility_evaluations set {', '.join(sets)} "
                f"where id = $1 and facility_id = ${len(params)} returning {_HDR}",
                *params,
            )
            if hdr is None:
                return None
            if factors is not None:
                await conn.execute(
                    "delete from facility_evaluation_factors where evaluation_id = $1",
                    evaluation_id)
                await _insert_factors(conn, evaluation_id, factors)
    return (await _attach_factors([hdr]))[0]
