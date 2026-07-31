"use client";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

// Lightweight, dependency-free tooltip. Wrap a focusable trigger; the label
// shows on hover AND keyboard focus. `title` is the no-JS / screen-reader
// fallback. Motion is opacity-only, so prefers-reduced-motion degrades cleanly.
export function Tooltip({
  label,
  children,
  side = "bottom",
}: {
  label: string;
  children: ReactNode;
  side?: "top" | "bottom";
}) {
  return (
    <span className="group/tt relative inline-flex" title={label}>
      {children}
      <span
        role="tooltip"
        className={cn(
          "pointer-events-none absolute left-1/2 z-50 -translate-x-1/2 whitespace-nowrap rounded-md bg-ink px-2 py-1 text-xxs font-medium text-canvas opacity-0 shadow-pop transition-opacity duration-150 group-hover/tt:opacity-100 group-focus-within/tt:opacity-100",
          side === "bottom" ? "top-[calc(100%+6px)]" : "bottom-[calc(100%+6px)]",
        )}
      >
        {label}
      </span>
    </span>
  );
}
