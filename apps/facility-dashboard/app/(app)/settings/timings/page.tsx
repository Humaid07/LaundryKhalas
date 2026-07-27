"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Check, Plus, X } from "lucide-react";
import { facilityApi, type FacilityTiming } from "@/lib/api-client";
import { SettingsHeader } from "@/components/settings/SettingsHeader";
import { SectionCard } from "@/components/shared/SectionCard";
import { Switch } from "@/components/ui/Switch";
import { Button } from "@/components/ui/Button";
import { LoadingState, ErrorState } from "@/components/ui/states";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export default function TimingsSettingsPage() {
  const qc = useQueryClient();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["facility", "settings", "timings"],
    queryFn: () => facilityApi.getTimings(),
  });

  const [rows, setRows] = useState<FacilityTiming[]>([]);
  const [blackouts, setBlackouts] = useState<string[]>([]);
  const [newBlackout, setNewBlackout] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!data) return;
    // Ensure a row exists per weekday, preserving any values the backend sent.
    const byDay = new Map((data ?? []).map((t) => [t.day, t]));
    setRows(
      DAYS.map(
        (d) => byDay.get(d) ?? { day: d, open: "09:00", close: "21:00", closed: false },
      ),
    );
  }, [data]);

  const mutation = useMutation({
    mutationFn: () => facilityApi.updateTimings({ timings: rows, blackout_dates: blackouts }),
    onSuccess: () => {
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      qc.invalidateQueries({ queryKey: ["facility", "settings", "timings"] });
    },
  });

  const update = (day: string, patch: Partial<FacilityTiming>) =>
    setRows((rs) => rs.map((r) => (r.day === day ? { ...r, ...patch } : r)));

  return (
    <div className="lk-enter space-y-5">
      <SettingsHeader title="Timings" description="Your weekly operating hours and closures." />

      {isLoading ? (
        <LoadingState label="Loading timings…" />
      ) : isError ? (
        <ErrorState description="Could not load timings." onRetry={() => refetch()} />
      ) : (
        <>
          <SectionCard title="Weekly hours">
            <ul className="divide-y divide-border/60">
              {rows.map((r) => (
                <li key={r.day} className="flex flex-wrap items-center gap-3 py-3 first:pt-0 last:pb-0">
                  <span className="w-24 shrink-0 text-sm font-medium text-ink">{r.day}</span>
                  {r.closed ? (
                    <span className="flex-1 text-sm text-ink-muted">Closed</span>
                  ) : (
                    <div className="flex flex-1 items-center gap-2">
                      <input
                        type="time"
                        value={r.open ?? ""}
                        onChange={(e) => update(r.day!, { open: e.target.value })}
                        className="h-10 rounded-lg border border-border bg-canvas px-2 text-sm text-ink focus:border-rose focus-visible:outline-none"
                      />
                      <span className="text-ink-faint">–</span>
                      <input
                        type="time"
                        value={r.close ?? ""}
                        onChange={(e) => update(r.day!, { close: e.target.value })}
                        className="h-10 rounded-lg border border-border bg-canvas px-2 text-sm text-ink focus:border-rose focus-visible:outline-none"
                      />
                    </div>
                  )}
                  <label className="flex shrink-0 items-center gap-2 text-xs text-ink-muted">
                    <span>Open</span>
                    <Switch checked={!r.closed} onChange={(on) => update(r.day!, { closed: !on })} />
                  </label>
                </li>
              ))}
            </ul>
          </SectionCard>

          <SectionCard title="Blackout dates">
            <div className="mb-3 flex flex-wrap gap-2">
              {blackouts.length === 0 && <p className="text-sm text-ink-muted">No blackout dates set.</p>}
              {blackouts.map((d) => (
                <span
                  key={d}
                  className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-2 px-2.5 py-1 text-xs font-medium text-ink"
                >
                  {d}
                  <button
                    type="button"
                    onClick={() => setBlackouts((b) => b.filter((x) => x !== d))}
                    aria-label={`Remove ${d}`}
                    className="text-ink-faint hover:text-danger"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                type="date"
                value={newBlackout}
                onChange={(e) => setNewBlackout(e.target.value)}
                className="h-11 flex-1 rounded-lg border border-border bg-canvas px-3 text-sm text-ink focus:border-rose focus-visible:outline-none"
              />
              <Button
                variant="secondary"
                size="lg"
                disabled={!newBlackout || blackouts.includes(newBlackout)}
                onClick={() => {
                  setBlackouts((b) => [...b, newBlackout]);
                  setNewBlackout("");
                }}
              >
                <Plus className="h-4 w-4" /> Add
              </Button>
            </div>
          </SectionCard>

          <div className="flex items-center gap-3">
            <Button variant="primary" size="lg" disabled={mutation.isPending} onClick={() => mutation.mutate()}>
              {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Save changes
            </Button>
            {saved && (
              <span className="inline-flex items-center gap-1 text-xs font-medium text-success">
                <Check className="h-3.5 w-3.5" /> Saved
              </span>
            )}
          </div>
        </>
      )}
    </div>
  );
}
