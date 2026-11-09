"use client";

import { useMemo } from "react";

import { usePrefersReducedMotion } from "@/hooks/use-motion";

const COLORS = ["#10b981", "#34d399", "#6366f1", "#a5b4fc", "#f59e0b", "#ffffff"];

/** One-shot celebratory burst for an approval watched live. Purely decorative; skipped under reduced motion. */
export function ConfettiBurst() {
  const reduced = usePrefersReducedMotion();
  const pieces = useMemo(
    () =>
      Array.from({ length: 28 }, (_, i) => {
        const angle = (i / 28) * Math.PI * 2 + Math.random() * 0.4;
        const distance = 90 + Math.random() * 110;
        return {
          id: i,
          x: Math.cos(angle) * distance,
          y: Math.sin(angle) * distance - 40,
          rotate: Math.round(Math.random() * 540 - 270),
          color: COLORS[i % COLORS.length],
          size: 6 + Math.round(Math.random() * 5),
          delay: Math.round(Math.random() * 120),
          round: i % 3 === 0,
        };
      }),
    [],
  );
  if (reduced) return null;
  return (
    <div aria-hidden className="pointer-events-none absolute left-1/2 top-12 z-10 h-0 w-0">
      {pieces.map((p) => (
        <span
          key={p.id}
          className="confetti-piece"
          style={
            {
              background: p.color,
              width: p.size,
              height: p.round ? p.size : p.size * 0.45,
              borderRadius: p.round ? 9999 : 2,
              animationDelay: `${p.delay}ms`,
              ["--x" as string]: `${p.x}px`,
              ["--y" as string]: `${p.y}px`,
              ["--r" as string]: `${p.rotate}deg`,
            } as React.CSSProperties
          }
        />
      ))}
    </div>
  );
}
