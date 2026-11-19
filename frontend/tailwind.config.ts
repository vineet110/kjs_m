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
      keyframes: {
        // Offers ticker: slide left by half its width (the list is doubled), then repeat
        ticker: { from: { transform: "translateX(0)" }, to: { transform: "translateX(-50%)" } },
        // Loading screen: a light sheen sweeping across placeholder cards
        shimmer: { from: { transform: "translateX(-100%)" }, to: { transform: "translateX(100%)" } },
        // Loading screen: the gold bar running along the top
        progress: { "0%": { transform: "translateX(-100%)" }, "100%": { transform: "translateX(400%)" } },
        // Loading screen: product packs bobbing up and down
        float: { "0%, 100%": { transform: "translateY(0) rotate(-3deg)" }, "50%": { transform: "translateY(-14px) rotate(3deg)" } },
        // Products page, Coffee card: a steam wisp rising, widening and fading out
        steam: {
          "0%": { transform: "translateY(0) scaleX(1)", opacity: "0" },
          "25%": { opacity: "0.7" },
          "100%": { transform: "translateY(-56px) scaleX(1.8)", opacity: "0" },
        },
        // Products page, category cards: a gold shine sweeping left to right on hover
        shine: { from: { transform: "translateX(0) skewX(-12deg)" }, to: { transform: "translateX(400%) skewX(-12deg)" } },
        // Home hero: the striped line filling up while a slide shows (duration from site_ui.ini)
        heroline: { from: { width: "0%" }, to: { width: "100%" } },
        // Home partner strip: slide left by one copy of the list (duration set from its width and speed)
        marquee: { from: { transform: "translateX(0)" }, to: { transform: "translateX(-50%)" } },
      },
      backgroundImage: {
        // Gold-and-charcoal stripes (the hero's loading line)
        hazard: "repeating-linear-gradient(-45deg, #D9A930 0 8px, #111714 8px 16px)",
      },
      animation: {
        ticker: "ticker 40s linear infinite",
        shimmer: "shimmer 1.6s ease-in-out infinite",
        progress: "progress 1.4s ease-in-out infinite",
        float: "float 2.2s ease-in-out infinite",
        steam: "steam 2.7s ease-out infinite",
        shine: "shine 0.9s ease-out",
        heroline: "heroline 6s linear forwards", // duration overridden from site_ui.ini
        marquee: "marquee 40s linear infinite", // duration overridden from the strip's width and speed
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
export default config;
