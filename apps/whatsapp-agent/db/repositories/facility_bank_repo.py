"""Facility bank details persistence (dev/test Supabase schema).

Raw CRUD over ``facility_bank_details`` — ONE row per facility. This layer is
deliberately dumb: it stores exactly the columns handed to it and never encrypts,
decrypts, masks, or audits. All of that (Fernet encrypt/decrypt, last-4 masking,
audit logging, partner-vs-internal shaping) lives in services/facility_bank.py so
the crypto boundary is in one place. The sensitive IBAN / account number are
persisted ONLY as ciphertext (the ``*_ciphertext`` columns); plaintext never
reaches this module's SQL.

Every call is scoped by ``facility_id`` (resolved from the session upstream).
"""
from __future__ import annotations

from db import database

_COLS = (
    "id, facility_id, account_holder_name, bank_name, swift_bic, branch_name, "
    "bank_country, currency, iban_ciphertext, iban_last4, "
    "account_number_ciphertext, account_number_last4, "
    "created_by_user_id, updated_by_user_id, created_at, updated_at"
)

# Columns a write may set (never facility_id — that comes from the session).
_WRITABLE = (
    "account_holder_name", "bank_name", "swift_bic", "branch_name",
    "bank_country", "currency", "iban_ciphertext", "iban_last4",
    "account_number_ciphertext", "account_number_last4",
)


async def get(facility_id: str) -> dict | None:
    return await database.fetchrow(
        f"select {_COLS} from facility_bank_details where facility_id = $1",
        facility_id,
    )


async def upsert(facility_id: str, *, updated_by_user_id: str | None = None,
                 **fields) -> dict | None:
    """Insert or update the single bank-details row for a facility. Only keys in
    ``_WRITABLE`` that are explicitly provided (present in ``fields``) are written,
    so a partial edit never clobbers untouched columns."""
    data = {k: v for k, v in fields.items() if k in _WRITABLE}
    existing = await get(facility_id)

    if existing is None:
        cols = ["facility_id", "updated_by_user_id", "created_by_user_id"]
        params: list = [facility_id, updated_by_user_id, updated_by_user_id]
        placeholders = ["$1", "$2", "$3"]
        for col, val in data.items():
            params.append(val)
            cols.append(col)
            placeholders.append(f"${len(params)}")
        await database.execute(
            f"insert into facility_bank_details "
            f"({', '.join(cols)}, is_test_data, environment, created_by_seed) "
            f"values ({', '.join(placeholders)}, true, 'dev', false)",
            *params,
        )
        return await get(facility_id)

    sets = ["updated_by_user_id = $2"]
    params = [facility_id, updated_by_user_id]
    for col, val in data.items():
        params.append(val)
        sets.append(f"{col} = ${len(params)}")
    return await database.fetchrow(
        f"update facility_bank_details set {', '.join(sets)} "
        f"where facility_id = $1 returning {_COLS}",
        *params,
    )
