/**
 * Admin user-management client → FastAPI `/api/users` (admin-only, JWT-guarded).
 *
 * The users table lives only in the dev/test Supabase project, so when the
 * backend runs in local SQLite/dev mode these endpoints return 503 — surfaced
 * here as `UsersUnavailableError` so the UI can show a calm "available in
 * auth+Supabase mode" notice instead of an error.
 *
 * A 401 anywhere means the session expired → clear it and bounce to /login
 * (session-expiry hardening; the backend is the real gate, this is UX).
 */
import { getToken, clearSession, type UserRole } from "./auth-token";

const BASE_URL =
  process.env.NEXT_PUBLIC_WHATSAPP_AGENT_API_URL ?? "http://localhost:8101";

export interface ManagedUser {
  id: string;
  email: string;
  full_name?: string | null;
  role: UserRole;
  is_active: boolean;
  market?: string | null;
}

export interface NewUser {
  email: string;
  password: string;
  full_name?: string | null;
  role: UserRole;
}

export interface UserPatch {
  full_name?: string;
  role?: UserRole;
  is_active?: boolean;
}

export class UsersApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** Raised when user management is unavailable (backend not in auth+Supabase mode). */
export class UsersUnavailableError extends UsersApiError {}

async function detail(res: Response): Promise<string> {
  try {
    return (await res.json()).detail ?? `Request failed (${res.status}).`;
  } catch {
    return `Request failed (${res.status}).`;
  }
}

async function authed(path: string, init?: RequestInit): Promise<Response> {
  const token = getToken();
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
  } catch {
    throw new UsersApiError(0, "Could not reach the server. Is the backend running?");
  }
  if (res.status === 401) {
    clearSession();
    if (typeof window !== "undefined") window.location.assign("/login");
    throw new UsersApiError(401, "Your session has expired. Please sign in again.");
  }
  if (res.status === 503) {
    throw new UsersUnavailableError(503, await detail(res));
  }
  return res;
}

export async function listUsers(): Promise<{ users: ManagedUser[]; roles: UserRole[] }> {
  const res = await authed("/api/users");
  if (!res.ok) throw new UsersApiError(res.status, await detail(res));
  return res.json();
}

export async function createUser(input: NewUser): Promise<ManagedUser> {
  const res = await authed("/api/users", { method: "POST", body: JSON.stringify(input) });
  if (!res.ok) throw new UsersApiError(res.status, await detail(res));
  return res.json();
}

export async function updateUser(id: string, patch: UserPatch): Promise<ManagedUser> {
  const res = await authed(`/api/users/${id}`, { method: "PATCH", body: JSON.stringify(patch) });
  if (!res.ok) throw new UsersApiError(res.status, await detail(res));
  return res.json();
}
