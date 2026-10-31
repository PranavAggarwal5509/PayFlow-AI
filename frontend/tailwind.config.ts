import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
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
      borderRadius: { lg: "0.625rem", md: "0.5rem", sm: "0.375rem" },
      boxShadow: {
        card: "0 1px 2px rgba(15,23,42,0.04), 0 1px 3px rgba(15,23,42,0.05)",
        pop: "0 8px 24px rgba(15,23,42,0.12)",
      },
    },
  },
  plugins: [animate],
};

export default config;

