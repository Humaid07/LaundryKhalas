"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { CATEGORICAL, CHART, tooltipItemStyle, tooltipLabelStyle, tooltipStyle } from "@/lib/dashboard/chart-theme";
import type { TimeSeriesPoint } from "@/lib/dashboard/types";

const axisProps = {
  stroke: CHART.axis,
  tick: { fill: "rgb(var(--ink-faint))", fontSize: 11, fontFamily: "var(--font-body)" },
  tickLine: false,
  axisLine: false,
} as const;

type Series = { key: string; color: string; name?: string };

const commonTooltip = (
  <Tooltip
    contentStyle={tooltipStyle}
    itemStyle={tooltipItemStyle}
    labelStyle={tooltipLabelStyle}
    cursor={{ fill: "rgb(var(--ink) / 0.04)" }}
  />
);

/* --------------------------------- Area trend -------------------------------- */

export function AreaTrend({
  data,
  series,
  height = 260,
  stacked = false,
  currency = false,
}: {
  data: TimeSeriesPoint[];
  series: Series[];
  height?: number;
  stacked?: boolean;
  currency?: boolean;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 6, left: -12, bottom: 0 }}>
        <defs>
          {series.map((s) => (
            <linearGradient key={s.key} id={`grad-${s.key}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={s.color} stopOpacity={0.32} />
              <stop offset="100%" stopColor={s.color} stopOpacity={0.02} />
            </linearGradient>
          ))}
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
        <XAxis dataKey="label" {...axisProps} />
        <YAxis
          {...axisProps}
          width={48}
          tickFormatter={(v) => (currency ? `${(v / 1000).toFixed(0)}k` : `${v}`)}
        />
        {commonTooltip}
        {series.map((s) => (
          <Area
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.name ?? s.key}
            stroke={s.color}
            strokeWidth={2}
            fill={`url(#grad-${s.key})`}
            stackId={stacked ? "1" : undefined}
            dot={false}
            activeDot={{ r: 4, strokeWidth: 0 }}
          />
        ))}
        {series.length > 1 && (
          <Legend
            iconType="circle"
            iconSize={8}
            wrapperStyle={{ fontSize: 12, color: "rgb(var(--ink-muted))", paddingTop: 8 }}
          />
        )}
      </AreaChart>
    </ResponsiveContainer>
  );
}

/* --------------------------------- Line trend -------------------------------- */

export function LineTrend({
  data,
  series,
  height = 260,
}: {
  data: TimeSeriesPoint[];
  series: Series[];
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 6, left: -12, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
        <XAxis dataKey="label" {...axisProps} />
        <YAxis {...axisProps} width={40} />
        {commonTooltip}
        {series.map((s) => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.name ?? s.key}
            stroke={s.color}
            strokeWidth={2.25}
            dot={false}
            activeDot={{ r: 4, strokeWidth: 0 }}
          />
        ))}
        {series.length > 1 && (
          <Legend
            iconType="circle"
            iconSize={8}
            wrapperStyle={{ fontSize: 12, color: "rgb(var(--ink-muted))", paddingTop: 8 }}
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}

/* ---------------------------------- Bars ------------------------------------ */

export function BarSeries({
  data,
  height = 260,
  color = CHART.rose,
  horizontal = false,
  currency = false,
  colorByIndex = false,
}: {
  data: TimeSeriesPoint[];
  height?: number;
  color?: string;
  horizontal?: boolean;
  currency?: boolean;
  colorByIndex?: boolean;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart
        data={data}
        layout={horizontal ? "vertical" : "horizontal"}
        margin={{ top: 8, right: 12, left: horizontal ? 8 : -12, bottom: 0 }}
        barCategoryGap={horizontal ? "22%" : "32%"}
      >
        <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} horizontal={!horizontal} vertical={horizontal} />
        {horizontal ? (
          <>
            <XAxis
              type="number"
              {...axisProps}
              tickFormatter={(v) => (currency ? `${(v / 1000).toFixed(0)}k` : `${v}`)}
            />
            <YAxis type="category" dataKey="label" {...axisProps} width={128} />
          </>
        ) : (
          <>
            <XAxis type="category" dataKey="label" {...axisProps} interval={0} angle={0} />
            <YAxis
              type="number"
              {...axisProps}
              width={44}
              tickFormatter={(v) => (currency ? `${(v / 1000).toFixed(0)}k` : `${v}`)}
            />
          </>
        )}
        <Tooltip
          contentStyle={tooltipStyle}
          itemStyle={tooltipItemStyle}
          labelStyle={tooltipLabelStyle}
          cursor={{ fill: "rgb(var(--ink) / 0.04)" }}
        />
        <Bar dataKey="value" radius={horizontal ? [0, 6, 6, 0] : [6, 6, 0, 0]} maxBarSize={horizontal ? 20 : 46}>
          {data.map((_, i) => (
            <Cell key={i} fill={colorByIndex ? CATEGORICAL[i % CATEGORICAL.length] : color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/* -------------------------------- Grouped bars ------------------------------ */

export function GroupedBars({
  data,
  series,
  height = 260,
}: {
  data: TimeSeriesPoint[];
  series: Series[];
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 6, left: -12, bottom: 0 }} barCategoryGap="26%">
        <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
        <XAxis dataKey="label" {...axisProps} />
        <YAxis {...axisProps} width={44} tickFormatter={(v) => (v >= 1000 ? `${(v / 1000).toFixed(0)}k` : `${v}`)} />
        {commonTooltip}
        {series.map((s) => (
          <Bar key={s.key} dataKey={s.key} name={s.name ?? s.key} fill={s.color} radius={[5, 5, 0, 0]} maxBarSize={26} />
        ))}
        <Legend
          iconType="circle"
          iconSize={8}
          wrapperStyle={{ fontSize: 12, color: "rgb(var(--ink-muted))", paddingTop: 8 }}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}

/* --------------------------------- Donut ------------------------------------ */

export function DonutChart({
  data,
  height = 260,
  colors = CATEGORICAL,
  centerLabel,
  centerValue,
}: {
  data: TimeSeriesPoint[];
  height?: number;
  colors?: readonly string[];
  centerLabel?: string;
  centerValue?: string;
}) {
  return (
    <div className="relative">
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="label"
            innerRadius="62%"
            outerRadius="88%"
            paddingAngle={2}
            stroke="rgb(var(--surface))"
            strokeWidth={2}
          >
            {data.map((_, i) => (
              <Cell key={i} fill={colors[i % colors.length]} />
            ))}
          </Pie>
          <Tooltip contentStyle={tooltipStyle} itemStyle={tooltipItemStyle} labelStyle={tooltipLabelStyle} />
          <Legend
            iconType="circle"
            iconSize={8}
            wrapperStyle={{ fontSize: 12, color: "rgb(var(--ink-muted))", paddingTop: 4 }}
          />
        </PieChart>
      </ResponsiveContainer>
      {centerValue && (
        <div
          className="pointer-events-none absolute inset-x-0 flex flex-col items-center"
          style={{ top: height * 0.5 - 34 }}
        >
          <span className="font-mono text-xl font-semibold text-ink tnum">{centerValue}</span>
          {centerLabel && <span className="text-xxs uppercase tracking-eyebrow text-ink-faint">{centerLabel}</span>}
        </div>
      )}
    </div>
  );
}
