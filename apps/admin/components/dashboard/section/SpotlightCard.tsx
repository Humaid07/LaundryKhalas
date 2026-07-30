"use client";

import { useRef, type ReactNode } from "react";
import Link from "next/link";

/**
 * Client wrapper that adds the tuned "spotlight" glow to a card-shaped link: a
 * soft radial highlight (in the given accent colour) that tracks the pointer and
 * fades in on hover. No 3D tilt, no sibling-dimming, no rainbow aurora — calm and
 * readable for a data cockpit, theme-aware (the accent token differs per theme),
 * and reduced-motion safe (opacity only; the pointer-follow is not an animation).
 *
 * It takes only serializable props + server-rendered ``children`` so a Server
 * Component (SectionCard/SectionLanding) can compose it without crossing the RSC
 * boundary with a non-serializable icon component.
 */
export function SpotlightCard({
  href,
  glowVar,
  className,
  children,
}: {
  href: string;
  /** CSS colour variable (R G B triplet) for the glow, e.g. "--accent-teal". */
  glowVar: string;
  className?: string;
  children: ReactNode;
}) {
  const ref = useRef<HTMLAnchorElement>(null);

  const onMouseMove = (e: React.MouseEvent<HTMLAnchorElement>) => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    el.style.setProperty("--spot-x", `${e.clientX - r.left}px`);
    el.style.setProperty("--spot-y", `${e.clientY - r.top}px`);
  };

  return (
    <Link ref={ref} href={href} onMouseMove={onMouseMove} className={className}>
      {/* Spotlight glow — below the content (z-0) so text never washes out. */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 z-0 opacity-0 transition-opacity duration-300 ease-out-quint group-hover:opacity-100 motion-reduce:transition-none"
        style={{
          background: `radial-gradient(260px circle at var(--spot-x, 50%) var(--spot-y, 0%), rgb(var(${glowVar}) / 0.14), transparent 72%)`,
        }}
      />
      {children}
    </Link>
  );
}
