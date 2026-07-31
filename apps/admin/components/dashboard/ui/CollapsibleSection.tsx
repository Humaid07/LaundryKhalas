"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ComponentType,
  type ReactNode,
} from "react";
import { ChevronDown, ChevronsDownUp, ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Collapsible dashboard sections — lets an operator fold away Overview groups they
 * are not working with. State is per-section, persisted to localStorage under a
 * single key, and coordinated through a small context so an "Expand all / Collapse
 * all" control can drive every registered section at once. No backend involved.
 *
 * Collapsing hides only a section's CONTENT (via a grid-rows height animation) — the
 * header row stays visible so the section can always be reopened.
 */

type Ctx = {
  /** Current collapsed state for a section, falling back to its default. */
  isCollapsed: (id: string, defaultCollapsed: boolean) => boolean;
  /** Register a section so Expand/Collapse-all knows it exists. */
  register: (id: string, defaultCollapsed: boolean) => void;
  setCollapsed: (id: string, collapsed: boolean) => void;
  setAll: (collapsed: boolean) => void;
  hydrated: boolean;
};

const CollapseCtx = createContext<Ctx | null>(null);

const STORAGE_KEY = "laundrykhalas.dashboard.overview.collapsedSections";

export function CollapsibleSectionsProvider({ children }: { children: ReactNode }) {
  // Explicit user overrides only (id → collapsed). Sections not present here use
  // their own default. Empty on the server + first client render (avoids hydration
  // mismatch); localStorage is applied in the effect below.
  const [overrides, setOverrides] = useState<Record<string, boolean>>({});
  const [hydrated, setHydrated] = useState(false);
  const registry = useRef<Map<string, boolean>>(new Map());

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setOverrides(JSON.parse(raw) as Record<string, boolean>);
    } catch {
      /* ignore malformed / unavailable storage */
    }
    setHydrated(true);
  }, []);

  const write = useCallback((next: Record<string, boolean>) => {
    setOverrides(next);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      /* storage may be unavailable (private mode) — state still works in-session */
    }
  }, []);

  const register = useCallback((id: string, defaultCollapsed: boolean) => {
    registry.current.set(id, defaultCollapsed);
  }, []);

  const isCollapsed = useCallback(
    (id: string, defaultCollapsed: boolean) => overrides[id] ?? defaultCollapsed,
    [overrides],
  );

  const setCollapsed = useCallback(
    (id: string, collapsed: boolean) => write({ ...overrides, [id]: collapsed }),
    [overrides, write],
  );

  const setAll = useCallback(
    (collapsed: boolean) => {
      const next = { ...overrides };
      registry.current.forEach((_default, id) => {
        next[id] = collapsed;
      });
      write(next);
    },
    [overrides, write],
  );

  return (
    <CollapseCtx.Provider value={{ isCollapsed, register, setCollapsed, setAll, hydrated }}>
      {children}
    </CollapseCtx.Provider>
  );
}

/** Expand-all / Collapse-all buttons — place near the page header. No-op with no provider. */
export function CollapseAllControls({ className }: { className?: string }) {
  const ctx = useContext(CollapseCtx);
  if (!ctx) return null;
  const btn =
    "inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface px-2.5 py-1.5 text-xs font-medium text-ink-muted transition-colors hover:border-border-strong hover:text-ink focus:outline-none focus-visible:border-border-strong";
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <button type="button" onClick={() => ctx.setAll(false)} className={btn}>
        <ChevronsUpDown className="h-3.5 w-3.5" /> Expand all
      </button>
      <button type="button" onClick={() => ctx.setAll(true)} className={btn}>
        <ChevronsDownUp className="h-3.5 w-3.5" /> Collapse all
      </button>
    </div>
  );
}

export function CollapsibleDashboardSection({
  id,
  title,
  description,
  icon: Icon,
  defaultCollapsed = false,
  rightAction,
  children,
  className,
}: {
  id: string;
  title: ReactNode;
  description?: ReactNode;
  icon?: ComponentType<{ className?: string }>;
  defaultCollapsed?: boolean;
  /** Extra control shown left of the collapse button (e.g. a badge). */
  rightAction?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const ctx = useContext(CollapseCtx);
  const [localCollapsed, setLocalCollapsed] = useState(defaultCollapsed);

  useEffect(() => {
    ctx?.register(id, defaultCollapsed);
  }, [ctx, id, defaultCollapsed]);

  const collapsed = ctx ? ctx.isCollapsed(id, defaultCollapsed) : localCollapsed;
  const toggle = () => (ctx ? ctx.setCollapsed(id, !collapsed) : setLocalCollapsed((c) => !c));

  const contentId = `section-panel-${id}`;
  const headerId = `section-header-${id}`;

  return (
    <section className={cn("mb-6", className)} aria-labelledby={headerId}>
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2.5">
          {Icon && (
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-ink/8 text-ink-muted">
              <Icon className="h-4 w-4" />
            </span>
          )}
          <div className="min-w-0">
            <h2 id={headerId} className="font-display text-card-title font-semibold leading-tight text-ink">
              {title}
            </h2>
            {description && <p className="mt-0.5 truncate text-xs text-ink-muted">{description}</p>}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {rightAction}
          <button
            type="button"
            onClick={toggle}
            aria-expanded={!collapsed}
            aria-controls={contentId}
            aria-label={collapsed ? `Expand ${typeof title === "string" ? title : "section"}` : `Collapse ${typeof title === "string" ? title : "section"}`}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-surface text-ink-muted transition-colors hover:border-border-strong hover:text-ink focus:outline-none focus-visible:border-border-strong"
          >
            <ChevronDown className={cn("h-4 w-4 transition-transform duration-300", collapsed ? "rotate-0" : "rotate-180")} />
          </button>
        </div>
      </div>

      {/* grid-rows height animation: 1fr (open) → 0fr (collapsed), inner overflow hidden. */}
      <div
        id={contentId}
        role="region"
        aria-labelledby={headerId}
        aria-hidden={collapsed}
        className={cn(
          "grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none",
          collapsed ? "grid-rows-[0fr]" : "grid-rows-[1fr]",
        )}
      >
        <div
          className={cn(
            "min-h-0 overflow-hidden transition-opacity duration-200",
            collapsed ? "pointer-events-none opacity-0" : "opacity-100",
          )}
        >
          {children}
        </div>
      </div>
    </section>
  );
}
