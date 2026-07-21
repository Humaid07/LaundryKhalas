"use client";

import { useEffect, useState, type ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export function AppShell({ children }: { children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  // Restore collapse preference
  useEffect(() => {
    setCollapsed(localStorage.getItem("lk-sidebar-collapsed") === "1");
  }, []);
  const toggleCollapse = () => {
    setCollapsed((c) => {
      localStorage.setItem("lk-sidebar-collapsed", c ? "0" : "1");
      return !c;
    });
  };

  // Lock scroll + close drawer on Escape when the mobile drawer is open
  useEffect(() => {
    if (!mobileOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMobileOpen(false);
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [mobileOpen]);

  return (
    <div className="min-h-screen bg-canvas">
      {/* Desktop sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 hidden border-r border-border transition-[width] duration-300 ease-out-quint lg:block",
          collapsed ? "w-[76px]" : "w-64",
        )}
      >
        <Sidebar collapsed={collapsed} onToggleCollapse={toggleCollapse} />
      </aside>

      {/* Mobile drawer */}
      <div className={cn("lg:hidden", mobileOpen ? "pointer-events-auto" : "pointer-events-none")}>
        <div
          onClick={() => setMobileOpen(false)}
          className={cn(
            "fixed inset-0 z-40 bg-ink/40 backdrop-blur-sm transition-opacity duration-300",
            mobileOpen ? "opacity-100" : "opacity-0",
          )}
        />
        <aside
          className={cn(
            "fixed inset-y-0 left-0 z-50 w-[280px] border-r border-border shadow-pop transition-transform duration-300 ease-out-quint",
            mobileOpen ? "translate-x-0" : "-translate-x-full",
          )}
        >
          <button
            type="button"
            onClick={() => setMobileOpen(false)}
            aria-label="Close navigation"
            className="absolute right-3 top-4 z-10 flex h-8 w-8 items-center justify-center rounded-lg text-ink-muted hover:bg-surface-2 hover:text-ink"
          >
            <X className="h-4 w-4" />
          </button>
          <Sidebar collapsed={false} onNavigate={() => setMobileOpen(false)} />
        </aside>
      </div>

      {/* Main column */}
      <div className={cn("flex min-h-screen flex-col transition-[padding] duration-300 ease-out-quint", collapsed ? "lg:pl-[76px]" : "lg:pl-64")}>
        <Topbar onOpenMobile={() => setMobileOpen(true)} />
        <main className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-6 md:px-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
