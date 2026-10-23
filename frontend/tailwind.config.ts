import type { Config } from "tailwindcss";

// Design tokens. Gold + charcoal come from the KJS logo; forest green from the demo video.
const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        gold: { DEFAULT: "#D9A930", light: "#F2D27A", dark: "#A87E14" },
        ink: { DEFAULT: "#111714", soft: "#1E2823" },
        forest: { DEFAULT: "#123A2B", light: "#1E5641" },
        paper: "#F7F5F0",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
export default config;
