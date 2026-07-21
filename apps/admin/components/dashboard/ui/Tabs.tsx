"use client";

import { useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export type TabDef = {
  id: string;
  label: string;
  icon?: ReactNode;
  badge?: number;
  content: ReactNode;
};

/**
 * Tabs with two looks:
 *  - "underline" (default): understated secondary tabs with a rose underline.
 *  - "segmented": a prominent pill switch, used for the top-level team switch so
 *    a second (underline) tab row nested inside reads as a clear sub-level.
 * Both are horizontally scrollable so strips never overflow on mobile.
 */
export function Tabs({
  tabs,
  initial,
  className,
  variant = "underline",
}: {
  tabs: TabDef[];
  initial?: string;
  className?: string;
  variant?: "underline" | "segmented";
}) {
  const [active, setActive] = useState(initial ?? tabs[0]?.id);
  const current = tabs.find((t) => t.id === active) ?? tabs[0];

  const Badge = ({ t, on }: { t: TabDef; on: boolean }) =>
    typeof t.badge === "number" && t.badge > 0 ? (
      <span
        className={cn(
          "rounded-full px-1.5 py-0.5 text-xxs font-semibold tnum",
          on ? "bg-rose/12 text-rose" : "bg-ink/8 text-ink-muted",
        )}
      >
        {t.badge}
      </span>
    ) : null;

  if (variant === "segmented") {
    return (
      <div className={className}>
        <div className="mb-6 overflow-x-auto">
          <div role="tablist" className="inline-flex min-w-max gap-1 rounded-xl border border-border bg-surface-2 p-1">
            {tabs.map((t) => {
              const on = t.id === active;
              return (
                <button
                  key={t.id}
                  role="tab"
                  aria-selected={on}
                  onClick={() => setActive(t.id)}
                  className={cn(
                    "flex items-center gap-2 whitespace-nowrap rounded-lg px-4 py-2 text-sm font-semibold transition-all duration-200",
                    on ? "bg-surface text-rose shadow-card" : "text-ink-muted hover:text-ink",
                  )}
                >
                  {t.icon}
                  {t.label}
                  <Badge t={t} on={on} />
                </button>
              );
            })}
          </div>
        </div>
        <div role="tabpanel" className="lk-enter">
          {current?.content}
        </div>
      </div>
    );
  }

  return (
    <div className={className}>
      <div className="mb-5 overflow-x-auto border-b border-border">
        <div role="tablist" className="flex min-w-max gap-1">
          {tabs.map((t) => {
            const on = t.id === active;
            return (
              <button
                key={t.id}
                role="tab"
                aria-selected={on}
                onClick={() => setActive(t.id)}
                className={cn(
                  "relative flex items-center gap-2 whitespace-nowrap px-3.5 py-2.5 text-sm font-medium transition-colors",
                  on ? "text-ink" : "text-ink-muted hover:text-ink",
                )}
              >
                {t.icon}
                {t.label}
                <Badge t={t} on={on} />
                {on && <span className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-rose" />}
              </button>
            );
          })}
        </div>
      </div>
      <div role="tabpanel" className="lk-enter">
        {current?.content}
      </div>
    </div>
  );
}
