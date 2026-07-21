import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { StatusBadge } from "@/components/dashboard/ui/primitives";
import { toneText } from "@/components/dashboard/ui/tones";
import type { Subsection } from "@/lib/dashboard/sections";
import { cn } from "@/lib/utils";

/** A landing-page card that links to one subsection route. Summary only. */
export function SectionCard({ base, sub }: { base: string; sub: Subsection }) {
  const Icon = sub.icon;
  return (
    <Link
      href={`${base}/${sub.slug}`}
      className="group flex flex-col rounded-2xl border border-border bg-surface p-5 shadow-card transition-all duration-300 ease-out-quint hover:-translate-y-0.5 hover:border-rose/40 hover:shadow-raised"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-rose/12 text-rose transition-colors group-hover:bg-rose/16">
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
        <span className="inline-flex items-center gap-1.5 rounded-lg bg-surface-2 px-3 py-1.5 text-xs font-semibold text-ink transition-colors group-hover:bg-rose group-hover:text-rose-contrast">
          Open <ArrowRight className="h-3.5 w-3.5" />
        </span>
      </div>
    </Link>
  );
}
