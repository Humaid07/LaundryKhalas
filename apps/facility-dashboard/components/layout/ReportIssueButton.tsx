"use client";

import { useRouter } from "next/navigation";
import { AlertTriangle } from "lucide-react";

/**
 * Floating "Report Issue" action for mobile. Sits above the bottom nav and opens
 * the issue-reporting form. Hidden on md+ (desktop uses the in-page action).
 */
export function ReportIssueButton() {
  const router = useRouter();
  return (
    <button
      type="button"
      onClick={() => router.push("/issues/new")}
      className="fixed right-4 z-40 flex items-center gap-2 rounded-full bg-rose px-4 py-3 text-sm font-semibold text-rose-contrast shadow-rose-glow transition-transform active:scale-95 md:hidden"
      style={{ bottom: "calc(env(safe-area-inset-bottom) + 4.75rem)" }}
    >
      <AlertTriangle className="h-4 w-4" />
      Report Issue
    </button>
  );
}
