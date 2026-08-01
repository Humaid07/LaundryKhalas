"use client";

import { useQuery } from "@tanstack/react-query";
import { Star, Truck, TrendingUp } from "lucide-react";
import { facilityApi, type RatingSummary, type PartnerEvaluation } from "@/lib/api-client";
import { MobilePageHeader } from "@/components/shared/MobilePageHeader";
import { SectionCard } from "@/components/shared/SectionCard";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/states";

const MAX = 5;

function Bar({ value }: { value: number | null }) {
  const pct = value == null ? 0 : Math.max(0, Math.min(100, (value / MAX) * 100));
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-ink/8">
      <div className="h-full rounded-full bg-rose transition-all" style={{ width: `${pct}%` }} />
    </div>
  );
}

function Trend({ points }: { points: RatingSummary["trend"] }) {
  if (!points || points.length < 2) return null;
  const first = points[0].overall_score;
  const last = points[points.length - 1].overall_score;
  const delta = Math.round((last - first) * 10) / 10;
  return (
    <span className={`inline-flex items-center gap-1 text-xxs ${delta >= 0 ? "text-success" : "text-danger"}`}>
      <TrendingUp className={`h-3 w-3 ${delta < 0 ? "rotate-180" : ""}`} />
      {delta >= 0 ? "+" : ""}{delta} over {points.length} evals
    </span>
  );
}

function RatingBlock({ summary, latest }: { summary: RatingSummary; latest: PartnerEvaluation | null }) {
  if (!summary || summary.evaluation_count === 0) {
    return (
      <p className="rounded-xl border border-dashed border-border bg-canvas px-4 py-8 text-center text-sm text-ink-muted">
        No performance ratings are available yet. Ratings will appear after an internal evaluation is completed.
      </p>
    );
  }
  const factors = latest?.factors?.length
    ? latest.factors.map((f) => ({ key: f.factor_key, label: f.factor_label, value: f.score }))
    : summary.factor_averages.map((f) => ({ key: f.factor_key, label: f.factor_label, value: f.average }));

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-x-4 gap-y-2">
        <span className="font-mono text-4xl font-semibold leading-none text-ink tnum">
          {summary.overall_score?.toFixed(1)}
        </span>
        <span className="pb-1 text-sm text-ink-faint">/ {MAX}</span>
        <div className="ml-auto text-right">
          <p className="text-xxs text-ink-faint">
            {summary.evaluation_count} evaluation{summary.evaluation_count === 1 ? "" : "s"}
            {summary.latest_evaluation_date ? ` · last ${summary.latest_evaluation_date}` : ""}
          </p>
          <Trend points={summary.trend} />
        </div>
      </div>

      <div className="space-y-2.5">
        {factors.map((f) => (
          <div key={f.key}>
            <div className="mb-1 flex items-center justify-between">
              <span className="text-xs text-ink-muted">{f.label}</span>
              <span className="font-mono text-xs text-ink tnum">{f.value.toFixed(1)}</span>
            </div>
            <Bar value={f.value} />
          </div>
        ))}
      </div>

      {latest?.partner_visible_summary && (
        <div className="rounded-xl bg-ink/4 px-4 py-3">
          <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Performance summary</p>
          <p className="mt-1 text-sm text-ink">{latest.partner_visible_summary}</p>
        </div>
      )}
    </div>
  );
}

export default function RatingsPage() {
  const facilityQ = useQuery({ queryKey: ["facility", "rating"], queryFn: () => facilityApi.getFacilityRating() });
  const driversQ = useQuery({ queryKey: ["facility", "ratings", "drivers"], queryFn: () => facilityApi.getDriverRatings() });

  return (
    <div className="lk-enter space-y-5">
      <MobilePageHeader
        title="Ratings"
        description="How LaundryKhalas rates your facility and drivers."
      />

      <SectionCard title="Facility rating" icon={Star}>
        {facilityQ.isLoading ? (
          <LoadingState label="Loading rating…" />
        ) : facilityQ.isError ? (
          <ErrorState description="Could not load your facility rating." onRetry={() => facilityQ.refetch()} />
        ) : (
          <RatingBlock summary={facilityQ.data!.summary} latest={facilityQ.data!.latest} />
        )}
      </SectionCard>

      <SectionCard title="Driver ratings" icon={Truck}>
        {driversQ.isLoading ? (
          <LoadingState label="Loading drivers…" />
        ) : driversQ.isError ? (
          <ErrorState description="Could not load driver ratings." onRetry={() => driversQ.refetch()} />
        ) : (driversQ.data?.drivers.length ?? 0) === 0 ? (
          <EmptyState icon={Truck} title="No drivers yet" description="Driver ratings appear once your drivers are evaluated." />
        ) : (
          <div className="space-y-3">
            {driversQ.data!.drivers.map((d) => (
              <div key={d.driver_id} className="rounded-xl border border-border/70 bg-surface p-4">
                <div className="mb-2 flex items-center gap-3">
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-ink/6 text-xs font-semibold text-ink">
                    {(d.name ?? "?").slice(0, 2).toUpperCase()}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-ink">{d.name ?? "Driver"}</p>
                    <p className="text-xxs text-ink-faint">
                      {d.summary.evaluation_count > 0
                        ? `${d.summary.overall_score?.toFixed(1)} / ${MAX} · ${d.summary.evaluation_count} eval${d.summary.evaluation_count === 1 ? "" : "s"}`
                        : "Not rated yet"}
                    </p>
                  </div>
                  {d.summary.evaluation_count > 0 && (
                    <span className="font-mono text-lg font-semibold text-ink tnum">{d.summary.overall_score?.toFixed(1)}</span>
                  )}
                </div>
                {d.summary.evaluation_count > 0 && (
                  <div className="space-y-1.5">
                    {(d.latest?.factors ?? d.summary.factor_averages.map((f) => ({ factor_key: f.factor_key, factor_label: f.factor_label, score: f.average }))).map((f) => (
                      <div key={f.factor_key}>
                        <div className="mb-0.5 flex items-center justify-between">
                          <span className="text-xxs text-ink-muted">{f.factor_label}</span>
                          <span className="font-mono text-xxs text-ink tnum">{f.score.toFixed(1)}</span>
                        </div>
                        <Bar value={f.score} />
                      </div>
                    ))}
                    {d.latest?.partner_visible_summary && (
                      <p className="mt-2 text-xxs text-ink-muted">{d.latest.partner_visible_summary}</p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </SectionCard>
    </div>
  );
}
