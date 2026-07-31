import { cn } from "@/lib/utils";

/** LaundryKhalas logo mark — transparent PNG, reads on light or dark surfaces. */
export function BrandMark({ className }: { className?: string }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src="/brand/laundrykhalas-logo.png"
      alt="LaundryKhalas"
      width={36}
      height={36}
      className={cn("h-9 w-9 shrink-0 object-contain", className)}
    />
  );
}

export function BrandWordmark({ collapsed }: { collapsed?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <BrandMark />
      {!collapsed && (
        <div className="leading-tight">
          <p className="font-display text-card-title font-bold tracking-tight text-ink">LaundryKhalas</p>
          <p className="text-xxs font-medium uppercase tracking-eyebrow text-ink-faint">Partner Portal</p>
        </div>
      )}
    </div>
  );
}
