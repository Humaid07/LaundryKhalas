"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

/**
 * Sidebar nav label that reveals its full text on hover / keyboard focus when it
 * is too long to fit — without widening the sidebar or shifting layout.
 *
 * - Fits: rendered plain (truncated), no animation.
 * - Overflows: the tail is hidden; on hover or keyboard focus of the enclosing
 *   row (`.lk-navrow`) the text scrolls horizontally, then resets. The full label
 *   is always exposed via `title` for the pointer tooltip + screen readers.
 * - `prefers-reduced-motion`: no animation (CSS handles it) — the tooltip remains.
 *
 * The row element must carry the `lk-navrow` class and be the focusable element
 * (the <Link>), so `:hover`/`:focus-visible` drive the scroll. Keyframes live in
 * app/globals.css (`lk-navlabel-scroll`). The same component is mirrored in the
 * facility portal so both dashboards share one behaviour.
 */
export function NavLabel({ label, className }: { label: string; className?: string }) {
  const wrapRef = useRef<HTMLSpanElement>(null);
  const textRef = useRef<HTMLSpanElement>(null);
  const [overflow, setOverflow] = useState(0);

  useEffect(() => {
    const wrap = wrapRef.current;
    const text = textRef.current;
    if (!wrap || !text) return;
    const measure = () => {
      const diff = text.scrollWidth - wrap.clientWidth;
      setOverflow(diff > 2 ? diff : 0);
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(wrap);
    ro.observe(text);
    return () => ro.disconnect();
  }, [label]);

  return (
    <span
      ref={wrapRef}
      title={label}
      className={cn("block min-w-0 overflow-hidden whitespace-nowrap", overflow > 0 && "lk-navlabel", className)}
    >
      <span
        ref={textRef}
        className="lk-navlabel__text inline-block align-top"
        style={overflow > 0 ? ({ ["--lk-scroll" as string]: `-${overflow}px` } as React.CSSProperties) : undefined}
      >
        {label}
      </span>
    </span>
  );
}
