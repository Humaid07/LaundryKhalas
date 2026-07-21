import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        wa: {
          panel: "#f0f2f5",
          sidebar: "#ffffff",
          border: "#e9edef",
          bg: "#efeae2",
          outgoing: "#d9fdd3",
          incoming: "#ffffff",
          accent: "#00a884",
          "accent-dark": "#008069",
          text: "#111b21",
          muted: "#667781",
          danger: "#e53935",
          warning: "#f0ad4e",
        },
      },
      borderRadius: {
        bubble: "7.5px",
      },
    },
  },
  plugins: [],
};
export default config;
