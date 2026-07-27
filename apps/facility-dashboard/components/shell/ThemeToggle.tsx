"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";
import { cn } from "@/lib/utils";

/** Light/dark toggle. Renders a stable placeholder until mounted to avoid a
 *  hydration mismatch (theme is only known client-side). */
export function ThemeToggle({ className }: { className?: string }) {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const isDark = resolvedTheme === "dark";
  return (
    <button
      type="button"
      aria-label="Toggle theme"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      className={cn(
        "flex h-10 w-10 items-center justify-center rounded-full border border-border bg-surface text-ink-muted transition-colors hover:border-border-strong hover:text-ink",
        className,
      )}
    >
      {mounted && isDark ? <Sun className="h-[1.15rem] w-[1.15rem]" /> : <Moon className="h-[1.1rem] w-[1.1rem]" />}
    </button>
  );
}
