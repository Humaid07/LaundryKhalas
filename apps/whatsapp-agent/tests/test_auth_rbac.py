"""Auth + RBAC tests.

Covers the pure auth primitives (password hashing, JWT round-trip), the role
guards (require_admin / require_ops → 401/403/pass), and that the admin-only
user-management API is Supabase-gated in SQLite dev mode. The users *table*
itself lives only in Supabase, so table-level CRUD is not exercised in the
hermetic SQLite suite (documented behaviour: 503 in SQLite mode).
"""
from starlette.requests import Request

from api import deps
from services import auth as auth_svc


# --------------------------- auth primitives --------------------------------

def test_password_hash_roundtrip():
    h = auth_svc.hash_password("correct horse battery staple")
    assert h.startswith("pbkdf2_sha256$")
    assert auth_svc.verify_password("correct horse battery staple", h) is True
    assert auth_svc.verify_password("wrong password", h) is False
    assert auth_svc.verify_password("x", None) is False


def test_jwt_roundtrip_and_tamper():
    secret = "unit-test-secret"
    token = auth_svc.create_access_token(subject="u1", role="admin", email="a@x.co", secret=secret)
    payload = auth_svc.decode_access_token(token, secret=secret)
    assert payload and payload["sub"] == "u1" and payload["role"] == "admin"
    # Wrong secret → rejected.
    assert auth_svc.decode_access_token(token, secret="other-secret") is None
    # Tampered token → rejected.
    assert auth_svc.decode_access_token(token + "x", secret=secret) is None
    # Missing token / secret → rejected.
    assert auth_svc.decode_access_token(None, secret=secret) is None
    assert auth_svc.decode_access_token(token, secret="") is None


def test_jwt_expired_rejected():
    secret = "unit-test-secret"
    expired = auth_svc.create_access_token(
        subject="u1", role="admin", email="a@x.co", secret=secret, expiry_hours=-1
    )
    assert auth_svc.decode_access_token(expired, secret=secret) is None


# --------------------------- role guards ------------------------------------

class _AuthOnSettings:
    """Minimal stand-in for Settings with auth enforced and a known secret."""
    require_auth = True
    jwt_secret_effective = "guard-test-secret"


def _request(token: str | None = None) -> Request:
    headers = [(b"authorization", f"Bearer {token}".encode())] if token else []
    return Request({"type": "http", "headers": headers})


async def test_require_admin_rejects_anonymous(monkeypatch):
    monkeypatch.setattr(deps, "get_settings", lambda: _AuthOnSettings())
    try:
        await deps.require_admin(_request(None))
        assert False, "expected 401"
    except Exception as exc:  # HTTPException
        assert getattr(exc, "status_code", None) == 401


async def test_require_admin_rejects_operations_role(monkeypatch):
    monkeypatch.setattr(deps, "get_settings", lambda: _AuthOnSettings())
    ops_token = auth_svc.create_access_token(
        subject="u2", role="operations", email="o@x.co", secret="guard-test-secret"
    )
    try:
        await deps.require_admin(_request(ops_token))
        assert False, "expected 403"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403


async def test_require_admin_allows_admin(monkeypatch):
    monkeypatch.setattr(deps, "get_settings", lambda: _AuthOnSettings())
    admin_token = auth_svc.create_access_token(
        subject="u3", role="admin", email="a@x.co", secret="guard-test-secret"
    )
    user = await deps.require_admin(_request(admin_token))
    assert user["role"] == "admin"


async def test_require_ops_allows_operations_and_admin(monkeypatch):
    monkeypatch.setattr(deps, "get_settings", lambda: _AuthOnSettings())
    for role in ("operations", "admin"):
        tok = auth_svc.create_access_token(
            subject="u", role=role, email=f"{role}@x.co", secret="guard-test-secret"
        )
        user = await deps.require_ops(_request(tok))
        assert user["role"] == role


# --------------------------- /api/users gating ------------------------------

async def test_users_api_requires_supabase_in_sqlite(client):
    # Default test env: REQUIRE_AUTH=false → dev-admin principal passes the guard,
    # then the endpoint reports it needs Supabase mode (users table is Supabase-only).
    r = await client.get("/api/users")
    assert r.status_code == 503
    assert "supabase" in r.json()["detail"].lower()

    r2 = await client.post("/api/users", json={"email": "x@y.co", "password": "longenough"})
    assert r2.status_code == 503

    r3 = await client.patch("/api/users/some-id", json={"is_active": False})
    assert r3.status_code == 503
