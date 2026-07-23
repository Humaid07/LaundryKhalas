# Build Report — Dashboard RBAC / Auth (complete & harden)

**Date:** 2026-07-23
**Branch:** main
**Related:** [[rbac-auth]]

## 1. Task objective
Deliver the outstanding P0 "dashboard RBAC/auth" before production. On investigation, real auth **already existed** (JWT + PBKDF2 backend, functional `/login`, `AuthGuard`, role-gated sidebar) — so the task became **complete + harden the RBAC**: keep the real 2 roles (admin, operations), make everything consistent, add functional user/role management, and do production hardening.

## 2. Decisions taken (owner)
- **Role model:** keep the 2 real roles (admin, operations); make consistent; no new permissions table.
- **Focus:** both — functional user/role management **and** hardening.

## 3. What was built
**Backend (`apps/whatsapp-agent`):** admin-only user-management API (`/api/users` list/create/update) with self-lockout protection; a `users_repo.update_user` partial update; `UserCreate`/`UserUpdate` schemas; router wired with `require_admin`; a users-table RLS/privilege hardening migration.
**Frontend (`apps/admin`):** a single role source of truth (`roles.ts`); a user-management client (`users-api.ts`) with 401→logout + graceful 503 handling; real Settings → **Profile & Team** (live users: add/assign-role/activate-deactivate) and **Roles & Permissions** (the 2 real roles + live counts) replacing the static 5-role mock; `auth.ts`/`UserMenu` refactored onto `roles.ts`.
**Docs/config:** RBAC doc; admin `.env.example` cleanup (removed the obsolete `NEXT_PUBLIC_ADMIN_API_KEY`, documented the JWT flow).

## 4. Files created
- `apps/whatsapp-agent/api/users.py`
- `apps/whatsapp-agent/tests/test_auth_rbac.py`
- `supabase/migrations/20260723_000008_users_rls_hardening.sql`
- `apps/admin/lib/dashboard/roles.ts`
- `apps/admin/lib/dashboard/users-api.ts`
- `apps/admin/components/dashboard/settings/UserManagement.tsx`
- `docs/architecture/rbac-auth.md`, this build report.

## 5. Files modified
- `apps/whatsapp-agent/db/repositories/users_repo.py` (`update_user`, `_public_by_id`)
- `apps/whatsapp-agent/schemas.py` (`UserCreate`, `UserUpdate`)
- `apps/whatsapp-agent/main.py` (import + include `users` router with `require_admin`)
- `apps/admin/lib/dashboard/auth.ts` (`isRouteAllowed` → `roles.ts`)
- `apps/admin/components/dashboard/settings/Settings.tsx` (wire real Profile/Users + Roles panels; drop mock imports)
- `apps/admin/components/dashboard/shell/UserMenu.tsx` (use `roleLabel` from `roles.ts`)
- `apps/admin/.env.example`

## 6. API endpoints added/changed
Added `GET /api/users`, `POST /api/users`, `PATCH /api/users/{id}` — all **admin-only** and **Supabase-mode-required** (503 in SQLite dev). No existing endpoints changed.

## 7. Database tables/models added/changed
No table added. New migration `…_000008_users_rls_hardening.sql`: `REVOKE ALL ON users FROM anon, authenticated` + a restrictive deny-all policy for those roles (password hashes unreachable via Supabase's public API; the backend service role bypasses RLS). Additive + idempotent; targets the dev/test Supabase project only.

## 8. UI pages/components added/changed
Settings → **Profile & Team** and **Roles & Permissions** are now real, RBAC-backed views (were static mock). `roles.ts` is the shared source; `UserMenu` role label and route-gating derive from it.

## 9. Agent behavior / integrations
None. No LLM/WhatsApp/Stripe changes.

## 10. What is mock-only vs live
- **Live/real:** the auth + RBAC machinery (hashing, JWT, guards, `/api/users`), the roles source of truth, and the Settings user-management UI when the backend runs with `REQUIRE_AUTH=true` + `DATABASE_MODE=supabase`.
- **Dev default:** `REQUIRE_AUTH=false` admits a synthetic dev admin; `/api/users` returns 503 in SQLite mode and the UI shows a calm "available in auth+Supabase mode" notice.

## 11. Tests run & results
- **Backend:** new `tests/test_auth_rbac.py` — **8 tests pass** (password hash/verify, JWT round-trip/tamper/expiry, `require_admin`/`require_ops` → 401/403/pass, `/api/users` → 503 in SQLite). Full suite: **349 passed, 13 pre-existing failures** (booking/service-catalogue tests that fail identically with my changes reverted — caused by the earlier 000007 service-catalogue work not seeding the catalogue in the SQLite suite; **not** introduced here).
- **Frontend:** `tsc --noEmit` = **0 errors**. Playwright-verified both new Settings pages render with **0 page errors**; backend `/api/users` returns the expected 503 in SQLite mode; the graceful notice + real Profile render correctly.

## 12. Bugs/issues found
- Discovered the 13 pre-existing booking/service-catalogue test failures on `main` (SQLite suite doesn't seed the service catalogue the booking FSM now needs) — out of scope here; flagged for a follow-up.
- Backend won't start in SQLite mode if `.env` sets a Postgres `DATABASE_URL` unless `DATABASE_URL` is also overridden (verification note, not a code change).

## 13. Known limitations
- Token in `localStorage` (no refresh/revocation, 12h expiry) — httpOnly-cookie migration is the next hardening step (documented in [[rbac-auth]]).
- `users.market` exists but market-scoped access is not enforced.
- User management works only in Supabase mode (users table is Supabase-only).

## 14. Security/privacy notes
- Two-role RBAC enforced on **both** backend (401/403) and frontend (guard/sidebar) — hiding nav is never the only defence.
- Passwords PBKDF2-hashed, never returned by the API (`_public` strips the hash). Self-lockout protection prevents removing the last admin by accident. Users table locked to the backend role via RLS + revoke.
- No secrets committed; `.env.example` documents names only.

## 15. Commands to run
```
# backend tests
cd apps/whatsapp-agent && ./.venv/Scripts/python.exe -m pytest tests/test_auth_rbac.py -q
# frontend typecheck
cd apps/admin && npm run typecheck
# seed an admin (Supabase mode)
cd apps/whatsapp-agent && python scripts/seed_admin_user.py --email you@laundrykhalas.com --password '…' --role admin
```

## 16. How to verify manually
With `REQUIRE_AUTH=true` + `DATABASE_MODE=supabase` and a seeded admin: sign in at `/login`; open Settings → Profile & Team → add a user, assign a role, deactivate one (your own row's role/deactivate are disabled); open Roles & Permissions → see the two roles + live member counts. As an `operations` user, confirm the sidebar shows only Orders + Operations and other routes redirect.

## 17. Next recommended step
Token-storage hardening (httpOnly cookie + refresh/revocation), then optionally market-scoped access. Separately: fix the pre-existing SQLite service-catalogue test seeding so the full backend suite is green again.
