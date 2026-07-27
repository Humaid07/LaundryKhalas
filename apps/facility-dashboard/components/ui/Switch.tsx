"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

export function Switch({
  checked,
  defaultOn = false,
  onChange,
  label,
  className,
}: {
  /** Controlled state. When provided, the switch reflects this value. */
  checked?: boolean;
  defaultOn?: boolean;
  onChange?: (on: boolean) => void;
  label?: string;
  className?: string;
}) {
  const [internal, setInternal] = useState(defaultOn);
  const on = checked ?? internal;
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      onClick={() => {
        const next = !on;
        if (checked === undefined) setInternal(next);
        onChange?.(next);
      }}
      className={cn(
        // Fixed track size, never allowed to shrink or clip.
        "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full",
        "transition-colors duration-200 ease-out-quint",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40 focus-visible:ring-offset-2 focus-visible:ring-offset-surface",
        on ? "bg-rose" : "bg-ink/20 dark:bg-ink/25",
        className,
      )}
    >
      <span
        className={cn(
          "pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-sm ring-1 ring-black/5",
          "transition-transform duration-200 ease-out-quint",
          on ? "translate-x-[1.375rem]" : "translate-x-0.5",
        )}
      />
    </button>
  );
}
