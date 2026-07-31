import { cn } from "@/lib/utils";
import type { KpiStat, Tone } from "@/lib/dashboard/types";
import { accentClasses, type AccentName } from "@/lib/dashboard/accents";
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

/** Signature KPI card: eyebrow label, big Space-Grotesk number, delta + sparkline.
 *  The hover signal-rail uses the module `accent` (defaults to rose). */
export function StatCard({
  stat,
  accent = "rose",
  className,
}: {
  stat: KpiStat;
  accent?: AccentName;
  className?: string;
}) {
  const tone = stat.tone ?? "rose";
  const a = accentClasses(accent);
  return (
    <div
      className={cn(
        "lk-hover-glow group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-border bg-surface p-4 shadow-card transition-all duration-300 ease-out-quint hover:-translate-y-0.5 hover:border-border-strong",
        className,
      )}
    >
      {/* accent signal rail on hover */}
      <span className={cn("pointer-events-none absolute inset-x-0 top-0 h-0.5 origin-left scale-x-0 transition-transform duration-300 ease-out-quint group-hover:scale-x-100", a.rail)} />
      <div className="flex items-start justify-between gap-2">
        <Eyebrow>{stat.label}</Eyebrow>
        {typeof stat.delta === "number" && <DeltaChip delta={stat.delta} />}
      </div>
      <div className="mt-3 flex items-end justify-between gap-3">
        <div className="min-w-0">
          <div className="font-mono text-metric font-semibold leading-none tracking-tight text-ink tnum">
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

/**
 * Hero KPI card — the single headline metric of a page. Larger than a standard
 * StatCard, with a solid always-on module-accent top-rule, an accent icon chip,
 * a big number, and an optional secondary stat. One per page (see the component
 * catalog: docs/architecture/erp-dashboard-component-catalog.md).
 */
export function HeroStat({
  stat,
  accent = "rose",
  icon: Icon,
  secondary,
  className,
}: {
  stat: KpiStat;
  accent?: AccentName;
  icon?: React.ComponentType<{ className?: string }>;
  /** Optional supporting metric shown beside the headline. */
  secondary?: { label: string; value: string };
  className?: string;
}) {
  const tone = stat.tone ?? "rose";
  const a = accentClasses(accent);
  return (
    <div
      className={cn(
        "lk-hover-glow relative flex flex-col justify-between overflow-hidden rounded-2xl border border-border-strong bg-surface p-5 shadow-raised",
        className,
      )}
    >
      {/* solid accent top-rule */}
      <span className={cn("pointer-events-none absolute inset-x-0 top-0 h-1", a.rail)} />
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          {Icon && (
            <span className={cn("flex h-9 w-9 items-center justify-center rounded-xl", a.chip)}>
              <Icon className="h-[18px] w-[18px]" />
            </span>
          )}
          <Eyebrow>{stat.label}</Eyebrow>
        </div>
        {typeof stat.delta === "number" && <DeltaChip delta={stat.delta} />}
      </div>

      <div className="mt-4 flex items-end justify-between gap-4">
        <div className="min-w-0">
          <div className="font-mono text-metric-lg font-bold leading-none tracking-tight text-ink tnum">
            {stat.value}
          </div>
          {stat.hint && <p className="mt-2 truncate text-xs text-ink-muted">{stat.hint}</p>}
        </div>
        {stat.spark ? (
          <Sparkline data={stat.spark} stroke={sparkStroke[tone]} fill={sparkFill[tone]} className="shrink-0 scale-[1.3] origin-bottom-right" />
        ) : (
          secondary && (
            <div className="shrink-0 rounded-xl bg-surface-2 px-3 py-2 text-right">
              <div className="font-mono text-lg font-semibold text-ink tnum">{secondary.value}</div>
              <div className="text-xxs uppercase tracking-eyebrow text-ink-faint">{secondary.label}</div>
            </div>
          )
        )}
      </div>
    </div>
  );
}

/** Grid wrapper that flows KPI cards responsively. */
export function StatGrid({
  stats,
  accent = "rose",
  className,
  cols = "auto",
}: {
  stats: KpiStat[];
  accent?: AccentName;
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
        <StatCard key={s.label} stat={s} accent={accent} />
      ))}
    </div>
  );
}
