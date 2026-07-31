import { cn } from "@/lib/utils";
import type { Tone } from "@/lib/types";
import { toneText } from "@/components/ui/tones";

export type MinimalKpi = {
  label: string;
  value: string;
  /** Optional one-word hint under the value (kept muted). */
  hint?: string;
  /** Tone tints ONLY the value when it carries a signal (e.g. danger count). Defaults to ink. */
  tone?: Tone;
  /** Optional click-through — turns the tile into a button. */
  onClick?: () => void;
};

/**
 * Minimal KPI strip — a quiet summary row for a main page. Label + number only.
 * Keep to 3–6 KPIs. Tiles become tappable when `onClick` is provided.
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
      {kpis.map((k) => {
        const inner = (
          <>
            <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">{k.label}</p>
            <p
              className={cn(
                "mt-2 font-mono text-metric font-semibold leading-none tracking-tight tnum",
                k.tone && k.tone !== "neutral" ? toneText[k.tone] : "text-ink",
              )}
            >
              {k.value}
            </p>
            {k.hint && <p className="mt-1.5 truncate text-xs text-ink-muted">{k.hint}</p>}
          </>
        );
        if (k.onClick) {
          return (
            <button
              key={k.label}
              type="button"
              onClick={k.onClick}
              className="min-w-0 px-5 py-4 text-left transition-colors hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-rose/40"
            >
              {inner}
            </button>
          );
        }
        return (
          <div key={k.label} className="min-w-0 px-5 py-4">
            {inner}
          </div>
        );
      })}
    </div>
  );
}
