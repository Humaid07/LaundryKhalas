"use client";

import { FlaskConical } from "lucide-react";
import { API_BASE_URL } from "@/lib/constants";

const FLAGS = [
  { label: "Live WhatsApp", on: false },
  { label: "Live Stripe", on: false },
  { label: "Live LLM", on: false },
];

export function AdminTopbar() {
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-surface/95 px-4 backdrop-blur md:px-6">
      <div className="flex items-center gap-2 rounded-full border border-warning/30 bg-warning-soft px-3 py-1.5">
        <FlaskConical size={14} className="text-warning" />
        <span className="text-xs font-semibold uppercase tracking-wide text-warning-text">
          Review Mode
        </span>
        <span className="hidden text-xs text-warning-text/70 sm:inline">
          No live WhatsApp messages are being sent.
        </span>
      </div>

      <div className="flex items-center gap-4">
        <div className="hidden items-center gap-3 lg:flex">
          {FLAGS.map((flag) => (
            <div key={flag.label} className="flex items-center gap-1.5 text-xs text-ink-muted">
              <span className={`h-1.5 w-1.5 rounded-full ${flag.on ? "bg-success" : "bg-ink-faint"}`} />
              {flag.label}: <span className="font-medium text-ink">{flag.on ? "On" : "Off"}</span>
            </div>
          ))}
        </div>
        <div className="hidden text-xs text-ink-faint md:block" title={API_BASE_URL}>
          API: {API_BASE_URL.replace(/^https?:\/\//, "")}
        </div>
      </div>
    </header>
  );
}
