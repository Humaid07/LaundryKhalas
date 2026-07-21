"use client";

import { ArrowLeft, CheckCircle2, XCircle } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api-client";
import type { SettingsStatus } from "@/lib/types";
import { ErrorBanner } from "@/components/ErrorBanner";

function StatusRow({ label, value, tone }: { label: string; value: string; tone?: "good" | "warn" }) {
  return (
    <div className="flex items-center justify-between border-b border-wa-border py-3 last:border-none">
      <span className="text-sm text-wa-muted">{label}</span>
      <span
        className={
          tone === "warn"
            ? "text-sm font-medium text-wa-danger"
            : "text-sm font-medium text-wa-text"
        }
      >
        {value}
      </span>
    </div>
  );
}

export default function SettingsPage() {
  const [status, setStatus] = useState<SettingsStatus | null>(null);
  const [health, setHealth] = useState<"checking" | "ok" | "down">("checking");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getSettingsStatus()
      .then(setStatus)
      .catch((err: unknown) => setError(err instanceof ApiError ? err.detail : "Could not load settings."));

    api
      .getHealth()
      .then(() => setHealth("ok"))
      .catch(() => setHealth("down"));
  }, []);

  return (
    <div className="mx-auto max-w-xl px-6 py-8">
      <Link
        href="/chat"
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-wa-muted hover:text-wa-text"
      >
        <ArrowLeft size={15} /> Back to chat
      </Link>

      <h1 className="text-lg font-semibold text-wa-text">Local Settings</h1>
      <p className="mt-1 text-sm text-wa-muted">
        Read-only status of this standalone WhatsApp Agent. No API keys or secrets are ever shown
        here.
      </p>

      {error && <div className="mt-4"><ErrorBanner message={error} /></div>}

      <div className="mt-6 rounded-lg border border-wa-border bg-white px-4">
        <StatusRow
          label="Backend API health"
          value={health === "checking" ? "Checking…" : health === "ok" ? "Reachable" : "Unreachable"}
          tone={health === "down" ? "warn" : undefined}
        />
        <StatusRow label="Agent mode" value={status?.agent_mode ?? "—"} />
        <StatusRow label="Environment" value={status?.app_env ?? "—"} />
        <StatusRow label="Database" value={status?.database_kind ?? "—"} />
      </div>

      <h2 className="mb-2 mt-6 text-sm font-semibold text-wa-text">LLM Provider</h2>
      <div className="rounded-lg border border-wa-border bg-white px-4">
        <StatusRow label="Configured provider" value={status?.llm_provider ?? "—"} />
        <StatusRow
          label="Live calls ready"
          value={status?.llm_live_ready ? "Yes — API key configured" : "No — using mock"}
          tone={status?.llm_live_ready ? undefined : undefined}
        />
      </div>

      <h2 className="mb-2 mt-6 text-sm font-semibold text-wa-text">WhatsApp Channel</h2>
      <div className="rounded-lg border border-wa-border bg-white px-4">
        <StatusRow label="Configured mode" value={status?.whatsapp_mode ?? "—"} />
        <StatusRow
          label="Live sending ready"
          value={status?.whatsapp_live_ready ? "Yes — Meta credentials configured" : "No — mock only"}
        />
      </div>

      <div className="mt-6 flex items-start gap-2 rounded-lg bg-wa-panel px-4 py-3 text-xs text-wa-muted">
        {status?.llm_live_ready || status?.whatsapp_live_ready ? (
          <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-wa-accent-dark" />
        ) : (
          <XCircle size={16} className="mt-0.5 shrink-0 text-wa-muted" />
        )}
        <span>
          Live mode only activates when the corresponding environment variables are set on the
          backend (never in this UI). This page reflects current backend configuration; it cannot
          change it.
        </span>
      </div>
    </div>
  );
}
