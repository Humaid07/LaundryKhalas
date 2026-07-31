import type { Config } from "tailwindcss";
import designPreset from "../../packages/design/tailwind-preset";

// Theme (tokens, colours, fonts, radius, shadow, type scale) lives in the shared
// preset at packages/design/ so both dashboards stay in lockstep. This file only
// declares this app's content globs. The preset is intentionally dependency-free
// (see packages/design/README.md), so it is cast to Tailwind's preset shape here.
const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  presets: [designPreset as unknown as Partial<Config>],
};

export default config;
