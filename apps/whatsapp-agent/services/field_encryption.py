"""Reversible field-level encryption for sensitive facility data (bank details).

The project stores passwords with one-way PBKDF2 (services/auth.py), but bank
details must be *decryptable* by authorized users (the explicit reveal action),
so a symmetric cipher is required. Python's stdlib ships no symmetric cipher, so
this uses Fernet (AES-128-CBC + HMAC-SHA256 authenticated encryption) from the
`cryptography` package — the same library the ecosystem standardises on.

Key handling:
  * The Fernet key is DERIVED from ``settings.bank_encryption_secret_effective``
    via SHA-256, so the operator can supply any long random ``BANK_ENCRYPTION_KEY``
    (not necessarily a raw 32-byte Fernet key). In dev it falls back to the JWT
    secret so the feature works without extra config.
  * If no secret is configured (require_auth=true with BANK_ENCRYPTION_KEY unset),
    encryption/decryption RAISE rather than silently storing plaintext — fail-safe.

Only ciphertext is ever persisted; plaintext lives in memory for the duration of
a request and is never logged (see services/facility_bank.py for masking + audit).
"""
from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from settings import get_settings


class EncryptionUnavailable(RuntimeError):
    """Raised when no encryption secret is configured (never store plaintext)."""


class DecryptionError(RuntimeError):
    """Raised when a stored value cannot be decrypted (wrong/rotated key or tamper)."""


def _fernet_key_from_secret(secret: str) -> bytes:
    # SHA-256 → 32 bytes → url-safe base64 = a valid Fernet key derived from any
    # passphrase. Deterministic, so the same secret always yields the same key.
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache(maxsize=4)
def _fernet_for(secret: str) -> Fernet:
    return Fernet(_fernet_key_from_secret(secret))


def _fernet() -> Fernet:
    secret = get_settings().bank_encryption_secret_effective
    if not secret:
        raise EncryptionUnavailable(
            "No bank encryption secret configured. Set BANK_ENCRYPTION_KEY "
            "(required when REQUIRE_AUTH=true) before storing bank details."
        )
    return _fernet_for(secret)


def encrypt(plaintext: str | None) -> str | None:
    """Encrypt a plaintext string → an opaque token (str). None/empty → None."""
    if plaintext is None or plaintext == "":
        return None
    token = _fernet().encrypt(plaintext.encode("utf-8"))
    return token.decode("ascii")


def decrypt(token: str | None) -> str | None:
    """Decrypt a token produced by ``encrypt`` → plaintext. None → None."""
    if token is None or token == "":
        return None
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:  # wrong key, rotated secret, or tampered value
        raise DecryptionError("Stored value could not be decrypted.") from exc


def is_available() -> bool:
    """True when an encryption secret is configured (feature usable)."""
    return bool(get_settings().bank_encryption_secret_effective)
