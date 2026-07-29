"use client";

import { useEffect, useState } from "react";
import { Bell, Menu, Search } from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";
import { UserMenu } from "./UserMenu";
import { CommandPalette } from "./CommandPalette";

export function Topbar({ onOpenMobile }: { onOpenMobile: () => void }) {
  const [paletteOpen, setPaletteOpen] = useState(false);

  // Global ⌘K / Ctrl+K opens the command palette.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

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

      {/* Search → opens the command palette */}
      <button
        type="button"
        onClick={() => setPaletteOpen(true)}
        aria-label="Search and jump to a section"
        aria-keyshortcuts="Meta+K Control+K"
        className="relative hidden max-w-md flex-1 items-center gap-2 rounded-lg border border-border bg-surface pl-9 pr-2 text-left transition-colors hover:border-border-strong sm:flex"
      >
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
        <span className="h-9 flex-1 truncate py-2 text-sm text-ink-faint">Search orders, customers, conversations…</span>
        <kbd className="hidden shrink-0 rounded border border-border bg-surface-2 px-1.5 py-0.5 text-xxs font-medium text-ink-faint md:block">
          ⌘K
        </kbd>
      </button>

      <div className="flex flex-1 items-center justify-end gap-2 sm:flex-none">
        {/* Mobile search icon */}
        <button
          type="button"
          onClick={() => setPaletteOpen(true)}
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

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </header>
  );
}
