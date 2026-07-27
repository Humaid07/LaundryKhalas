"use client";

import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { homeRouteFor, isRouteAllowed } from "@/lib/auth";

function FullScreen({ label }: { label: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas">
      <div className="flex items-center gap-2.5 text-sm text-ink-muted">
        <Loader2 className="h-4 w-4 animate-spin text-rose" />
        {label}
      </div>
    </div>
  );
}

/**
 * Client-side gate for the whole app route group.
 * - Unauthenticated (auth required, no valid token) → redirect to /login.
 * - Authenticated but role-forbidden route → redirect to the role's home.
 * - While the session resolves, show a full-screen spinner.
 * Backend independently enforces auth on every guarded /api/* call.
 */
export function AuthGuard({ children }: { children: ReactNode }) {
  const { status, role } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const forbidden = status === "authed" && role !== null && !isRouteAllowed(role, pathname);

  useEffect(() => {
    if (status === "anon") {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    } else if (forbidden) {
      router.replace(homeRouteFor(role));
    }
  }, [status, forbidden, role, pathname, router]);

  if (status === "loading") return <FullScreen label="Loading your workspace…" />;
  if (status === "anon") return <FullScreen label="Redirecting to sign in…" />;
  if (forbidden) return <FullScreen label="Redirecting…" />;
  return <>{children}</>;
}
