"use client";

import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { EmptyState } from "@/components/tables/table-states";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { formatMonth } from "@/lib/format";
import type { DashboardStats } from "@/types/api";

const COLORS: Record<string, string> = {
  APPROVED: "#10b981", // Emerald 500
  NEEDS_REVIEW: "#f59e0b", // Amber 500
  REJECTED: "#ef4444", // Rose 500
  PROCESSING_FAILED: "#64748b", // Slate 500
  PROCESSING: "#3b82f6", // Blue 500
};

const LABELS: Record<string, string> = {
  APPROVED: "Approved",
  NEEDS_REVIEW: "Needs review",
  REJECTED: "Rejected",
  PROCESSING_FAILED: "Technical failure",
  PROCESSING: "In processing",
};

const axisStyle = {
  fontSize: 11,
  fill: "#64748b",
  fontWeight: 500,
};

const tooltipStyle = {
  borderRadius: 8,
  border: "1px solid #e2e8f0",
  fontSize: 12,
  boxShadow: "0 4px 12px rgba(15,23,42,0.08)",
  backgroundColor: "#ffffff",
  padding: "8px 12px",
};

export function VolumeChart({ data }: { data: DashboardStats["daily_volume"] }) {
  const totalVolume = data.reduce((acc, d) => acc + d.count, 0);

  return (
    <Card className="border-slate-200/90 shadow-card">
      <CardHeader
        title="Processing Volume"
        description={`Daily invoice ingestion throughput · ${totalVolume} total documents in the last 30 days`}
      />
      <CardBody className="h-72 pt-2">
        {data.length === 0 ? (
          <EmptyState title="No uploads recorded in the last 30 days" />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ left: -18, right: 12, top: 10, bottom: 0 }}>
              <defs>
                <linearGradient id="volGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#2563eb" stopOpacity={0.22} />
                  <stop offset="95%" stopColor="#2563eb" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis
                dataKey="date"
                tick={axisStyle}
                tickFormatter={(v: string) => {
                  const parts = v.split("-");
                  return `${parts[1]}/${parts[2]}`;
                }}
                tickLine={false}
                axisLine={{ stroke: "#e2e8f0" }}
                dy={6}
              />
              <YAxis
                allowDecimals={false}
                tick={axisStyle}
                tickLine={false}
                axisLine={false}
                dx={-4}
              />
              <Tooltip
                contentStyle={tooltipStyle}
                labelFormatter={(v) => `Date: ${v}`}
                formatter={(val) => [`${val} invoices`, "Volume"]}
              />
              <Area
                type="monotone"
                dataKey="count"
                name="Invoices"
                stroke="#2563eb"
                strokeWidth={2.5}
                fill="url(#volGrad)"
                activeDot={{ r: 5, strokeWidth: 2, stroke: "#ffffff" }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardBody>
    </Card>
  );
}

export function DecisionChart({ data }: { data: DashboardStats["decision_distribution"] }) {
  const total = data.reduce((sum, item) => sum + item.count, 0);

  return (
    <Card className="border-slate-200/90 shadow-card">
      <CardHeader
        title="Decision Distribution"
        description="Outcomes assigned by deterministic rules"
      />
      <CardBody className="h-72 pt-0 flex flex-col justify-center">
        {total === 0 ? (
          <EmptyState title="No decision metrics recorded" />
        ) : (
          <div className="flex h-full items-center gap-4">
            <div className="relative h-full w-1/2">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={data}
                    dataKey="count"
                    nameKey="status"
                    innerRadius="65%"
                    outerRadius="90%"
                    paddingAngle={3}
                    stroke="none"
                  >
                    {data.map((entry) => (
                      <Cell key={entry.status} fill={COLORS[entry.status] ?? "#94a3b8"} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={tooltipStyle}
                    formatter={(v, n) => [v, LABELS[String(n)] ?? n]}
                  />
                </PieChart>
              </ResponsiveContainer>

              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                <span className="tabular text-3xl font-bold tracking-tight text-slate-900">
                  {total}
                </span>
                <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  Invoices
                </span>
              </div>
            </div>

            <ul className="flex-1 space-y-2.5 text-xs pr-2">
              {data.map((entry) => {
                const pct = total > 0 ? Math.round((entry.count / total) * 100) : 0;
                return (
                  <li key={entry.status} className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-2 truncate">
                      <span
                        className="h-2.5 w-2.5 shrink-0 rounded-full"
                        style={{ background: COLORS[entry.status] ?? "#94a3b8" }}
                      />
                      <span className="text-slate-700 font-medium truncate">
                        {LABELS[entry.status] ?? entry.status}
                      </span>
                    </span>
                    <span className="tabular font-semibold text-slate-900 flex items-center gap-1.5">
                      <span>{entry.count}</span>
                      <span className="text-[10px] text-muted-foreground font-normal">
                        ({pct}%)
                      </span>
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

export function MonthlyValueChart({ data }: { data: DashboardStats["monthly_volume"] }) {
  const rows = useMemo(() => data.map((m) => ({ ...m, value: Number(m.value) })), [data]);
  const totalVal = rows.reduce((acc, r) => acc + r.value, 0);

  return (
    <Card className="border-slate-200/90 shadow-card">
      <CardHeader
        title="Monthly Value Progression"
        description="Historical extracted invoice value aggregated by billing month (INR)"
      />
      <CardBody className="h-72 pt-2">
        {rows.length === 0 ? (
          <EmptyState title="No historical value data recorded" />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} margin={{ left: -10, right: 12, top: 10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis
                dataKey="month"
                tick={axisStyle}
                tickFormatter={formatMonth}
                tickLine={false}
                axisLine={{ stroke: "#e2e8f0" }}
                dy={6}
              />
              <YAxis
                tick={axisStyle}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: number) =>
                  v >= 10000000
                    ? `₹${(v / 10000000).toFixed(1)}Cr`
                    : v >= 100000
                    ? `₹${(v / 100000).toFixed(1)}L`
                    : `₹${(v / 1000).toFixed(0)}k`
                }
                dx={-4}
              />
              <Tooltip
                contentStyle={tooltipStyle}
                labelFormatter={(v) => `Billing Month: ${formatMonth(String(v))}`}
                formatter={(v) => [`₹${Number(v).toLocaleString("en-IN")}`, "Extracted Value"]}
              />
              <Bar
                dataKey="value"
                fill="#2563eb"
                radius={[4, 4, 0, 0]}
                maxBarSize={40}
                className="hover:opacity-90 transition-opacity"
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardBody>
    </Card>
  );
}
