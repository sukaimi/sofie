/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      // Cypher Seven identity — dark ground, decisive red, muted grey support.
      colors: {
        ground: "#0A0A0A",
        surface: { DEFAULT: "#131313", 2: "#1A1A1A" },
        hairline: { DEFAULT: "#2A2A2A", strong: "#3B3B3B" },
        ink: "#FFFFFF",
        muted: { DEFAULT: "#8A8A8A", dim: "#5E5E5E" },
        accent: { DEFAULT: "#BF0606", bright: "#E5484D" },
        good: "#46B26B",
        warn: "#E0A020",
      },
      fontFamily: {
        display: ["Satoshi", "Neue Montreal", "Helvetica Neue", "Arial", "sans-serif"],
        sans: ['"IBM Plex Sans"', "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        glow: "0 8px 30px rgba(191, 6, 6, 0.25)",
        "glow-sm": "0 0 0 1px rgba(255,255,255,0.05), 0 6px 20px rgba(191,6,6,0.20)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.35s ease both",
      },
    },
  },
  plugins: [],
};
