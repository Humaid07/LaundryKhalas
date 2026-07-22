"use client";

import { useCallback, useEffect, useState } from "react";
import { AgentApiError } from "@/lib/dashboard/whatsapp-agent-api";

/**
 * Live-data feature flag. When NEXT_PUBLIC_USE_LIVE_WHATSAPP_INBOX=true the
 * dashboard fetches real backend/Supabase data THROUGH FastAPI (never Supabase
 * directly). Off (default) → the live panels render nothing and the existing
 * demo surfaces are untouched.
 */
export const LIVE_WHATSAPP_ENABLED =
  process.env.NEXT_PUBLIC_USE_LIVE_WHATSAPP_INBOX === "true";

export interface LiveState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/**
 * Small fetch hook for the live panels: loading / error / data + a manual
 * refresh. `fetcher` should call one of the `agentApi` methods (Dashboard →
 * FastAPI → Supabase). Errors are surfaced as a friendly message, never thrown.
 */
export function useLiveAgentData<T>(fetcher: () => Promise<T>, deps: unknown[] = []): LiveState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const refresh = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    if (!LIVE_WHATSAPP_ENABLED) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetcher()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message =
          err instanceof AgentApiError
            ? err.message
            : "Could not load live data from the WhatsApp agent backend.";
        setError(message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nonce, ...deps]);

  return { data, loading, error, refresh };
}
