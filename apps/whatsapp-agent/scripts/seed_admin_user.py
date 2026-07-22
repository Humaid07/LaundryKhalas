"""Create (or update) a dashboard login user in the Supabase `public.users`
table — the way you bootstrap the first admin so the dashboard can authenticate
when REQUIRE_AUTH=true.

This is NOT demo/operational data (spec §4.4) — `users` is reference/access
data, so this script is intentionally separate from seed_demo_data and is safe
to run against staging to create real operator accounts. Passwords are hashed
with PBKDF2-HMAC-SHA256 (services/auth.hash_password); the plaintext is never
stored. `users_repo.create` upserts by email, so re-running rotates the password.

Requires DATABASE_MODE=supabase and migration 20260722_000006_auth_users applied.

Usage (from apps/whatsapp-agent):
    python scripts/seed_admin_user.py --email admin@laundrykhalas.com \\
        --password 'S0me-Strong-Pass' --role admin --name "Ops Admin"
    python scripts/seed_admin_user.py --email ops@laundrykhalas.com \\
        --password 'S0me-Strong-Pass' --role operations --market AE
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import database  # noqa: E402
from db.repositories import users_repo  # noqa: E402
from services.auth import ROLES, hash_password  # noqa: E402
from settings import get_settings  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser(description="Create/update a dashboard login user.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--role", default="admin", choices=list(ROLES))
    parser.add_argument("--name", default=None, help="Full name (optional).")
    parser.add_argument("--market", default=None, help="Optional market scope (e.g. AE).")
    args = parser.parse_args()

    settings = get_settings()
    if not database.is_supabase_mode():
        print("Refusing: DATABASE_MODE must be 'supabase' to create dashboard users.")
        return 1
    if len(args.password) < 8:
        print("Refusing: password must be at least 8 characters.")
        return 1

    print(
        f"Target Supabase (app_env={settings.app_env}, "
        f"database_env={getattr(settings, 'database_env', '?')}). "
        f"Creating/updating {args.role} user {args.email} …"
    )
    try:
        # Fail clearly if the users table isn't there yet.
        has_users = await database.fetchval(
            "select to_regclass('public.users') is not null"
        )
        if not has_users:
            print("public.users not found. Apply migration 000006 first (supabase db push).")
            return 1
        user = await users_repo.create(
            email=args.email,
            password_hash=hash_password(args.password),
            full_name=args.name,
            role=args.role,
            market=args.market,
            created_by_seed=True,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to create user: {exc}")
        return 1
    finally:
        await database.close_pool()

    print(f"Done. User id={user['id']} email={user['email']} role={user['role']} active={user['is_active']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
