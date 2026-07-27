import { cn } from "@/lib/utils";

/** Tiny inline SVG sparkline — no chart lib, no hydration cost. */
export function Sparkline({
  data,
  className,
  stroke = "rgb(var(--rose))",
  fill = "rgb(var(--rose) / 0.12)",
  width = 96,
  height = 32,
}: {
  data: number[];
  className?: string;
  stroke?: string;
  fill?: string;
  width?: number;
  height?: number;
}) {
  if (!data || data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const stepX = width / (data.length - 1);
  const pts = data.map((d, i) => {
    const x = i * stepX;
    const y = height - ((d - min) / range) * (height - 4) - 2;
    return [x, y] as const;
  });
  const line = pts.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  const area = `${line} L${width} ${height} L0 ${height} Z`;
  return (
    <svg
      className={cn("overflow-visible", className)}
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      fill="none"
      aria-hidden
    >
      <path d={area} fill={fill} />
      <path d={line} stroke={stroke} strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={pts[pts.length - 1][0]} cy={pts[pts.length - 1][1]} r={2.25} fill={stroke} />
    </svg>
  );
}
