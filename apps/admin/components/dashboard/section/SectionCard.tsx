import { ArrowRight } from "lucide-react";
import { StatusBadge } from "@/components/dashboard/ui/primitives";
import { toneText } from "@/components/dashboard/ui/tones";
import { accentClasses, accentForHref, type AccentName } from "@/lib/dashboard/accents";
import type { Subsection } from "@/lib/dashboard/sections";
import { cn } from "@/lib/utils";
import { SpotlightCard } from "./SpotlightCard";

// The CSS colour token (R G B triplet, see globals.css) used for each accent's
// spotlight glow. Rose uses the brand token; neutral falls back to ink-faint.
const ACCENT_GLOW_VAR: Record<AccentName, string> = {
  rose: "--rose",
  slate: "--accent-slate",
  teal: "--accent-teal",
  sky: "--accent-sky",
  amber: "--accent-amber",
  violet: "--accent-violet",
  indigo: "--accent-indigo",
  fuchsia: "--accent-fuchsia",
  cyan: "--accent-cyan",
  steel: "--accent-steel",
  plum: "--accent-plum",
  orange: "--accent-orange",
  neutral: "--ink-faint",
};

/** A landing-page card that links to one subsection route. Summary only.
 *  Carries the module's accent (top-rule, icon chip, hover border, CTA) plus a
 *  tuned pointer-tracked spotlight glow (see SpotlightCard). Stays a Server
 *  Component — the client behaviour lives in SpotlightCard and only serializable
 *  props + server-rendered children cross the boundary. */
export function SectionCard({ base, sub }: { base: string; sub: Subsection }) {
  const Icon = sub.icon;
  const accentName = accentForHref(base);
  const accent = accentClasses(accentName);
  return (
    <SpotlightCard
      href={`${base}/${sub.slug}`}
      glowVar={ACCENT_GLOW_VAR[accentName]}
      className={cn(
        "group relative flex flex-col overflow-hidden rounded-2xl border border-border bg-surface p-5 shadow-card transition-all duration-300 ease-out-quint hover:-translate-y-0.5 hover:shadow-raised",
        accent.hoverBorder,
      )}
    >
      {/* module-accent top-rule — reveals fully on hover (above the glow) */}
      <span className={cn("pointer-events-none absolute inset-x-0 top-0 z-20 h-0.5 origin-left scale-x-[0.35] opacity-70 transition-transform duration-300 ease-out-quint group-hover:scale-x-100 group-hover:opacity-100", accent.rail)} />

      <div className="relative z-10 flex flex-1 flex-col">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className={cn("flex h-10 w-10 items-center justify-center rounded-xl transition-colors", accent.chip)}>
              <Icon className="h-5 w-5" />
            </span>
            <h3 className="font-display text-base font-semibold leading-tight text-ink">{sub.label}</h3>
          </div>
          {sub.status && <StatusBadge tone={sub.status.tone} dot={false}>{sub.status.label}</StatusBadge>}
        </div>

        <p className="mt-3 flex-1 text-sm leading-relaxed text-ink-muted">{sub.description}</p>

        {sub.kpis && sub.kpis.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2 border-t border-border pt-4">
            {sub.kpis.map((k) => (
              <span key={k.label} className="inline-flex items-baseline gap-1.5 rounded-lg bg-surface-2 px-2.5 py-1">
                <span className={cn("font-mono text-sm font-semibold tnum", k.tone ? toneText[k.tone] : "text-ink")}>{k.value}</span>
                <span className="text-xxs text-ink-faint">{k.label}</span>
              </span>
            ))}
          </div>
        )}

        <div className="mt-4 flex items-center justify-end">
          <span className={cn("inline-flex items-center gap-1.5 rounded-lg bg-surface-2 px-3 py-1.5 text-xs font-semibold text-ink transition-colors", accent.ctaHover)}>
            Open <ArrowRight className="h-3.5 w-3.5" />
          </span>
        </div>
      </div>
    </SpotlightCard>
  );
}
