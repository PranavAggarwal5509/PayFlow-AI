"use client";

import { BarChart3 } from "lucide-react";
import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Card } from "@/components/ui/card";
import { usePrefersReducedMotion } from "@/hooks/use-motion";

interface Day {
  key: string;
  label: string;
  count: number;
  today: boolean;
}

function lastDays(rows: { date: string; count: number }[], days: number): Day[] {
  const byDate = new Map(rows.map((r) => [r.date, r.count]));
  const out: Day[] = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    out.push({
      key,
      label: d.toLocaleDateString("en-IN", { day: "numeric", month: "short" }),
      count: byDate.get(key) ?? 0,
      today: i === 0,
    });
  }
  return out;
}

/** 14-day intake as bars that grow in (zero-filled so quiet days are visible, not skipped). */
export function ThroughputChart({ data }: { data: { date: string; count: number }[] }) {
  const reduced = usePrefersReducedMotion();
  const days = useMemo(() => lastDays(data, 14), [data]);
  const total = days.reduce((s, d) => s + d.count, 0);
  const busiest = days.reduce((best, d) => (d.count > best.count ? d : best), days[0]);
  const activeDays = days.filter((d) => d.count > 0).length;

  return (
    <Card className="flex h-full flex-col p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="eyebrow">Throughput</p>
          <h3 className="mt-1 text-[16px] font-semibold text-slate-900">Invoices received, last 14 days</h3>
          <p className="mt-0.5 text-[12.5px] text-slate-500">Every upload, whatever the decision.</p>
        </div>
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600 ring-1 ring-inset ring-indigo-100">
          <BarChart3 className="h-[18px] w-[18px]" />
        </span>
      </div>

      <dl className="mt-4 grid grid-cols-3 gap-3">
        {[
          { label: "Received", value: String(total) },
          { label: "Busiest day", value: busiest?.count ? `${busiest.count} · ${busiest.label}` : "—" },
          { label: "Active days", value: `${activeDays} / 14` },
        ].map((s) => (
          <div key={s.label} className="rounded-lg bg-slate-50 px-3 py-2">
            <dt className="text-[11px] font-medium text-slate-500">{s.label}</dt>
            <dd className="tabular mt-0.5 text-[15px] font-semibold text-slate-900">{s.value}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-4 h-[200px] flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={days} margin={{ top: 8, right: 4, left: -24, bottom: 0 }} barCategoryGap="22%">
            <defs>
              <linearGradient id="tp-bar" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#6366f1" />
                <stop offset="100%" stopColor="#a5b4fc" />
              </linearGradient>
              <linearGradient id="tp-today" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#10b981" />
                <stop offset="100%" stopColor="#6ee7b7" />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke="#f1f5f9" />
            <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "#94a3b8" }} interval={1} />
            <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "#94a3b8" }} />
            <Tooltip
              cursor={{ fill: "rgba(99,102,241,0.06)", radius: 6 }}
              contentStyle={{ borderRadius: 10, border: "1px solid #e2e8f0", fontSize: 12, boxShadow: "0 8px 24px -8px rgba(15,23,42,0.18)" }}
              formatter={(value: number) => [`${value} invoice${value === 1 ? "" : "s"}`, "Received"]}
            />
            <Bar
              dataKey="count"
              radius={[6, 6, 2, 2]}
              isAnimationActive={!reduced}
              animationDuration={900}
              animationEasing="ease-out"
              minPointSize={2}
            >
              {days.map((d) => (
                <Cell key={d.key} fill={d.count === 0 ? "#e2e8f0" : d.today ? "url(#tp-today)" : "url(#tp-bar)"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 flex items-center gap-3 text-[11.5px] text-slate-500">
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-sm bg-emerald-500" /> Today
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-sm bg-indigo-500" /> Earlier
        </span>
      </p>
    </Card>
  );
}
