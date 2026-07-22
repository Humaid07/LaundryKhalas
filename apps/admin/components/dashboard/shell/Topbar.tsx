"use client";

import { Bell, Menu, Search } from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";
import { UserMenu } from "./UserMenu";

export function Topbar({ onOpenMobile }: { onOpenMobile: () => void }) {
  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-border bg-canvas/85 px-4 backdrop-blur-md md:px-6">
      {/* Mobile hamburger */}
      <button
        type="button"
        onClick={onOpenMobile}
        aria-label="Open navigation"
        className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-surface text-ink-muted transition-colors hover:text-ink lg:hidden"
      >
        <Menu className="h-4 w-4" />
      </button>

      {/* Search */}
      <div className="relative hidden max-w-md flex-1 sm:block">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
        <input
          type="search"
          placeholder="Search orders, customers, conversations…"
          className="h-9 w-full rounded-lg border border-border bg-surface pl-9 pr-16 text-sm text-ink placeholder:text-ink-faint transition-colors hover:border-border-strong focus:border-rose focus-visible:outline-none"
        />
        <kbd className="absolute right-2.5 top-1/2 hidden -translate-y-1/2 rounded border border-border bg-surface-2 px-1.5 py-0.5 text-xxs font-medium text-ink-faint md:block">
          ⌘K
        </kbd>
      </div>

      <div className="flex flex-1 items-center justify-end gap-2 sm:flex-none">
        {/* Mobile search icon */}
        <button
          type="button"
          aria-label="Search"
          className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-surface text-ink-muted hover:text-ink sm:hidden"
        >
          <Search className="h-4 w-4" />
        </button>

        <ThemeToggle />

        {/* Notifications */}
        <button
          type="button"
          aria-label="Notifications"
          className="relative flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-surface text-ink-muted transition-colors hover:border-border-strong hover:text-ink"
        >
          <Bell className="h-4 w-4" />
          <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-rose ring-2 ring-surface" />
        </button>

        {/* Profile + sign out */}
        <UserMenu />
      </div>
    </header>
  );
}
