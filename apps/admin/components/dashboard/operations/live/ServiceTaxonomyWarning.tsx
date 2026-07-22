"use client";

import { AlertTriangle } from "lucide-react";
import { Panel, StatusBadge } from "@/components/dashboard/ui/primitives";
import {
  agentApi,
  type ServiceTaxonomyHealth,
} from "@/lib/dashboard/whatsapp-agent-api";
import { LIVE_WHATSAPP_ENABLED, useLiveAgentData } from "./useLiveAgentData";

/** Render a mismatch entry (string or small object) as a readable surface label. */
function mismatchLabel(m: ServiceTaxonomyHealth["mismatches"][number]): string {
  if (typeof m === "string") return m;
  return m.surface ?? m.name ?? m.detail ?? JSON.stringify(m);
}

/**
 * Live guardrail banner: warns operators when the backend reports its service
 * taxonomy has drifted from the canonical catalog (GET /api/service-taxonomy/health,
 * Dashboard → FastAPI). Renders ONLY when the live flag is on AND the backend
 * explicitly reports `in_sync: false`; otherwise (flag off, still loading, fetch
 * failed, or in sync) it renders nothing so healthy pages stay clean.
 */
export function ServiceTaxonomyWarning() {
  const { data, error } = useLiveAgentData<ServiceTaxonomyHealth>(() =>
    agentApi.serviceTaxonomyHealth(),
  );

  if (!LIVE_WHATSAPP_ENABLED) return null;
  if (error || !data || data.in_sync !== false) return null;

  const surfaces = (data.mismatches ?? []).map(mismatchLabel).filter(Boolean);

  return (
    <Panel className="border-danger/40 bg-danger/5">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger" />
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-display text-[0.95rem] font-semibold text-ink">
              Service taxonomy mismatch detected.
            </h3>
            <StatusBadge tone="danger">Action needed</StatusBadge>
          </div>
          <p className="text-xs text-ink-muted">
            {surfaces.length > 0
              ? `Out-of-sync ${surfaces.length === 1 ? "surface" : "surfaces"}: ${surfaces.join(", ")}.`
              : "One or more surfaces have drifted from the canonical service catalog."}
          </p>
        </div>
      </div>
    </Panel>
  );
}
