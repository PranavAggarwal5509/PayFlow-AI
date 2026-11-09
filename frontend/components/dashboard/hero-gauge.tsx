"use client";

import { useCountUp, useMounted } from "@/hooks/use-motion";
import { formatMoney } from "@/lib/format";

const R = 54;
const CIRC = 2 * Math.PI * R;

/** Glass panel on the hero band: touchless rate ring + money cleared vs held. */
export function HeroGauge({
  rate,
  cleared,
  held,
  blocked,
  loading,
}: {
  rate: number | null | undefined;
  cleared: number;
  held: number;
  blocked: number;
  loading: boolean;
}) {
  const mounted = useMounted();
  const value = useCountUp(loading ? 0 : rate ?? 0, 1200);
  const target = Math.max(0, Math.min(100, rate ?? 0));
  const offset = CIRC * (1 - (mounted && !loading ? target : 0) / 100);
  const max = Math.max(cleared, held, blocked, 1);

  const rows = [
    { label: "Cleared", value: cleared, bar: "bg-emerald-400" },
    { label: "Held", value: held, bar: "bg-amber-400" },
    { label: "Blocked", value: blocked, bar: "bg-rose-400" },
  ];

  return (
    <div className="glass flex w-full flex-wrap items-center gap-5 rounded-2xl bg-navy-900/60 p-5 sm:flex-nowrap shadow-[0_20px_60px_-20px_rgba(79,70,229,0.55)] lg:w-auto">
      <div className="relative h-[132px] w-[132px] shrink-0">
        <svg viewBox="0 0 132 132" className="h-full w-full -rotate-90" aria-hidden>
          <defs>
            <linearGradient id="gauge-grad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#34d399" />
              <stop offset="100%" stopColor="#818cf8" />
            </linearGradient>
          </defs>
          <circle cx="66" cy="66" r={R} fill="none" stroke="rgb(255 255 255 / 0.08)" strokeWidth="11" />
          <circle
            cx="66"
            cy="66"
            r={R}
            fill="none"
            stroke="url(#gauge-grad)"
            strokeWidth="11"
            strokeLinecap="round"
            strokeDasharray={CIRC}
            strokeDashoffset={offset}
            style={{ transition: "stroke-dashoffset 1.3s cubic-bezier(0.22, 1, 0.36, 1)" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center text-white">
          <span className="tabular text-[30px] font-semibold leading-none">{Math.round(value)}%</span>
          <span className="mt-1 text-[10.5px] font-semibold uppercase tracking-[0.14em] text-slate-400">Touchless</span>
        </div>
      </div>
      <div className="min-w-[190px] flex-1">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-indigo-300">Invoice value · INR</p>
        <ul className="mt-3 space-y-2.5">
          {rows.map((row, i) => (
            <li key={row.label}>
              <div className="flex items-baseline justify-between gap-3 text-[12.5px]">
                <span className="text-slate-300">{row.label}</span>
                <span className="tabular font-semibold text-white">{formatMoney(row.value, "INR")}</span>
              </div>
              <div className="mt-1 h-1 overflow-hidden rounded-full bg-white/10">
                <div
                  className={`h-full rounded-full ${row.bar}`}
                  style={{
                    width: mounted && !loading ? `${(row.value / max) * 100}%` : "0%",
                    transition: `width 1s cubic-bezier(0.22, 1, 0.36, 1) ${0.2 + i * 0.12}s`,
                  }}
                />
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
