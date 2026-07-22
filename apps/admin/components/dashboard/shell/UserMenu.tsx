"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/dashboard/auth-context";

function initials(name: string | null | undefined, email: string): string {
  const source = (name && name.trim()) || email;
  const parts = source.split(/[\s@._-]+/).filter(Boolean);
  const letters = (parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "");
  return (letters || source.slice(0, 2)).toUpperCase();
}

const ROLE_LABEL: Record<string, string> = {
  admin: "Administrator",
  operations: "Operations",
};

/** Topbar account chip wired to the real authenticated user, with a sign-out
 *  action. Falls back to nothing when the auth context has no user yet. */
export function UserMenu() {
  const { user, role, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!user) return null;

  const name = user.full_name || user.email;
  const roleLabel = (role && ROLE_LABEL[role]) || "Member";

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-2 rounded-lg border border-border bg-surface py-1 pl-1 pr-2 transition-colors hover:border-border-strong"
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-md bg-rose/12 font-display text-xs font-bold text-rose">
          {initials(user.full_name, user.email)}
        </span>
        <span className="hidden text-left leading-tight md:block">
          <span className="block max-w-[9rem] truncate text-xs font-semibold text-ink">{name}</span>
          <span className="block text-xxs text-ink-faint">{roleLabel}</span>
        </span>
        <ChevronDown className={cn("hidden h-3.5 w-3.5 text-ink-faint transition-transform md:block", open && "rotate-180")} />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-[calc(100%+6px)] z-50 w-56 overflow-hidden rounded-xl border border-border bg-surface shadow-pop"
        >
          <div className="border-b border-border px-3 py-2.5">
            <p className="truncate text-sm font-semibold text-ink">{name}</p>
            <p className="truncate text-xs text-ink-faint">{user.email}</p>
            <span className="mt-1 inline-block rounded-full bg-rose/10 px-2 py-0.5 text-xxs font-semibold text-rose">
              {roleLabel}
            </span>
          </div>
          <button
            type="button"
            role="menuitem"
            onClick={logout}
            className="flex w-full items-center gap-2 px-3 py-2.5 text-left text-sm font-medium text-ink-muted transition-colors hover:bg-surface-2 hover:text-ink"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
