/** Shared UI types for the facility dashboard. */

export type Tone = "rose" | "success" | "warning" | "danger" | "info" | "neutral" | "plum";

/** A single point on a time-series chart. `label` is the x-axis category;
 *  every other key is a numeric (or string) series value. */
export interface TimeSeriesPoint {
  label: string;
  [key: string]: string | number;
}
