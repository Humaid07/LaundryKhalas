"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bell, LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import { facilityApi } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { useUnreadCount } from "@/lib/use-notifications";
import { operatingLabel, operatingTone } from "@/lib/status";
import { toneChip, toneDot } from "@/components/ui/tones";
import { BrandWordmark } from "@/components/shell/Brand";
import { ThemeToggle } from "@/components/shell/ThemeToggle";
import { NotificationCenter } from "./NotificationCenter";

/**
 * FacilityHeader — sticky top bar: brand/facility name + operating-status chip +
 * notifications bell (unread badge) + theme toggle. On desktop the brand is in
 * the sidebar, so here we lead with the facility name.
 */
export function FacilityHeader() {
  const { user, logout } = useAuth();
  const [notifOpen, setNotifOpen] = useState(false);
  const unread = useUnreadCount();

  const { data: profile } = useQuery({
    queryKey: ["facility", "me"],
    queryFn: () => facilityApi.me(),
    staleTime: 60_000,
  });

  const facilityName = profile?.name ?? user?.facility_name ?? "Your Facility";
  const status = profile?.operating_status ?? "accepting";
  const tone = operatingTone(status);

  return (
    <>
      <header className="sticky top-0 z-30 border-b border-border bg-surface/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-5xl items-center justify-between gap-3 px-4">
          {/* Brand shows only on mobile (desktop sidebar carries it). */}
          <div className="flex min-w-0 items-center gap-3">
            <div className="md:hidden">
              <BrandWordmark />
            </div>
            <div className="hidden min-w-0 md:block">
              <p className="truncate font-display text-base font-semibold text-ink">{facilityName}</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span
              className={cn(
                "hidden items-center gap-1.5 rounded-full px-2.5 py-1 text-xxs font-semibold sm:inline-flex",
                toneChip[tone],
              )}
            >
              <span className={cn("h-1.5 w-1.5 rounded-full", toneDot[tone])} />
              {operatingLabel(status)}
            </span>

            <button
              type="button"
              onClick={() => setNotifOpen(true)}
              aria-label="Open notifications"
              className="relative flex h-10 w-10 items-center justify-center rounded-full border border-border bg-surface text-ink-muted transition-colors hover:border-border-strong hover:text-ink"
            >
              <Bell className="h-[1.1rem] w-[1.1rem]" />
              {unread > 0 && (
                <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose px-1 text-[9px] font-bold text-rose-contrast">
                  {unread > 9 ? "9+" : unread}
                </span>
              )}
            </button>

            <ThemeToggle />

            <button
              type="button"
              onClick={logout}
              aria-label="Sign out"
              className="hidden h-10 w-10 items-center justify-center rounded-full border border-border bg-surface text-ink-muted transition-colors hover:border-border-strong hover:text-ink sm:flex"
            >
              <LogOut className="h-[1.05rem] w-[1.05rem]" />
            </button>
          </div>
        </div>
      </header>

      <NotificationCenter open={notifOpen} onClose={() => setNotifOpen(false)} />
    </>
  );
}
