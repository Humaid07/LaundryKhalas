"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Star, Loader2, Truck, X, Pencil } from "lucide-react";
import { DetailSectionCard } from "@/components/dashboard/minimal/DetailSectionCard";
import { Button } from "@/components/dashboard/ui/Button";
import {
  getRatingFactors, getFacilityRating, listFacilityEvaluations,
  createFacilityEvaluation, updateFacilityEvaluation, getFacilityDrivers,
  getDriverRating, createDriverEvaluation,
  type RatingFactorDef, type RatingSummary, type InternalEvaluation,
  type EvaluationInput, type DriverRow,
} from "@/lib/dashboard/ratings-api";

const inputCls = "h-9 w-full rounded-md border border-border bg-canvas px-2 text-xs text-ink focus:border-rose focus-visible:outline-none";

/* ------------------------------- helpers ---------------------------------- */
function previewOverall(scores: Record<string, number>, defs: RatingFactorDef[]): number | null {
  const used = defs.filter((d) => scores[d.key] != null);
  if (used.length === 0) return null;
  const tw = used.reduce((s, d) => s + d.weight, 0);
  const ws = used.reduce((s, d) => s + scores[d.key] * d.weight, 0);
  return tw > 0 ? Math.round((ws / tw) * 10) / 10 : null;
}

function ScoreBar({ value, max = 5 }: { value: number | null; max?: number }) {
  const pct = value == null ? 0 : Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
      <div className="h-full rounded-full bg-accent-orange transition-all" style={{ width: `${pct}%` }} />
    </div>
  );
}

/* -------------------------- rating summary card --------------------------- */
function RatingSummaryView({ summary, max }: { summary: RatingSummary; max: number }) {
  if (!summary || summary.evaluation_count === 0) {
    return (
      <p className="rounded-lg border border-dashed border-border bg-canvas px-4 py-6 text-center text-xs text-ink-muted">
        No performance ratings are available yet. Ratings will appear after an internal evaluation is completed.
      </p>
    );
  }
  return (
    <div className="space-y-4">
      <div className="flex items-end gap-3">
        <span className="text-3xl font-semibold text-ink">{summary.overall_score?.toFixed(1)}</span>
        <span className="pb-1 text-xs text-ink-faint">/ {max}</span>
        <span className="ml-auto text-xxs text-ink-faint">
          {summary.evaluation_count} evaluation{summary.evaluation_count === 1 ? "" : "s"}
          {summary.latest_evaluation_date ? ` · last ${summary.latest_evaluation_date}` : ""}
        </span>
      </div>
      <div className="space-y-2">
        {summary.factor_averages.map((f) => (
          <div key={f.factor_key} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2">
            <div className="min-w-0">
              <div className="mb-1 flex items-center justify-between">
                <span className="truncate text-xxs text-ink-muted">{f.factor_label}</span>
                <span className="ml-2 font-mono text-xxs text-ink">{f.average.toFixed(1)}</span>
              </div>
              <ScoreBar value={f.average} max={max} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ---------------------------- rating form dialog -------------------------- */
function RatingFormDialog({
  title, defs, max, initial, onClose, onSubmit,
}: {
  title: string;
  defs: RatingFactorDef[];
  max: number;
  initial?: InternalEvaluation | null;
  onClose: () => void;
  onSubmit: (body: EvaluationInput) => Promise<void>;
}) {
  const [scores, setScores] = useState<Record<string, number>>(() => {
    const s: Record<string, number> = {};
    if (initial) initial.factors.forEach((f) => { s[f.factor_key] = f.score; });
    return s;
  });
  const [summary, setSummary] = useState(initial?.partner_visible_summary ?? "");
  const [notes, setNotes] = useState(initial?.internal_notes ?? "");
  const [date, setDate] = useState(initial?.evaluation_date ?? "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const overall = useMemo(() => previewOverall(scores, defs), [scores, defs]);
  const allScored = defs.every((d) => scores[d.key] != null);

  async function save() {
    if (!allScored) { setErr("Please score every factor."); return; }
    setBusy(true); setErr(null);
    try {
      await onSubmit({
        factors: defs.map((d) => ({ factor_key: d.key, score: scores[d.key] })),
        partner_visible_summary: summary.trim() || null,
        internal_notes: notes.trim() || null,
        evaluation_date: date || undefined,
        status: "published",
      });
      onClose();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not save the rating.");
    } finally { setBusy(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl border border-border bg-surface p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-ink">{title}</h3>
          <button onClick={onClose} className="text-ink-faint hover:text-ink" aria-label="Close"><X className="h-4 w-4" /></button>
        </div>

        <div className="mb-4 flex items-center gap-3 rounded-lg bg-surface-2 px-3 py-2">
          <span className="text-xxs uppercase tracking-eyebrow text-ink-faint">Overall (auto)</span>
          <span className="text-lg font-semibold text-ink">{overall != null ? overall.toFixed(1) : "—"}</span>
          <span className="text-xxs text-ink-faint">/ {max}</span>
          <span className="ml-auto text-xxs text-ink-faint">Computed on the backend from the factor scores.</span>
        </div>

        <div className="space-y-3">
          {defs.map((d) => (
            <div key={d.key} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3">
              <span className="truncate text-xs text-ink">{d.label}</span>
              <div className="flex items-center gap-1">
                {Array.from({ length: max }, (_, i) => i + 1).map((n) => (
                  <button key={n} type="button" onClick={() => setScores((s) => ({ ...s, [d.key]: n }))}
                    className={`grid h-7 w-7 place-items-center rounded-md border text-xs font-medium transition-colors ${
                      scores[d.key] === n ? "border-accent-orange bg-accent-orange/15 text-accent-orange"
                        : "border-border text-ink-muted hover:border-border-strong"}`}>
                    {n}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-4 space-y-3">
          <div>
            <label className="mb-1 block text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Evaluation date</label>
            <input type="date" className={inputCls} value={date ?? ""} onChange={(e) => setDate(e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Partner-visible summary</label>
            <textarea className={`${inputCls} h-16 py-1.5`} value={summary} onChange={(e) => setSummary(e.target.value)}
              placeholder="Shown to the partner (strengths + improvement areas)." />
          </div>
          <div>
            <label className="mb-1 block text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Internal notes (never shown to partner)</label>
            <textarea className={`${inputCls} h-16 py-1.5`} value={notes} onChange={(e) => setNotes(e.target.value)}
              placeholder="Internal-only context." />
          </div>
        </div>

        {err && <p className="mt-3 text-xs text-danger">{err}</p>}

        <div className="mt-4 flex items-center gap-2">
          <Button variant="primary" onClick={save} disabled={busy || !allScored}>
            {busy && <Loader2 className="h-4 w-4 animate-spin" />} Save evaluation
          </Button>
          <Button variant="secondary" onClick={onClose} disabled={busy}>Cancel</Button>
        </div>
      </div>
    </div>
  );
}

/* --------------------------- facility ratings ----------------------------- */
export function FacilityRatingsSection({ facilityId }: { facilityId: string }) {
  const [defs, setDefs] = useState<RatingFactorDef[]>([]);
  const [scaleMax, setScaleMax] = useState(5);
  const [summary, setSummary] = useState<RatingSummary | null>(null);
  const [history, setHistory] = useState<InternalEvaluation[]>([]);
  const [dialog, setDialog] = useState<null | { edit?: InternalEvaluation }>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [f, s, h] = await Promise.all([
        getRatingFactors(), getFacilityRating(facilityId),
        listFacilityEvaluations(facilityId, { limit: 20 }),
      ]);
      setDefs(f.facility_factors); setScaleMax(f.scale.max);
      setSummary(s); setHistory(h.evaluations);
    } catch { /* keep prior */ } finally { setLoading(false); }
  }, [facilityId]);

  useEffect(() => { load(); }, [load]);

  return (
    <DetailSectionCard title="Performance rating" icon={Star}
      action={<Button variant="secondary" size="sm" onClick={() => setDialog({})}>Rate facility</Button>}>
      {loading && !summary ? (
        <p className="text-xs text-ink-muted">Loading rating…</p>
      ) : (
        <>
          <RatingSummaryView summary={summary ?? { overall_score: null, evaluation_count: 0, latest_evaluation_date: null, factor_averages: [], trend: [] }} max={scaleMax} />
          {history.length > 0 && (
            <div className="mt-4 border-t border-border/60 pt-3">
              <p className="mb-2 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">History</p>
              <ul className="space-y-1.5">
                {history.map((ev) => (
                  <li key={ev.id} className="flex items-center justify-between gap-2 text-xs">
                    <span className="text-ink-muted">{ev.evaluation_date} · <span className="font-mono text-ink">{ev.overall_score?.toFixed(1)}</span>
                      {ev.status && ev.status !== "published" && <span className="ml-1 text-ink-faint">({ev.status})</span>}</span>
                    <button onClick={() => setDialog({ edit: ev })} className="inline-flex items-center gap-1 text-ink-faint hover:text-ink">
                      <Pencil className="h-3 w-3" /> Edit
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}

      {dialog && (
        <RatingFormDialog
          title={dialog.edit ? "Edit facility evaluation" : "Rate facility"}
          defs={defs} max={scaleMax} initial={dialog.edit}
          onClose={() => setDialog(null)}
          onSubmit={async (body) => {
            if (dialog.edit) await updateFacilityEvaluation(facilityId, dialog.edit.id, body);
            else await createFacilityEvaluation(facilityId, body);
            await load();
          }}
        />
      )}
    </DetailSectionCard>
  );
}

/* ----------------------------- driver ratings ----------------------------- */
export function DriverRatingsSection({ facilityId }: { facilityId: string }) {
  const [defs, setDefs] = useState<RatingFactorDef[]>([]);
  const [scaleMax, setScaleMax] = useState(5);
  const [drivers, setDrivers] = useState<DriverRow[]>([]);
  const [ratings, setRatings] = useState<Record<string, RatingSummary>>({});
  const [dialog, setDialog] = useState<null | { driver: DriverRow }>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [f, d] = await Promise.all([getRatingFactors(), getFacilityDrivers(facilityId)]);
      setDefs(f.driver_factors); setScaleMax(f.scale.max);
      setDrivers(d.drivers);
      const entries = await Promise.all(
        d.drivers.map(async (dr) => [dr.id, await getDriverRating(dr.id)] as const),
      );
      setRatings(Object.fromEntries(entries));
    } catch { /* keep */ } finally { setLoading(false); }
  }, [facilityId]);

  useEffect(() => { load(); }, [load]);

  return (
    <DetailSectionCard title="Driver ratings" icon={Truck}>
      {loading && drivers.length === 0 ? (
        <p className="text-xs text-ink-muted">Loading drivers…</p>
      ) : drivers.length === 0 ? (
        <p className="text-xs text-ink-muted">No drivers are registered for this facility yet.</p>
      ) : (
        <ul className="space-y-2.5">
          {drivers.map((dr) => {
            const r = ratings[dr.id];
            return (
              <li key={dr.id} className="flex items-center gap-3">
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-surface-2 text-xxs font-semibold text-ink">
                  {(dr.name ?? "?").slice(0, 2).toUpperCase()}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-medium text-ink">{dr.name ?? "Driver"}</p>
                  <p className="text-xxs text-ink-faint">
                    {r && r.evaluation_count > 0
                      ? `${r.overall_score?.toFixed(1)} / ${scaleMax} · ${r.evaluation_count} eval${r.evaluation_count === 1 ? "" : "s"}`
                      : "Not rated yet"}
                  </p>
                </div>
                <Button variant="ghost" size="sm" onClick={() => setDialog({ driver: dr })}>Rate</Button>
              </li>
            );
          })}
        </ul>
      )}

      {dialog && (
        <RatingFormDialog
          title={`Rate ${dialog.driver.name ?? "driver"}`}
          defs={defs} max={scaleMax}
          onClose={() => setDialog(null)}
          onSubmit={async (body) => { await createDriverEvaluation(dialog.driver.id, body); await load(); }}
        />
      )}
    </DetailSectionCard>
  );
}
