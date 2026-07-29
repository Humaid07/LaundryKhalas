"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

/**
 * Sidebar nav label that reveals its full text on hover / keyboard focus when it
 * is too long to fit — without widening the sidebar or shifting layout. Mirrors
 * the admin dashboard's NavLabel so both apps share one behaviour.
 *
 * - Fits: rendered plain, no animation.
 * - Overflows: the tail is hidden; on hover/focus of the enclosing `.lk-navrow`
 *   the text scrolls, then resets. The full label is always exposed via `title`.
 * - `prefers-reduced-motion`: no animation (CSS) — the tooltip remains.
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
