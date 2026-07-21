import { cn } from "@/lib/utils";

/** LaundryKhalas mark — a rose droplet inside a soft-cornered tile. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-rose text-rose-contrast shadow-rose-glow",
        className,
      )}
    >
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" aria-hidden>
        <path
          d="M12 3.2c2.9 3.2 5 5.9 5 8.7a5 5 0 0 1-10 0c0-2.8 2.1-5.5 5-8.7Z"
          fill="currentColor"
          opacity="0.95"
        />
        <path
          d="M9.6 12.4c0 1.6 1 2.7 2.4 2.9"
          stroke="rgb(var(--rose))"
          strokeWidth="1.4"
          strokeLinecap="round"
        />
      </svg>
    </span>
  );
}

export function BrandWordmark({ collapsed }: { collapsed?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <BrandMark />
      {!collapsed && (
        <div className="leading-tight">
          <p className="font-display text-[0.95rem] font-bold tracking-tight text-ink">LaundryKhalas</p>
          <p className="text-xxs font-medium uppercase tracking-eyebrow text-ink-faint">Command Center</p>
        </div>
      )}
    </div>
  );
}
