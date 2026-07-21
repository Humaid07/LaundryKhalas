import { cn } from "@/lib/utils";
import type { KpiStat, Tone } from "@/lib/dashboard/types";
import { DeltaChip, Eyebrow } from "./primitives";
import { Sparkline } from "./Sparkline";

const sparkStroke: Partial<Record<Tone, string>> = {
  rose: "rgb(var(--c-rose))",
  success: "rgb(var(--success))",
  info: "rgb(var(--c-sky))",
  warning: "rgb(var(--warning))",
  danger: "rgb(var(--danger))",
  plum: "rgb(var(--c-plum))",
  neutral: "rgb(var(--ink-faint))",
};
const sparkFill: Partial<Record<Tone, string>> = {
  rose: "rgb(var(--c-rose) / 0.12)",
  success: "rgb(var(--success) / 0.12)",
  info: "rgb(var(--c-sky) / 0.12)",
  warning: "rgb(var(--warning) / 0.12)",
  danger: "rgb(var(--danger) / 0.12)",
  plum: "rgb(var(--c-plum) / 0.12)",
  neutral: "rgb(var(--ink-faint) / 0.1)",
};

/** Signature KPI card: eyebrow label, big Space-Grotesk number, delta + sparkline. */
export function StatCard({ stat, className }: { stat: KpiStat; className?: string }) {
  const tone = stat.tone ?? "rose";
  return (
    <div
      className={cn(
        "group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-border bg-surface p-4 shadow-card transition-all duration-300 ease-out-quint hover:-translate-y-0.5 hover:border-border-strong hover:shadow-raised",
        className,
      )}
    >
      {/* rose signal rail on hover */}
      <span className="pointer-events-none absolute inset-x-0 top-0 h-0.5 origin-left scale-x-0 bg-rose transition-transform duration-300 ease-out-quint group-hover:scale-x-100" />
      <div className="flex items-start justify-between gap-2">
        <Eyebrow>{stat.label}</Eyebrow>
        {typeof stat.delta === "number" && <DeltaChip delta={stat.delta} />}
      </div>
      <div className="mt-3 flex items-end justify-between gap-3">
        <div className="min-w-0">
          <div className="font-mono text-[1.6rem] font-semibold leading-none tracking-tight text-ink tnum">
            {stat.value}
          </div>
          {stat.hint && <p className="mt-1.5 truncate text-xs text-ink-muted">{stat.hint}</p>}
        </div>
        {stat.spark && (
          <Sparkline
            data={stat.spark}
            stroke={sparkStroke[tone]}
            fill={sparkFill[tone]}
            className="shrink-0"
          />
        )}
      </div>
    </div>
  );
}

/** Grid wrapper that flows KPI cards responsively. */
export function StatGrid({
  stats,
  className,
  cols = "auto",
}: {
  stats: KpiStat[];
  className?: string;
  cols?: "auto" | "2" | "3" | "4";
}) {
  const colClass =
    cols === "auto"
      ? "grid-cols-2 md:grid-cols-3 xl:grid-cols-4"
      : cols === "4"
        ? "grid-cols-2 lg:grid-cols-4"
        : cols === "3"
          ? "grid-cols-1 sm:grid-cols-3"
          : "grid-cols-1 sm:grid-cols-2";
  return (
    <div className={cn("grid gap-3", colClass, className)}>
      {stats.map((s) => (
        <StatCard key={s.label} stat={s} />
      ))}
    </div>
  );
}
