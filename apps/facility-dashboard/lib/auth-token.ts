/**
 * Minimal, dependency-free session storage for the facility dashboard.
 *
 * Kept deliberately separate from the API client (api-client.ts) and the React
 * auth context so the request layer can read the bearer token without importing
 * React or creating a circular dependency.
 *
 * The token is a signed HS256 JWT issued by the FastAPI backend
 * (`POST /api/auth/login`). It is sent as `Authorization: Bearer <token>` on
 * every guarded `/api/*` call and verified server-side.
 */
export type UserRole =
  | "admin"
  | "operations"
  | "facility_owner"
  | "facility_manager"
  | "facility_staff"
  | "facility_driver";

export interface AuthUser {
  id: string | null;
  email: string;
  full_name?: string | null;
  role: UserRole;
  market?: string | null;
  /** Facility this user belongs to (facility_* roles). */
  facility_id?: string | null;
  facility_name?: string | null;
}

const TOKEN_KEY = "lk-facility-auth-token";
const USER_KEY = "lk-facility-auth-user";

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
