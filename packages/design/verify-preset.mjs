// packages/design/verify-preset.mjs
// Guard: the token maps must expose the required keys and match in count.
// Run: node packages/design/verify-preset.mjs  (needs Node TS-strip; the build
// is the authoritative gate if this Node lacks it).
import { LIGHT_TOKENS, DARK_TOKENS } from "./tokens.ts";

const REQUIRED = [
  "canvas", "surface", "border", "ink", "rose", "success", "warning",
  "danger", "info", "accent-orange", "ring", "shadow-color",
];
const missingL = REQUIRED.filter((k) => !(k in LIGHT_TOKENS));
const missingD = REQUIRED.filter((k) => !(k in DARK_TOKENS));
if (missingL.length || missingD.length) {
  console.error("Missing tokens — light:", missingL, "dark:", missingD);
  process.exit(1);
}
if (Object.keys(LIGHT_TOKENS).length !== Object.keys(DARK_TOKENS).length) {
  console.error("Light/dark token counts differ.");
  process.exit(1);
}
console.log("preset tokens OK:", Object.keys(LIGHT_TOKENS).length, "tokens x2 themes");
