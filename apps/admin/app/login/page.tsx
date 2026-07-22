"use client";

import { Suspense, useEffect, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2, LockKeyhole } from "lucide-react";
import { BrandWordmark } from "@/components/dashboard/shell/Brand";
import { useAuth } from "@/lib/dashboard/auth-context";
import { homeRouteFor } from "@/lib/dashboard/auth";
import { AuthError } from "@/lib/dashboard/auth";

function LoginForm() {
  const { status, role, authRequired, login } = useAuth();
  const router = useRouter();
  const search = useSearchParams();
  const next = search.get("next");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Already signed in (or auth disabled) → leave the login screen.
  useEffect(() => {
    if (status === "authed") {
      const dest = next && next.startsWith("/") ? next : homeRouteFor(role);
      router.replace(dest);
    }
  }, [status, role, next, router]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const u = await login(email.trim(), password);
      const dest = next && next.startsWith("/") ? next : homeRouteFor(u.role);
      router.replace(dest);
    } catch (err) {
      setError(err instanceof AuthError ? err.message : "Something went wrong. Please try again.");
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex justify-center">
          <BrandWordmark collapsed={false} />
        </div>

        <div className="rounded-2xl border border-border bg-surface p-6 shadow-pop">
          <div className="mb-5 flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-rose/12 text-rose">
              <LockKeyhole className="h-4 w-4" />
            </span>
            <div>
              <h1 className="font-display text-base font-semibold text-ink">Sign in</h1>
              <p className="text-xs text-ink-faint">Operations Command Center</p>
            </div>
          </div>

          {authRequired === false && (
            <p className="mb-4 rounded-lg border border-border bg-surface-2 px-3 py-2 text-xs text-ink-muted">
              Authentication is currently disabled on this environment — you can open the
              dashboard directly.
            </p>
          )}

          <form onSubmit={onSubmit} className="space-y-3.5">
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-ink-muted">Email</span>
              <input
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="h-10 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none"
                placeholder="you@laundrykhalas.com"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-ink-muted">Password</span>
              <input
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-10 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none"
                placeholder="••••••••"
              />
            </label>

            {error && (
              <p role="alert" className="rounded-lg border border-rose/30 bg-rose/8 px-3 py-2 text-xs font-medium text-rose">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-rose text-sm font-semibold text-white transition-colors hover:bg-rose/90 disabled:opacity-60"
            >
              {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
              {submitting ? "Signing in…" : "Sign in"}
            </button>
          </form>
        </div>

        <p className="mt-6 text-center text-xxs text-ink-faint">
          LaundryKhalas — internal operations. Access is restricted and audited.
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
