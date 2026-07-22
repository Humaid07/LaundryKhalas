"""Auth primitives — password hashing + signed JWTs, using ONLY the Python
standard library (no external crypto dependency).

Passwords: PBKDF2-HMAC-SHA256 with a per-user random salt, stored as
``pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>``.

Tokens: compact HS256 JWTs (header.payload.signature, base64url) signed with the
backend's ``JWT_SECRET``. These are verified on every dashboard API call by
``api/deps.py``. The dashboard authenticates against FastAPI (never Supabase
directly), matching the project's Dashboard → FastAPI → Supabase architecture.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

ROLES = ("admin", "operations")
_PBKDF2_ITERATIONS = 200_000


# --- passwords --------------------------------------------------------------
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = (stored or "").split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


# --- JWT (HS256) ------------------------------------------------------------
def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64u_decode(seg: str) -> bytes:
    return base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4))


def create_access_token(
    *, subject: str, role: str, email: str, secret: str, expiry_hours: int = 12,
    extra: dict | None = None,
) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": subject, "role": role, "email": email,
               "iat": now, "exp": now + expiry_hours * 3600}
    if extra:
        payload.update(extra)
    signing_input = (
        _b64u_encode(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + _b64u_encode(json.dumps(payload, separators=(",", ":")).encode())
    )
    sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64u_encode(sig)}"


def decode_access_token(token: str | None, *, secret: str) -> dict | None:
    """Return the verified payload, or None if the token is missing, tampered,
    or expired."""
    if not token or not secret:
        return None
    try:
        signing_input, sig_b64 = token.rsplit(".", 1)
        expected = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64u_decode(sig_b64)):
            return None
        _, payload_b64 = signing_input.split(".")
        payload = json.loads(_b64u_decode(payload_b64))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload
