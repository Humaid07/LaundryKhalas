import { cn } from "@/lib/utils";
import type { Tone } from "@/lib/dashboard/types";
import { toneText } from "@/components/dashboard/ui/tones";

export type MinimalKpi = {
  label: string;
  value: string;
  /** Optional one-word hint under the value (kept muted). */
  hint?: string;
  /** Tone tints ONLY the value when it carries a signal (e.g. danger count). Defaults to ink. */
  tone?: Tone;
};

/**
 * Minimal KPI strip — a quiet summary row for a main page. Label + number only:
 * no sparklines, no hover lift, no rose rail. Fewer colors (value stays ink
 * unless a tone signals attention). Keep to 3–4 KPIs; deeper metrics live on the
 * Overview page or a detail view. See docs/architecture/minimal-dashboard-design-system.md.
 */
export function MinimalKpiStrip({
  kpis,
  className,
}: {
  kpis: MinimalKpi[];
  className?: string;
}) {
  return (
    <div
      className={cn(
        "grid grid-cols-2 divide-ink/5 overflow-hidden rounded-2xl border border-border/70 bg-surface shadow-card sm:divide-x lg:grid-cols-4",
        className,
      )}
    >
      {kpis.map((k) => (
        <div key={k.label} className="min-w-0 px-5 py-4">
          <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">{k.label}</p>
          <p
            className={cn(
              "mt-2 font-mono text-2xl font-semibold leading-none tracking-tight tnum",
              k.tone && k.tone !== "neutral" ? toneText[k.tone] : "text-ink",
            )}
          >
            {k.value}
          </p>
          {k.hint && <p className="mt-1.5 truncate text-xs text-ink-muted">{k.hint}</p>}
        </div>
      ))}
    </div>
  );
}
