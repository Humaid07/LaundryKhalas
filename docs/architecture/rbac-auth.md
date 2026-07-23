# Dashboard RBAC & Authentication

> Status: **active** · Updated 2026-07-23 · Applies to the admin dashboard (`apps/admin`) + the active backend (`apps/whatsapp-agent`). The legacy `app/` backend uses only a placeholder shared-key guard and is out of scope.

## Model in one paragraph

The dashboard authenticates against **FastAPI** (never Supabase directly). FastAPI hashes passwords (PBKDF2-HMAC-SHA256, stdlib) and issues **HS256 JWTs**; the frontend stores the JWT and sends it as `Authorization: Bearer <token>` on every guarded `/api/*` call. There are exactly **two roles — `admin` and `operations`** — enforced at the router level on the backend **and** mirrored in the frontend sidebar/guard. Access rules live in one place per side (`services/auth.py` + `main.py` on the backend; `lib/dashboard/roles.ts` on the frontend).

## Roles

| Role | Access |
|------|--------|
| `admin` | Everything — all sections, Settings, **user management**, all approvals. |
| `operations` | `/orders` + `/operations` only (Customer Facing, Facility Facing, Drivers, Customer Orders). No Settings/admin. |

The role set is intentionally small and consistent across the stack — the Settings → Roles & Permissions view renders these exact two roles from `roles.ts`, never an aspirational mock. (The old static 5-role mock was removed on 2026-07-23.)

## Backend (`apps/whatsapp-agent`)

- **`services/auth.py`** — `ROLES = ("admin","operations")`, `hash_password`/`verify_password` (PBKDF2, 200k iters), `create_access_token`/`decode_access_token` (HS256, `sub`/`role`/`email`/`iat`/`exp`).
- **`db/repositories/users_repo.py`** — `get_by_email`, `get_by_id`, `create` (upsert by email), `list_users` (hash-stripped), `set_active`, **`update_user`** (partial: full_name/role/is_active).
- **`api/auth.py`** (`/api/auth`, never guarded) — `GET /config` (`{auth_required}`), `POST /login`, `GET /me`.
- **`api/users.py`** (`/api/users`, **admin-only**) — `GET` (list + roles), `POST` (create, ≥8-char password, 409 on dup), `PATCH /{id}` (role/name/active). **Self-lockout protection**: an admin can't demote or deactivate their own account. Requires `DATABASE_MODE=supabase` (503 otherwise — the users table is Supabase-only).
- **`api/deps.py`** — `current_user` (decode bearer → active user), `require_roles(*roles)` → `require_admin` / `require_ops`. Gated by `REQUIRE_AUTH`: off ⇒ anonymous requests run as a synthetic dev admin; on ⇒ missing token → 401, wrong role → 403.
- **`main.py`** — router-level guards: ops surface (orders/conversations/flags/tickets) = `require_ops`; admin-only (chat/settings/**users**/seo/service-taxonomy) = `require_admin`; open (auth/webhooks/health).
- **DB** — `supabase/migrations/…_000006_auth_users.sql` (users table, roles CHECK, RLS enabled) + **`…_000008_users_rls_hardening.sql`** (REVOKE from anon/authenticated + restrictive deny policy, so password hashes are unreachable via Supabase's public API; the backend service role bypasses RLS).
- **Bootstrap** — `scripts/seed_admin_user.py --email --password --role {admin|operations}` (Supabase mode).

### Turning auth on (staging/production)
Set on the backend: `REQUIRE_AUTH=true`, a long random `JWT_SECRET`, and `DATABASE_MODE=supabase` (with the users table migrated + at least one admin seeded). With `REQUIRE_AUTH=false` (default) the backend admits a synthetic dev admin so local work needs no login. An unset `JWT_SECRET` while `REQUIRE_AUTH=true` makes tokens unverifiable → all requests fail (fail-safe).

## Frontend (`apps/admin`)

- **`lib/dashboard/roles.ts`** — the single source of truth: `ROLES`, `ROLE_LIST`, `roleAllowsRoute`, `roleLabel`. `auth.ts#isRouteAllowed`, the sidebar, the AuthGuard, `UserMenu`, and the Roles UI all derive from it.
- **`lib/dashboard/auth-token.ts`** — JWT + user in `localStorage` (`lk-auth-token` / `lk-auth-user`).
- **`lib/dashboard/auth.ts`** / **`auth-context.tsx`** — `fetchAuthConfig`/`login`/`fetchMe`; `AuthProvider` (`loading`/`authed`/`anon`; injects a synthetic dev admin when `auth_required:false`).
- **`components/dashboard/shell/AuthGuard.tsx`** — redirects `anon` → `/login`, role-forbidden → the role's home. Wraps the whole `(dashboard)` group.
- **`lib/dashboard/users-api.ts`** — admin user-management client. **401 anywhere → clear session + redirect to `/login`** (session-expiry hardening). **503 → `UsersUnavailableError`** so the UI shows a calm "available in auth+Supabase mode" notice.
- **`components/dashboard/settings/UserManagement.tsx`** — real Settings views: **Profile & Team** (your account + live user list: add user, assign role, activate/deactivate, self-row protected) and **Roles & Permissions** (the two roles + live member counts). Gracefully degrades in dev.

## Security posture & known gaps

**Enforced now:** two-role RBAC on both sides; password hashing; signed/expiring JWTs; admin-only user management with self-lockout protection; users table locked to the backend role (RLS + revoke); no card/PII exposure changes.

**Deferred (documented, not yet done):**
- Token is in `localStorage` (XSS-exposed), no refresh token, fixed 12h expiry, no server-side revocation. A move to httpOnly cookies (needs cross-origin `SameSite=None; Secure` + CSRF) is the next hardening step.
- No market-scoped access yet (the `users.market` column exists but guards ignore it).
- No permissions matrix — access is role/router-level, which is sufficient for two roles.
- Richer actors (facility, driver, finance) from CLAUDE.md §1 are future work, not in this two-role model.
