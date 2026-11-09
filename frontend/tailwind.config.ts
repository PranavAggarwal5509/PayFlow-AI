import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";
import palette from "tailwindcss/colors";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}", "./hooks/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "var(--font-inter)",
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Roboto",
          "Oxygen",
          "Ubuntu",
          "Cantarell",
          '"Fira Sans"',
          '"Droid Sans"',
          '"Helvetica Neue"',
          "sans-serif",
        ],
      },
      colors: {
        // One accent family across the product: legacy `blue-*` utilities render as indigo.
        blue: palette.indigo,
        canvas: "#f3f5fa",
        navy: { 950: "#070b16", 900: "#0b1222", 800: "#121a2e", 700: "#1c2640", 600: "#2a3655" },
        border: "hsl(var(--border))",
        input: "hsl(var(--border))",
        ring: "hsl(var(--primary))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: { DEFAULT: "hsl(var(--primary))", foreground: "hsl(var(--primary-foreground))" },
        muted: { DEFAULT: "hsl(var(--muted))", foreground: "hsl(var(--muted-foreground))" },
        card: { DEFAULT: "hsl(var(--card))", foreground: "hsl(var(--foreground))" },
        success: { DEFAULT: "#15803d", soft: "#f0fdf4", ring: "#bbf7d0" },
        warning: { DEFAULT: "#b45309", soft: "#fffbeb", ring: "#fde68a" },
        danger: { DEFAULT: "#b91c1c", soft: "#fef2f2", ring: "#fecaca" },
      },
      borderRadius: { xl: "1rem", lg: "0.75rem", md: "0.5rem", sm: "0.375rem" },
      boxShadow: {
        card: "0 1px 2px rgba(15,23,42,0.04), 0 2px 8px -2px rgba(15,23,42,0.06)",
        lift: "0 1px 2px rgba(15,23,42,0.04), 0 8px 24px -8px rgba(15,23,42,0.12)",
        pop: "0 12px 32px -8px rgba(15,23,42,0.18)",
        glow: "0 0 0 4px rgba(99,102,241,0.12)",
      },
      keyframes: {
        "fade-up": { from: { opacity: "0", transform: "translateY(6px)" }, to: { opacity: "1", transform: "none" } },
        shimmer: { from: { backgroundPosition: "200% 0" }, to: { backgroundPosition: "-200% 0" } },
        "pulse-ring": {
          "0%": { boxShadow: "0 0 0 0 rgba(99,102,241,0.45)" },
          "100%": { boxShadow: "0 0 0 10px rgba(99,102,241,0)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.35s ease-out both",
        shimmer: "shimmer 2.2s linear infinite",
        "pulse-ring": "pulse-ring 1.4s ease-out infinite",
      },
    },
  },
  plugins: [animate],
};

export default config;

