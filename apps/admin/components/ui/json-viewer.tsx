"use client";

import { ChevronRight } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

export function JsonViewer({
  data,
  label = "View JSON",
  defaultOpen = false,
}: {
  data: unknown;
  label?: string;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const isEmpty =
    data === null ||
    data === undefined ||
    (typeof data === "object" && Object.keys(data as object).length === 0);

  if (isEmpty) {
    return <span className="text-xs text-ink-faint">-</span>;
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1 text-xs font-medium text-brand hover:text-brand-hover"
      >
        <ChevronRight className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-90")} />
        {label}
      </button>
      {open && (
        <pre className="mt-2 max-h-72 overflow-auto rounded-lg bg-ink px-3 py-2.5 text-xxs leading-relaxed text-neutral-soft">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
}
