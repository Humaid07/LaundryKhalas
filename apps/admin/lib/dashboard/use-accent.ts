"use client";

import { usePathname } from "next/navigation";
import { accentForPath, accentClasses, type AccentName, type AccentClasses } from "./accents";

/**
 * Resolve the current module's accent from the route. Use in client pages to
 * pass `accent` down to the shared kit (StatGrid, Panel, ChartCard, HeroStat) so
 * a page's metrics/charts carry the module colour without hardcoding it.
 *
 *   const accent = useAccentName();   // "amber" on /sales, "teal" on /operations …
 *   <StatGrid stats={kpis} accent={accent} />
 */
export function useAccentName(): AccentName {
  return accentForPath(usePathname());
}

export function useAccentClasses(): AccentClasses {
  return accentClasses(accentForPath(usePathname()));
}
