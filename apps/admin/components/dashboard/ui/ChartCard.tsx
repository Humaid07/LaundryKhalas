import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Panel, PanelHeader } from "./primitives";

/** Titled container for a chart, with optional legend/filter action slot. */
export function ChartCard({
  title,
  subtitle,
  action,
  children,
  className,
  bodyClassName,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <Panel className={cn("flex flex-col", className)}>
      <PanelHeader title={title} subtitle={subtitle} action={action} />
      <div className={cn("min-w-0", bodyClassName)}>{children}</div>
    </Panel>
  );
}
