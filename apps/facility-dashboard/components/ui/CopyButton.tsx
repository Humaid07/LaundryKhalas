"use client";
import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Inline copy-to-clipboard affordance with immediate "Copied" feedback — a small
 * micro-interaction (no global toast provider needed). Shows a check for ~1.2s
 * after copying; motion is opacity/colour only so prefers-reduced-motion degrades
 * cleanly. `value` is the text copied; `label` names it for a11y.
 */
export function CopyButton({
  value,
  label = "reference",
  className,
}: {
  value: string;
  label?: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);

  const copy = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      /* clipboard unavailable (insecure context) — no-op */
    }
  };

  return (
    <button
      type="button"
      onClick={copy}
      aria-label={copied ? `Copied ${label}` : `Copy ${label}`}
      title={copied ? "Copied" : "Copy"}
      className={cn(
        "inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-md text-ink-faint transition-colors hover:bg-ink/8 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40",
        copied && "text-success hover:text-success",
        className,
      )}
    >
      {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3 w-3" />}
    </button>
  );
}
