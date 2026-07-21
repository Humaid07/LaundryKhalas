import { cn } from "@/lib/utils";

export function Avatar({ name, size = 40 }: { name: string; size?: number }) {
  const initials = name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("") || "LK";

  return (
    <div
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full bg-wa-accent-dark font-semibold text-white"
      )}
      style={{ width: size, height: size, fontSize: size * 0.38 }}
    >
      {initials}
    </div>
  );
}
