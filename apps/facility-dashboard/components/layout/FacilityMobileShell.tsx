"use client";

import type { ReactNode } from "react";
import { FacilityHeader } from "./FacilityHeader";
import { FacilityBottomNav } from "./FacilityBottomNav";
import { FacilityDesktopShell } from "./FacilityDesktopShell";
import { ReportIssueButton } from "./ReportIssueButton";

/**
 * FacilityMobileShell — the app frame.
 *   • Mobile: sticky header + scrollable content + fixed bottom nav + floating
 *     "Report Issue" button.
 *   • Desktop (md+): a left sidebar replaces the bottom nav; content sits beside it.
 * Content is width-capped and horizontally padded so no route can overflow.
 */
export function FacilityMobileShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen bg-canvas">
      <FacilityDesktopShell />

      <div className="flex min-w-0 flex-1 flex-col">
        <FacilityHeader />

        <main
          className="mx-auto w-full max-w-5xl flex-1 px-4 py-5 sm:px-6"
          style={{ paddingBottom: "calc(env(safe-area-inset-bottom) + 5.5rem)" }}
        >
          {children}
        </main>
      </div>

      <FacilityBottomNav />
      <ReportIssueButton />
    </div>
  );
}
