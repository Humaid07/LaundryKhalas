"use client";

import { useEffect, useState } from "react";
import { Bell, Menu, Search } from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";
import { UserMenu } from "./UserMenu";
import { TopbarSearch } from "./TopbarSearch";

export function Topbar({ onOpenMobile }: { onOpenMobile: () => void }) {
  const [searchOpen, setSearchOpen] = useState(false);

  // Global ⌘K / Ctrl+K opens the search suggestions.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen((o) => !o);
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
        className="lk-control lk-control--pill lg:hidden"
      >
        <Menu className="h-4 w-4" />
      </button>

      {/* Search → inline suggestions dropdown (no modal / no page overlay) */}
      <TopbarSearch open={searchOpen} onOpenChange={setSearchOpen} />

      <div className="flex flex-1 items-center justify-end gap-2 sm:flex-none">
        {/* Mobile search icon */}
        <button
          type="button"
          data-search-trigger
          onClick={() => setSearchOpen((o) => !o)}
          aria-label="Search"
          aria-expanded={searchOpen}
          className="lk-control lk-control--pill sm:hidden"
        >
          <Search className="h-4 w-4" />
        </button>

        <ThemeToggle />

        {/* Notifications */}
        <button
          type="button"
          aria-label="Notifications"
          className="lk-control lk-control--pill relative"
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
