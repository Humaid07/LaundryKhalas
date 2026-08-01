"""Facility bank details — encryption, masking, validation, ownership, audit.

Security-critical invariants (spec §2/§10/§14):
  * IBAN + account number are encrypted; ciphertext != plaintext; decrypt round-trips.
  * reads are MASKED (no ciphertext, no full values) unless explicitly revealed.
  * audit records only masked identifiers (last 4) — never ciphertext/plaintext.
  * a partner write/reveal is scoped to the caller's own facility (session id),
    and staff cannot edit or reveal banking (403).
  * IBAN validation enforces the UAE format + mod-97 checksum.
DB is mocked — this suite does not hit Postgres.
"""
import pytest
from fastapi import HTTPException

from api import facility as facility_api
from db import database
from schemas import BankDetailsUpsert
from services import facility_bank as fb
from services import field_encryption as fe

VALID_UAE_IBAN = "AE070331234567890123456"


# ------------------------------- encryption --------------------------------
def test_encryption_round_trips_and_hides_plaintext():
    token = fe.encrypt(VALID_UAE_IBAN)
    assert token is not None and token != VALID_UAE_IBAN
    assert VALID_UAE_IBAN not in token
    assert fe.decrypt(token) == VALID_UAE_IBAN


def test_encrypt_none_and_empty_pass_through():
    assert fe.encrypt(None) is None
    assert fe.encrypt("") is None
    assert fe.decrypt(None) is None


# ------------------------------- IBAN validation ---------------------------
def test_valid_uae_iban_passes():
    assert fb.validate_iban(VALID_UAE_IBAN, country="AE") == VALID_UAE_IBAN
    # spaces / lower-case are normalised
    assert fb.validate_iban("ae07 0331 2345 6789 0123 456", country="AE") == VALID_UAE_IBAN


@pytest.mark.parametrize("bad", [
    "",                              # empty
    "AE00033123456789012345",        # bad checksum
    "AE07033123456789012345",        # too short for UAE (22)
    "GB07033123",                    # too short overall
    "1234567890123456789012",        # no country prefix
])
def test_invalid_ibans_rejected(bad):
    with pytest.raises(fb.BankValidationError):
        fb.validate_iban(bad, country="AE")


def test_non_uae_iban_skips_uae_length_rule():
    # A valid German IBAN should pass the generic mod-97 check.
    assert fb.validate_iban("DE89370400440532013000", country="DE") == "DE89370400440532013000"


# ------------------------------- masking -----------------------------------
def test_iban_mask_reveals_only_last4():
    masked = fb.mask_iban("1234", country="AE")
    assert masked.endswith("1234")
    assert masked.startswith("AE")
    assert "•" in masked
    # no other digits leak
    assert sum(c.isdigit() for c in masked) == 4


def test_account_mask_reveals_only_last4():
    assert fb.mask_account_number("9876") == "•••• 9876"
    assert fb.mask_account_number(None) is None


def test_to_masked_never_exposes_ciphertext_or_full_values():
    row = {
        "facility_id": "fac-1", "account_holder_name": "Acme Laundry LLC",
        "bank_name": "Emirates NBD", "swift_bic": "EBILAEAD", "branch_name": "Marina",
        "bank_country": "AE", "currency": "AED",
        "iban_ciphertext": "SECRET-CIPHER", "iban_last4": "3456",
        "account_number_ciphertext": "SECRET-CIPHER-2", "account_number_last4": "7890",
        "created_at": "x", "updated_at": "y",
    }
    out = fb.to_masked(row)
    flat = str(out)
    assert "SECRET-CIPHER" not in flat
    assert "ciphertext" not in out
    assert out["iban_masked"].endswith("3456")
    assert out["has_iban"] is True and out["has_account_number"] is True


def test_audit_snapshot_only_last4():
    snap = fb._audit_snapshot({
        "iban_ciphertext": "CIPHER", "iban_last4": "3456",
        "account_number_ciphertext": "CIPHER2", "account_number_last4": "7890",
        "account_holder_name": "Acme",
    })
    assert "iban_ciphertext" not in snap and "account_number_ciphertext" not in snap
    assert snap["iban_last4"] == "3456"


# ------------------------------- upsert flow -------------------------------
async def test_upsert_encrypts_stores_masked_and_audits(monkeypatch):
    stored = {}
    audits = []

    async def fake_get(_fid):
        return None  # first-time create

    async def fake_upsert(_fid, *, updated_by_user_id=None, **fields):
        stored.update(fields)
        return {"facility_id": _fid, **fields, "created_at": "x", "updated_at": "y"}

    async def fake_audit(**kw):
        audits.append(kw)

    monkeypatch.setattr(fb.facility_bank_repo, "get", fake_get)
    monkeypatch.setattr(fb.facility_bank_repo, "upsert", fake_upsert)
    monkeypatch.setattr(fb.facility_audit_repo, "create", fake_audit)

    result = await fb.upsert(
        "fac-1",
        {"account_holder_name": "Acme Laundry LLC", "bank_name": "Emirates NBD",
         "iban": VALID_UAE_IBAN, "account_number": "0123456789"},
        actor_id="u1", actor_type="partner", source_app="partner_portal",
    )
    # ciphertext stored, NOT the plaintext IBAN
    assert stored["iban_ciphertext"] and stored["iban_ciphertext"] != VALID_UAE_IBAN
    assert stored["iban_last4"] == "3456"
    assert fe.decrypt(stored["iban_ciphertext"]) == VALID_UAE_IBAN
    # response is masked — no plaintext / ciphertext
    assert VALID_UAE_IBAN not in str(result)
    assert result["iban_masked"].endswith("3456")
    # audit recorded created action with masked-only values
    assert audits[0]["action"] == "bank_details_created"
    assert VALID_UAE_IBAN not in str(audits[0])
    assert audits[0]["after"]["iban_last4"] == "3456"


async def test_upsert_requires_holder_and_iban(monkeypatch):
    async def fake_get(_fid):
        return None
    monkeypatch.setattr(fb.facility_bank_repo, "get", fake_get)
    with pytest.raises(fb.BankValidationError):
        await fb.upsert("fac-1", {"bank_name": "X", "iban": VALID_UAE_IBAN}, actor_id="u1")
    with pytest.raises(fb.BankValidationError):
        await fb.upsert("fac-1", {"account_holder_name": "Acme"}, actor_id="u1")


async def test_reveal_decrypts_and_audits_access(monkeypatch):
    audits = []
    cipher = fe.encrypt(VALID_UAE_IBAN)

    async def fake_get(_fid):
        return {"facility_id": _fid, "iban_ciphertext": cipher, "iban_last4": "3456",
                "account_number_ciphertext": None, "account_number_last4": None,
                "bank_country": "AE", "currency": "AED", "created_at": "x", "updated_at": "y"}

    async def fake_audit(**kw):
        audits.append(kw)

    monkeypatch.setattr(fb.facility_bank_repo, "get", fake_get)
    monkeypatch.setattr(fb.facility_audit_repo, "create", fake_audit)

    out = await fb.reveal("fac-1", actor_id="u1", actor_type="internal")
    assert out["iban"] == VALID_UAE_IBAN
    assert audits[0]["action"] == "bank_details_revealed"


# ------------------------------- ownership / RBAC (partner endpoints) ------
async def test_partner_put_is_scoped_to_session_facility(monkeypatch):
    monkeypatch.setattr(database, "is_supabase_mode", lambda: True)
    captured = {}

    async def fake_upsert(fid, payload, **kw):
        captured["fid"] = fid
        return {"facility_id": fid}

    monkeypatch.setattr(facility_api.facility_bank, "upsert", fake_upsert)
    principal = {"facility_id": "mine", "role": "facility_owner", "id": "u1"}
    await facility_api.put_bank_details(BankDetailsUpsert(iban=VALID_UAE_IBAN), principal)
    # facility resolved from the session, never the request body
    assert captured["fid"] == "mine"


async def test_partner_staff_cannot_edit_bank(monkeypatch):
    monkeypatch.setattr(database, "is_supabase_mode", lambda: True)
    principal = {"facility_id": "mine", "role": "facility_staff", "id": "u1"}
    with pytest.raises(HTTPException) as exc:
        await facility_api.put_bank_details(BankDetailsUpsert(iban=VALID_UAE_IBAN), principal)
    assert exc.value.status_code == 403


async def test_partner_staff_cannot_reveal_bank(monkeypatch):
    monkeypatch.setattr(database, "is_supabase_mode", lambda: True)
    principal = {"facility_id": "mine", "role": "facility_staff", "id": "u1"}
    with pytest.raises(HTTPException) as exc:
        await facility_api.reveal_bank_details(principal)
    assert exc.value.status_code == 403
