"use client";

import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { useCountUp, useMounted } from "@/hooks/use-motion";
import { cn } from "@/lib/utils";
import type { Kpi } from "@/types/api";

const ACCENTS = {
  neutral: { icon: "bg-indigo-50 text-indigo-600 ring-indigo-100", bar: "bg-indigo-500", glow: "from-indigo-500/15", stroke: "#6366f1" },
  success: { icon: "bg-emerald-50 text-emerald-600 ring-emerald-100", bar: "bg-emerald-500", glow: "from-emerald-500/15", stroke: "#10b981" },
  warning: { icon: "bg-amber-50 text-amber-600 ring-amber-100", bar: "bg-amber-500", glow: "from-amber-500/15", stroke: "#f59e0b" },
  danger: { icon: "bg-rose-50 text-rose-600 ring-rose-100", bar: "bg-rose-500", glow: "from-rose-500/15", stroke: "#f43f5e" },
} as const;

/** Headline metric: counts up on load, share-of-total meter grows in, optional sparkline draws itself. */
export function KpiCard({
  label,
  kpi,
  accent = "neutral",
  loading,
  icon,
  href,
  total,
  caption,
  spark,
  style,
  className,
}: {
  label: string;
  kpi?: Kpi;
  accent?: keyof typeof ACCENTS;
  loading?: boolean;
  icon?: ReactNode;
  href?: string;
  total?: number;
  caption?: string;
  spark?: number[];
  style?: CSSProperties;
  className?: string;
}) {
  const config = ACCENTS[accent];
  const value = kpi?.value ?? 0;
  const shown = useCountUp(value);
  const mounted = useMounted();
  const share = total ? Math.round((value / Math.max(total, 1)) * 100) : null;

  const content = (
    <div
      className={cn(
        "group relative h-full overflow-hidden rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card transition-all duration-200",
        href && "hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-lift",
      )}
    >
      <div className={cn("pointer-events-none absolute -right-12 -top-12 h-36 w-36 rounded-full bg-gradient-to-br to-transparent blur-2xl transition-opacity duration-300 group-hover:opacity-100", config.glow)} />
      <div className="relative flex items-start justify-between gap-3">
        <span className={cn("flex h-10 w-10 items-center justify-center rounded-xl ring-1 ring-inset transition-transform duration-200 group-hover:scale-105", config.icon)}>
          {icon}
        </span>
        {href && <ArrowUpRight className="h-4 w-4 text-slate-300 transition-all duration-200 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-indigo-500" aria-hidden />}
      </div>
      <p className="relative mt-4 text-[13px] font-medium text-slate-500">{label}</p>
      <div className="relative mt-1 flex items-end justify-between gap-3">
        {loading || !kpi ? (
          <Skeleton className="h-9 w-20" />
        ) : (
          <p className="tabular text-[36px] font-semibold leading-none tracking-tight text-slate-900" aria-label={`${value}`}>
            {Math.round(shown).toLocaleString()}
          </p>
        )}
        {spark && spark.length > 1 && <Sparkline points={spark} color={config.stroke} />}
      </div>
      <div className="relative mt-4">
        {share !== null ? (
          <>
            <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
              <div
                className={cn("h-full rounded-full", config.bar)}
                style={{ width: mounted && kpi ? `${share}%` : "0%", transition: "width 1.1s cubic-bezier(0.22, 1, 0.36, 1) 0.25s" }}
              />
            </div>
            <p className="mt-1.5 text-[11.5px] text-slate-500">
              <span className="tabular font-semibold text-slate-700">{share}%</span> {caption ?? "of processed invoices"}
            </p>
          </>
        ) : (
          <p className="text-[11.5px] text-slate-500">
            <span className="tabular font-semibold text-slate-700">{kpi?.last_30_days ?? 0}</span> {caption ?? "in the last 30 days"}
          </p>
        )}
      </div>
    </div>
  );

  return href ? (
    <Link href={href} style={style} className={cn("block h-full rounded-2xl focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400", className)}>
      {content}
    </Link>
  ) : (
    <div style={style} className={className}>
      {content}
    </div>
  );
}

function Sparkline({ points, color }: { points: number[]; color: string }) {
  const w = 96;
  const h = 34;
  const max = Math.max(...points, 1);
  const step = w / (points.length - 1);
  const coords = points.map((p, i) => [i * step, h - 3 - (p / max) * (h - 6)] as const);
  const line = coords.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${line} L${w},${h} L0,${h} Z`;
  const id = `spark-${color.slice(1)}`;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-[34px] w-[96px] shrink-0" aria-hidden>
      <defs>
        <linearGradient id={id} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.25} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${id})`} className="animate-fade-in" />
      <path d={line} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" pathLength={1} className="spark-draw" />
    </svg>
  );
}
