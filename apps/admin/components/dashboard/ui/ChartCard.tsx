import type { ComponentType, ReactNode } from "react";
import { cn } from "@/lib/utils";
import type { AccentName } from "@/lib/dashboard/accents";
import { Panel, PanelHeader } from "./primitives";

/** Titled container for a chart, with optional legend/filter action slot.
 *  Pass `accent` for a module-accent top-rule + header icon chip. */
export function ChartCard({
  title,
  subtitle,
  action,
  icon,
  accent,
  children,
  className,
  bodyClassName,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  icon?: ComponentType<{ className?: string }>;
  accent?: AccentName;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <Panel accent={accent} className={cn("flex flex-col", className)}>
      <PanelHeader title={title} subtitle={subtitle} action={action} icon={icon} accent={accent} />
      <div className={cn("min-w-0", bodyClassName)}>{children}</div>
    </Panel>
  );
}
