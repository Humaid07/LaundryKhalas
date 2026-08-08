"use client";

import { useQuery } from "@tanstack/react-query";
import { facilityApi } from "@/lib/api-client";
import { getDevFacilityId, setDevFacilityId } from "@/lib/auth-token";

/**
 * FacilitySwitcher — dev-only dropdown to view the dashboard as any facility.
 *
 * The list comes from `GET /api/facility/switchable`, which returns [] when the
 * backend has auth on (production) — so this control renders nothing there and
 * is purely a local testing convenience. Selecting a facility stores its id
 * (sent as `X-Facility-Id` on every request) and reloads so all data refetches.
 *
 * `currentId` is the facility currently in scope (from the live profile), used
 * to show the right option selected before any manual switch has been made.
 */
export function FacilitySwitcher({ currentId }: { currentId?: string }) {
  const { data: facilities = [] } = useQuery({
    queryKey: ["facility", "switchable"],
    queryFn: () => facilityApi.switchableFacilities(),
    staleTime: 5 * 60_000,
  });

  // Nothing to switch between (production, or a single facility): stay hidden.
  if (facilities.length < 2) return null;

  const selected = getDevFacilityId() ?? currentId ?? "";

  function onChange(id: string) {
    setDevFacilityId(id || null);
    // Full reload → every react-query cache refetches under the new facility.
    window.location.reload();
  }

  return (
    <label className="hidden items-center gap-1.5 sm:flex" title="Dev: view as facility">
      <span className="text-xxs font-semibold uppercase tracking-wide text-ink-muted">Dev</span>
      <select
        aria-label="Switch facility (dev)"
        value={selected}
        onChange={(e) => onChange(e.target.value)}
        className="max-w-[13rem] truncate rounded-md border border-border bg-surface px-2 py-1 text-xs font-medium text-ink outline-none transition-colors hover:border-border-strong focus:border-border-strong"
      >
        {facilities.map((f) => (
          <option key={f.id} value={f.id}>
            {f.name}
            {f.city ? ` — ${f.city}` : ""}
          </option>
        ))}
      </select>
    </label>
  );
}
