"""Facility bank details — the crypto/masking/audit boundary (spec §2/§10/§13).

This is the ONLY place that turns partner/internal input into stored bank data
and stored bank data into a response. Responsibilities:

  * validate input (mandatory holder name + IBAN; UAE IBAN format check);
  * encrypt the two account-identifying values (IBAN, account number) with
    services/field_encryption before they touch the DB — plaintext is never
    persisted, logged, or returned except via the explicit ``reveal`` action;
  * derive masked display values (AE•• •••• •••• •••• 1234) from the stored
    last-4 WITHOUT decrypting, for the default (non-reveal) reads;
  * audit every create/update/reveal with MASKED identifiers only (last 4),
    never ciphertext or plaintext (CLAUDE.md §7/§10).

Ownership (which facility) is resolved from the authenticated session upstream
and passed in as ``facility_id`` — this module never trusts a client id.
"""
from __future__ import annotations

import re

from db.repositories import facility_audit_repo, facility_bank_repo
from services import field_encryption

_MASK_GROUP = "••••"


class BankValidationError(ValueError):
    """Raised on invalid bank input (surfaced as HTTP 422 by the API layer)."""


# --------------------------------------------------------------------------
# IBAN handling
# --------------------------------------------------------------------------
def normalize_iban(iban: str | None) -> str:
    """Uppercase + strip spaces/punctuation for storage & validation."""
    return re.sub(r"[^A-Z0-9]", "", (iban or "").upper())


def _iban_mod97_ok(iban: str) -> bool:
    """ISO 13616 checksum: move the first 4 chars to the end, map letters to
    numbers (A=10..Z=35), and require the big-integer mod 97 == 1."""
    if len(iban) < 15 or len(iban) > 34:
        return False
    rearranged = iban[4:] + iban[:4]
    digits = "".join(str(int(ch, 36)) if ch.isalpha() else ch for ch in rearranged)
    if not digits.isdigit():
        return False
    return int(digits) % 97 == 1


def validate_iban(iban: str, *, country: str | None) -> str:
    """Validate & return the normalized IBAN, or raise BankValidationError.
    Applies the country-agnostic mod-97 checksum, plus the UAE-specific length
    rule (23 chars, 'AE' prefix) when the country is the UAE."""
    norm = normalize_iban(iban)
    if not norm:
        raise BankValidationError("IBAN is required.")
    if not re.match(r"^[A-Z]{2}[0-9A-Z]{13,32}$", norm):
        raise BankValidationError("IBAN format is invalid.")
    is_uae = (country or "").upper() in ("AE", "ARE", "UAE") or norm.startswith("AE")
    if is_uae and (len(norm) != 23 or not norm.startswith("AE")):
        raise BankValidationError("A UAE IBAN must be 23 characters and start with 'AE'.")
    if not _iban_mod97_ok(norm):
        raise BankValidationError("IBAN checksum is invalid.")
    return norm


# --------------------------------------------------------------------------
# Masking
# --------------------------------------------------------------------------
def mask_iban(last4: str | None, *, country: str | None = None) -> str | None:
    """Masked IBAN display, e.g. 'AE•• •••• •••• •••• 1234'. Built from the stored
    last-4 only — no decryption, and the middle is never revealed."""
    if not last4:
        return None
    prefix = (country or "AE")[:2].upper()
    return f"{prefix}•• {_MASK_GROUP} {_MASK_GROUP} {_MASK_GROUP} {last4}"


def mask_account_number(last4: str | None) -> str | None:
    """Masked account number, e.g. '•••• 1234'."""
    if not last4:
        return None
    return f"{_MASK_GROUP} {last4}"


def _last4(value: str) -> str:
    return value[-4:] if value and len(value) >= 4 else value


# --------------------------------------------------------------------------
# Response shaping
# --------------------------------------------------------------------------
def to_masked(row: dict | None) -> dict | None:
    """Default (safe) representation — NO ciphertext, NO full values. This is what
    partner and internal reads return unless an explicit reveal is requested."""
    if row is None:
        return None
    country = row.get("bank_country")
    return {
        "facility_id": str(row.get("facility_id")) if row.get("facility_id") else None,
        "account_holder_name": row.get("account_holder_name"),
        "bank_name": row.get("bank_name"),
        "swift_bic": row.get("swift_bic"),
        "branch_name": row.get("branch_name"),
        "bank_country": country,
        "currency": row.get("currency"),
        "iban_masked": mask_iban(row.get("iban_last4"), country=country),
        "iban_last4": row.get("iban_last4"),
        "account_number_masked": mask_account_number(row.get("account_number_last4")),
        "account_number_last4": row.get("account_number_last4"),
        "has_iban": bool(row.get("iban_ciphertext")),
        "has_account_number": bool(row.get("account_number_ciphertext")),
        "updated_at": row.get("updated_at"),
        "created_at": row.get("created_at"),
    }


def _audit_snapshot(row: dict | None) -> dict | None:
    """Masked snapshot for the audit log — last-4 only, never ciphertext/plaintext."""
    if row is None:
        return None
    return {
        "account_holder_name": row.get("account_holder_name"),
        "bank_name": row.get("bank_name"),
        "swift_bic": row.get("swift_bic"),
        "branch_name": row.get("branch_name"),
        "bank_country": row.get("bank_country"),
        "currency": row.get("currency"),
        "iban_last4": row.get("iban_last4"),
        "account_number_last4": row.get("account_number_last4"),
    }


# --------------------------------------------------------------------------
# Operations
# --------------------------------------------------------------------------
async def get_masked(facility_id: str) -> dict | None:
    return to_masked(await facility_bank_repo.get(facility_id))


async def reveal(
    facility_id: str, *, actor_id: str | None, actor_type: str = "internal",
    source_app: str | None = None,
) -> dict | None:
    """Full, decrypted bank details for an AUTHORIZED caller. Audited as an access
    event (masked identifiers only). Authorization is enforced at the API layer."""
    row = await facility_bank_repo.get(facility_id)
    if row is None:
        return None
    result = to_masked(row)
    result["iban"] = field_encryption.decrypt(row.get("iban_ciphertext"))
    result["account_number"] = field_encryption.decrypt(row.get("account_number_ciphertext"))
    await facility_audit_repo.create(
        facility_id=facility_id, action="bank_details_revealed",
        actor_id=actor_id, actor_type=actor_type, source_app=source_app,
        before=None, after={"iban_last4": row.get("iban_last4")},
    )
    return result


# Descriptive (non-secret) fields a caller may set directly.
_DESCRIPTIVE = ("account_holder_name", "bank_name", "swift_bic", "branch_name",
                "bank_country", "currency")


async def upsert(
    facility_id: str, payload: dict, *, actor_id: str | None,
    actor_type: str = "partner", source_app: str | None = None,
) -> dict:
    """Validate, encrypt, store, and audit bank details for a facility. ``payload``
    may include descriptive fields plus optional plaintext ``iban`` / ``account_number``.
    Returns the MASKED representation (never plaintext)."""
    if not field_encryption.is_available():
        raise BankValidationError(
            "Bank details cannot be stored: encryption is not configured on the server."
        )
    before = await facility_bank_repo.get(facility_id)

    write: dict = {}
    for key in _DESCRIPTIVE:
        if key in payload and payload[key] is not None:
            write[key] = str(payload[key]).strip() or None

    country = write.get("bank_country") or (before or {}).get("bank_country") or "AE"

    # Mandatory: holder name + IBAN must exist after this write (either provided
    # now or already stored). IBAN is the minimum needed to pay a facility.
    holder = write.get("account_holder_name") or (before or {}).get("account_holder_name")
    if not holder:
        raise BankValidationError("Account holder name is required.")

    iban_in = payload.get("iban")
    if iban_in:
        norm = validate_iban(iban_in, country=country)
        write["iban_ciphertext"] = field_encryption.encrypt(norm)
        write["iban_last4"] = _last4(norm)
    elif before is None or not before.get("iban_ciphertext"):
        raise BankValidationError("IBAN is required.")

    acct_in = payload.get("account_number")
    if acct_in:
        norm_acct = re.sub(r"\s", "", str(acct_in))
        if not norm_acct.isalnum():
            raise BankValidationError("Account number must be alphanumeric.")
        write["account_number_ciphertext"] = field_encryption.encrypt(norm_acct)
        write["account_number_last4"] = _last4(norm_acct)

    row = await facility_bank_repo.upsert(facility_id, updated_by_user_id=actor_id, **write)

    await facility_audit_repo.create(
        facility_id=facility_id,
        action="bank_details_created" if before is None else "bank_details_updated",
        actor_id=actor_id, actor_type=actor_type, source_app=source_app,
        before=_audit_snapshot(before), after=_audit_snapshot(row),
    )
    return to_masked(row)
