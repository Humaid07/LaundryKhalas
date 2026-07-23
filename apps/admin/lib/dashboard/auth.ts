/**
 * Auth network calls + pure route-access helpers for the admin dashboard.
 *
 * The dashboard authenticates against the FastAPI backend (never Supabase
 * directly), matching the project's Dashboard → FastAPI → Supabase architecture.
 * When the backend runs with REQUIRE_AUTH=false (local dev) `/api/auth/config`
 * reports `auth_required: false` and the UI skips the login wall entirely.
 */
import {
  type AuthUser,
  type UserRole,
  clearSession,
  getStoredUser,
  getToken,
  setSession,
} from "./auth-token";
import { roleAllowsRoute } from "./roles";

export { type AuthUser, type UserRole, clearSession, getStoredUser, getToken };

const BASE_URL =
  process.env.NEXT_PUBLIC_WHATSAPP_AGENT_API_URL ?? "http://localhost:8101";

export interface AuthConfig {
  auth_required: boolean;
}

interface LoginResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export class AuthError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** Whether the backend requires login. Unreachable backend → treat as not
 *  required, so a broken/off backend never traps the operator behind a login
 *  screen it cannot satisfy (the API calls surface their own errors instead). */
export async function fetchAuthConfig(): Promise<AuthConfig> {
  try {
    const res = await fetch(`${BASE_URL}/api/auth/config`);
    if (!res.ok) return { auth_required: false };
    return (await res.json()) as AuthConfig;
  } catch {
    return { auth_required: false };
  }
}

export async function login(email: string, password: string): Promise<AuthUser> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
  } catch {
    throw new AuthError(0, "Could not reach the server. Is the backend running?");
  }
  if (!res.ok) {
    let detail = "Invalid email or password.";
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new AuthError(res.status, detail);
  }
  const data = (await res.json()) as LoginResponse;
  setSession(data.access_token, data.user);
  return data.user;
}

/** Verify the stored token against the backend and return the live user, or
 *  null if there is no token or it is invalid/expired. */
export async function fetchMe(): Promise<AuthUser | null> {
  const token = getToken();
  if (!token) return null;
  try {
    const res = await fetch(`${BASE_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return null;
    return (await res.json()) as AuthUser;
  } catch {
    return null;
  }
}

// --- Route access (spec §25) -----------------------------------------------
// Access rules live in ONE place — lib/dashboard/roles.ts — so the sidebar, the
// AuthGuard, and the Settings → Roles & Permissions view can never disagree.
// Enforced in the UI by AuthGuard/Sidebar AND independently on the backend by
// api/deps.require_roles — hiding nav is never the only line of defence.
export function isRouteAllowed(role: UserRole, pathname: string): boolean {
  return roleAllowsRoute(role, pathname);
}

export function homeRouteFor(role: UserRole | null): string {
  return role === "operations" ? "/orders" : "/overview";
}
