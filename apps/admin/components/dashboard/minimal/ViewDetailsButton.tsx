import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * ViewDetailsButton — the explicit "there is more inside" affordance. Used on
 * cards/rows/panels that summarize a record on a main page and open its full
 * detail view. Quiet by default; the arrow nudges rose on hover.
 */
export function ViewDetailsButton({
  href,
  onClick,
  label = "View details",
  className,
}: {
  href?: string;
  onClick?: () => void;
  label?: string;
  className?: string;
}) {
  const cls = cn(
    "group inline-flex items-center gap-1.5 text-xs font-semibold text-ink-muted transition-colors hover:text-rose focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40 rounded",
    className,
  );
  const inner = (
    <>
      {label}
      <ArrowRight className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-0.5" />
    </>
  );
  if (href) {
    return (
      <Link href={href} className={cls}>
        {inner}
      </Link>
    );
  }
  return (
    <button type="button" onClick={onClick} className={cls}>
      {inner}
    </button>
  );
}
