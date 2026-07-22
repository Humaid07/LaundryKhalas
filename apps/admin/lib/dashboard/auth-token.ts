/**
 * Minimal, dependency-free session storage for the admin dashboard.
 *
 * Kept deliberately separate from the API clients (whatsapp-agent-api.ts,
 * seo-agent-api.ts) and the React auth context so the request layer can read the
 * bearer token without importing React or creating a circular dependency.
 *
 * The token is a signed HS256 JWT issued by the FastAPI backend
 * (`POST /api/auth/login`). It is sent as `Authorization: Bearer <token>` on
 * every guarded `/api/*` call and verified server-side in api/deps.py.
 */
export type UserRole = "admin" | "operations";

export interface AuthUser {
  id: string | null;
  email: string;
  full_name?: string | null;
  role: UserRole;
  market?: string | null;
}

const TOKEN_KEY = "lk-auth-token";
const USER_KEY = "lk-auth-user";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function setSession(token: string, user: AuthUser): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
}
