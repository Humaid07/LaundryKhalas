"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { AuthUser, UserRole } from "./auth-token";
import {
  clearSession,
  fetchAuthConfig,
  fetchMe,
  getStoredUser,
  login as apiLogin,
} from "./auth";

type Status = "loading" | "authed" | "anon";

interface AuthState {
  user: AuthUser | null;
  role: UserRole | null;
  status: Status;
  /** Whether the backend requires login (REQUIRE_AUTH=true). */
  authRequired: boolean;
  login: (email: string, password: string) => Promise<AuthUser>;
  logout: () => void;
}

/** Synthetic facility principal used when the backend runs with
 *  REQUIRE_AUTH=false — mirrors the backend's own dev principal so the whole
 *  workspace works without login during local development. */
const DEV_USER: AuthUser = {
  id: null,
  email: "partner@local",
  full_name: "Facility Partner",
  role: "facility_owner",
  // No hardcoded facility name — the real name comes from the facility profile
  // (`GET /api/facility/me`). Leaving this null lets the header show its loading
  // state, then the live facility name, instead of a static placeholder.
  facility_name: null,
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [authRequired, setAuthRequired] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const cfg = await fetchAuthConfig();
      if (cancelled) return;
      setAuthRequired(cfg.auth_required);

      if (!cfg.auth_required) {
        setUser(DEV_USER);
        setStatus("authed");
        return;
      }

      // Optimistically render the stored user, then confirm with the server.
      const stored = getStoredUser();
      if (stored) setUser(stored);
      const me = await fetchMe();
      if (cancelled) return;
      if (me) {
        setUser(me);
        setStatus("authed");
      } else {
        clearSession();
        setUser(null);
        setStatus("anon");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const u = await apiLogin(email, password);
    setUser(u);
    setAuthRequired(true);
    setStatus("authed");
    return u;
  }, []);

  const logout = useCallback(() => {
    clearSession();
    setUser(null);
    if (typeof window !== "undefined") {
      window.location.href = authRequired ? "/login" : "/";
    }
  }, [authRequired]);

  const value = useMemo<AuthState>(
    () => ({ user, role: user?.role ?? null, status, authRequired, login, logout }),
    [user, status, authRequired, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
