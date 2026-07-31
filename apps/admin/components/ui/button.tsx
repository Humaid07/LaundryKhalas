import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "danger" | "ghost";
type Size = "sm" | "md";

const VARIANT_CLASSES: Record<Variant, string> = {
  primary: "bg-rose text-rose-contrast hover:bg-rose-strong disabled:bg-rose/50",
  secondary:
    "bg-surface text-ink border border-border-strong hover:bg-surface-2 disabled:text-ink-faint",
  danger: "bg-danger text-canvas hover:bg-danger/90 disabled:bg-danger/50",
  ghost: "text-ink-muted hover:bg-surface-2 disabled:text-ink-faint",
};

const SIZE_CLASSES: Record<Size, string> = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
};

export function Button({
  variant = "secondary",
  size = "md",
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors duration-150 disabled:cursor-not-allowed",
        VARIANT_CLASSES[variant],
        SIZE_CLASSES[size],
        className
      )}
      {...props}
    />
  );
}
