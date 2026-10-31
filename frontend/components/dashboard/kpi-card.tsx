import Link from "next/link";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { Kpi } from "@/types/api";

const ACCENTS = {
  neutral: {
    bar: "bg-slate-400",
    badge: "bg-slate-100 text-slate-700",
    iconBg: "bg-slate-100 text-slate-600",
  },
  success: {
    bar: "bg-emerald-500",
    badge: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
    iconBg: "bg-emerald-50 text-emerald-600",
  },
  warning: {
    bar: "bg-amber-500",
    badge: "bg-amber-50 text-amber-700 ring-1 ring-amber-200",
    iconBg: "bg-amber-50 text-amber-600",
  },
  danger: {
    bar: "bg-rose-500",
    badge: "bg-rose-50 text-rose-700 ring-1 ring-rose-200",
    iconBg: "bg-rose-50 text-rose-600",
  },
} as const;

export function KpiCard({
  label,
  kpi,
  accent = "neutral",
  loading,
  icon,
  href,
  subtitle,
}: {
  label: string;
  kpi?: Kpi;
  accent?: keyof typeof ACCENTS;
  loading?: boolean;
  icon?: ReactNode;
  href?: string;
  subtitle?: string;
}) {
  const change = kpi?.change_percent;
  const config = ACCENTS[accent];

  const content = (
    <Card className="relative overflow-hidden p-5 border-slate-200/90 shadow-card transition-all duration-150 hover:shadow-pop/30 hover:border-slate-300 group cursor-pointer">
      {/* Accent top/left highlight */}
      <span className={cn("absolute inset-y-0 left-0 w-1 rounded-l-lg", config.bar)} />

      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {label}
          </p>
          {loading || !kpi ? (
            <Skeleton className="mt-2.5 h-8 w-24" />
          ) : (
            <p className="tabular mt-1.5 text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
              {kpi.value.toLocaleString()}
            </p>
          )}
        </div>

        {icon && (
          <div
            className={cn(
              "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-transform group-hover:scale-105",
              config.iconBg,
            )}
          >
            {icon}
          </div>
        )}
      </div>

      <div className="mt-3 flex items-center justify-between text-[11px] pt-2 border-t border-slate-100/80">
        <div className="flex items-center gap-1.5">
          {kpi && change !== null && change !== undefined ? (
            <span
              className={cn(
                "inline-flex items-center gap-0.5 rounded px-1 py-0.5 font-medium",
                change > 0
                  ? "bg-emerald-50 text-emerald-700 font-semibold"
                  : change < 0
                  ? "bg-rose-50 text-rose-700 font-semibold"
                  : "bg-slate-100 text-slate-600",
              )}
            >
              {change > 0 ? (
                <ArrowUpRight className="h-3 w-3" />
              ) : change < 0 ? (
                <ArrowDownRight className="h-3 w-3" />
              ) : (
                <Minus className="h-3 w-3" />
              )}
              {Math.abs(change)}%
            </span>
          ) : (
            <span className="text-muted-foreground">Last 30d: {kpi?.last_30_days ?? 0}</span>
          )}
          <span className="text-muted-foreground">{subtitle || "vs prev period"}</span>
        </div>
      </div>
    </Card>
  );

  return href ? (
    <Link href={href} className="block focus:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-lg">
      {content}
    </Link>
  ) : (
    content
  );
}
