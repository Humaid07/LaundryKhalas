"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

export function Switch({
  defaultOn = false,
  label,
  className,
}: {
  defaultOn?: boolean;
  label?: string;
  className?: string;
}) {
  const [on, setOn] = useState(defaultOn);
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      onClick={() => setOn((v) => !v)}
      className={cn(
        // Fixed track size, never allowed to shrink or clip.
        "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full",
        "transition-colors duration-200 ease-out-quint",
        // Subtle, accessible focus ring (offset against the card surface).
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40 focus-visible:ring-offset-2 focus-visible:ring-offset-surface",
        // Checked = LaundryKhalas rose; unchecked = neutral gray that stays
        // visible in dark mode (ink is light on dark, so this reads clearly).
        on ? "bg-rose" : "bg-ink/20 dark:bg-ink/25",
        className,
      )}
    >
      <span
        className={cn(
          // Thumb stays fully inside the track in both states.
          "pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-sm ring-1 ring-black/5",
          "transition-transform duration-200 ease-out-quint",
          on ? "translate-x-[1.375rem]" : "translate-x-0.5",
        )}
      />
    </button>
  );
}
