"use client";

import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  ChevronRight,
  GitBranch,
  Inbox,
  Lightbulb,
  ScanText,
  ShieldCheck,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useId, useState, type CSSProperties } from "react";

import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useCountUp, usePrefersReducedMotion } from "@/hooks/use-motion";
import { formatMoney } from "@/lib/format";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ data model */

export interface FlowCounts {
  total: number;
  approved: number;
  review: number;
  rejected: number;
  failed: number;
}

export interface FlowValues {
  approved: number;
  review: number;
  rejected: number;
}

type OutcomeKey = "approved" | "review" | "rejected" | "failed";
type Metric = "count" | "value";

interface OutcomeMeta {
  key: OutcomeKey;
  label: string;
  verb: string;
  color: string;
  soft: string;
  ring: string;
  text: string;
  icon: LucideIcon;
  href: string;
}

const OUTCOMES: OutcomeMeta[] = [
  { key: "approved", label: "Auto-approved", verb: "cleared touchless", color: "#10b981", soft: "bg-emerald-50", ring: "ring-emerald-200", text: "text-emerald-700", icon: CheckCircle2, href: "/invoices?source_origin=LIVE_UPLOAD&decision_status=APPROVED" },
  { key: "review", label: "Needs review", verb: "sent to a reviewer", color: "#f59e0b", soft: "bg-amber-50", ring: "ring-amber-200", text: "text-amber-800", icon: AlertTriangle, href: "/review" },
  { key: "rejected", label: "Rejected", verb: "stopped by a hard rule", color: "#f43f5e", soft: "bg-rose-50", ring: "ring-rose-200", text: "text-rose-700", icon: XCircle, href: "/invoices?source_origin=LIVE_UPLOAD&decision_status=REJECTED" },
  { key: "failed", label: "Technical failure", verb: "could not be read", color: "#94a3b8", soft: "bg-slate-100", ring: "ring-slate-200", text: "text-slate-600", icon: Ban, href: "/invoices?source_origin=LIVE_UPLOAD&processing_status=FAILED" },
];

const INDIGO = "#6366f1";

/** ₹ in lakh / crore for compact figures: 1052000 → "₹10.5L". */
export function compactInr(n: number): string {
  if (n >= 1e7) return `₹${(n / 1e7).toFixed(n >= 1e8 ? 0 : 1)}Cr`;
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(n >= 1e6 ? 1 : 2)}L`;
  if (n >= 1e3) return `₹${(n / 1e3).toFixed(0)}K`;
  return `₹${Math.round(n)}`;
}

/* ------------------------------------------------------------------ metro-map geometry */

const W = 1120;
const H = 292;
const RAIL_Y = 134;
const ST = { received: 40, extraction: 270, controls: 500, junction: 640 };
const END_X = 800;
const CARD = { x: 814, w: 296, h: 58 };
const LANE_Y: Record<OutcomeKey, number> = { approved: 40, review: 108, rejected: 180, failed: 252 };
const PARTICLE_DUR = 5.6; // seconds from intake to outcome

/** The branch each outcome takes after it leaves the shared rail. */
const branch = (key: OutcomeKey): string => {
  const y = LANE_Y[key];
  if (key === "failed") return `M${ST.extraction},${RAIL_Y} C${ST.extraction + 52},${RAIL_Y} ${ST.extraction + 48},${y} ${ST.extraction + 100},${y} H${END_X}`;
  return `M${ST.junction},${RAIL_Y} C${ST.junction + 62},${RAIL_Y} ${ST.junction + 58},${y} ${ST.junction + 120},${y} H${END_X}`;
};
/** The whole journey of one invoice: shared rail, then its branch. */
const journey = (key: OutcomeKey): string => {
  const split = key === "failed" ? ST.extraction : ST.junction;
  return `M${ST.received},${RAIL_Y} H${split} ${branch(key).replace(/^M[^C]+/, "")}`;
};

/* ------------------------------------------------------------------ component */

/**
 * Decision flow as a metro map: each glowing dot is an invoice travelling
 * intake → extraction → 24 controls → decision and peeling off onto its outcome line.
 * Dot density follows the outcome mix; outcomes are identified by icon + text (never colour alone),
 * lines highlight on hover/focus, cards drill down, and reduced motion gets a static map.
 */
export function DecisionFlow({
  counts,
  values,
  loading,
}: {
  counts: FlowCounts | null;
  values?: FlowValues | null;
  loading: boolean;
}) {
  const reduced = usePrefersReducedMotion();
  const uid = useId().replace(/:/g, "");
  const [metric, setMetric] = useState<Metric>("count");
  const [active, setActive] = useState<OutcomeKey | null>(null);

  const c = counts ?? { total: 0, approved: 0, review: 0, rejected: 0, failed: 0 };
  const money = { approved: values?.approved ?? 0, review: values?.review ?? 0, rejected: values?.rejected ?? 0 };
  const hasValue = money.approved + money.review + money.rejected > 0;
  const effectiveMetric: Metric = metric === "value" && hasValue ? "value" : "count";

  const metricValues: Record<OutcomeKey, number> =
    effectiveMetric === "count"
      ? { approved: c.approved, review: c.review, rejected: c.rejected, failed: c.failed }
      : { approved: money.approved, review: money.review, rejected: money.rejected, failed: 0 };

  const totalCount = Math.max(c.total, c.approved + c.review + c.rejected + c.failed);
  const readCount = c.approved + c.review + c.rejected;
  const totalMetric = OUTCOMES.reduce((s, o) => s + metricValues[o.key], 0);
  const share = (key: OutcomeKey) => (totalMetric ? Math.round((metricValues[key] / totalMetric) * 100) : 0);
  const pct = (n: number, of: number) => (of ? Math.round((n / of) * 100) : 0);

  if (loading && !counts) {
    return (
      <Card className="p-6">
        <Skeleton className="h-6 w-56" />
        <Skeleton className="mt-6 h-[300px] w-full" />
      </Card>
    );
  }

  if (totalCount === 0) {
    return (
      <Card className="p-6">
        <Header metric={effectiveMetric} onMetric={setMetric} canValue={false} />
        <div className="mt-6 flex h-[240px] flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 text-center">
          <GitBranch className="h-7 w-7 text-slate-300" />
          <p className="mt-2 text-[14px] font-medium text-slate-700">No invoices processed yet</p>
          <p className="text-[12.5px] text-slate-500">Run a scenario and watch the map light up.</p>
          <Link href="/upload" className="mt-3 text-[13px] font-semibold text-indigo-600 hover:text-indigo-700">
            Process an invoice →
          </Link>
        </div>
      </Card>
    );
  }

  // Particles: density proportional to the outcome mix, evenly phased so the stream never bunches.
  const particles = OUTCOMES.flatMap((o, oi) => {
    const v = metricValues[o.key];
    if (!v || !totalMetric) return [];
    const n = Math.max(1, Math.round((v / totalMetric) * 12));
    return Array.from({ length: n }, (_, k) => ({
      id: `${o.key}-${k}`,
      key: o.key,
      color: o.color,
      begin: -(((k + oi * 0.31) / n) % 1) * PARTICLE_DUR,
    }));
  });

  const exceptions = OUTCOMES.filter((o) => o.key !== "approved").sort((a, b) => c[b.key] - c[a.key]);
  const worst = exceptions[0];
  const touchless = pct(c.approved, totalCount);
  const readRate = pct(readCount, totalCount);
  const dim = (key: OutcomeKey) => !!active && active !== key;

  const stations = [
    { x: ST.received, icon: Inbox, eyebrow: "Intake", value: totalCount, caption: "received" },
    { x: ST.extraction, icon: ScanText, eyebrow: "Extraction", value: readCount, caption: "read & verified" },
    { x: ST.controls, icon: ShieldCheck, eyebrow: "24 controls", value: readCount, caption: "checked" },
  ];

  return (
    <Card className="overflow-hidden p-6">
      <Header metric={effectiveMetric} onMetric={setMetric} canValue={hasValue} />

      {/* ---------- Desktop / tablet: metro map ---------- */}
      <div className="mt-4 hidden md:block">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="h-auto w-full"
          role="img"
          aria-label={`Decision flow. ${totalCount} invoices received; ${readCount} read and verified; ${c.approved} auto-approved, ${c.review} need review, ${c.rejected} rejected, ${c.failed} technical failures.`}
        >
          <defs>
            <linearGradient id={`${uid}-rail`} x1="0" x2="1" y1="0" y2="0">
              <stop offset="0%" stopColor="#4f46e5" />
              <stop offset="100%" stopColor="#8b5cf6" />
            </linearGradient>
            <filter id={`${uid}-glow`} x="-200%" y="-200%" width="500%" height="500%">
              <feGaussianBlur stdDeviation="3" result="b" />
              <feMerge>
                <feMergeNode in="b" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <pattern id={`${uid}-dots`} width="22" height="22" patternUnits="userSpaceOnUse">
              <circle cx="1.5" cy="1.5" r="1.1" fill="#e2e8f0" />
            </pattern>
          </defs>

          {/* Blueprint dot grid behind the map */}
          <rect x="0" y="0" width={END_X + 4} height={H} fill={`url(#${uid}-dots)`} opacity={0.8} />

          {/* Branch lines: a soft track underneath, the coloured line on top */}
          {OUTCOMES.map((o, i) => {
            const live = c[o.key] > 0;
            return (
              <g key={o.key} opacity={dim(o.key) ? 0.18 : 1} style={{ transition: "opacity 200ms ease" }}>
                <path d={branch(o.key)} fill="none" stroke={live ? o.color : "#cbd5e1"} strokeOpacity={0.14} strokeWidth={12} strokeLinecap="round" />
                <path
                  d={branch(o.key)}
                  pathLength={1}
                  fill="none"
                  stroke={live ? o.color : "#cbd5e1"}
                  strokeWidth={active === o.key ? 4.5 : 3}
                  strokeLinecap="round"
                  strokeDasharray={live ? undefined : "0.012 0.012"}
                  className={live ? "rail-draw" : undefined}
                  style={{ animationDelay: `${0.75 + i * 0.12}s`, transition: "stroke-width 200ms ease" } as CSSProperties}
                />
              </g>
            );
          })}

          {/* Shared trunk */}
          <path d={`M${ST.received},${RAIL_Y} H${ST.junction}`} stroke="#6366f1" strokeOpacity={0.14} strokeWidth={14} strokeLinecap="round" />
          <path
            d={`M${ST.received},${RAIL_Y} H${ST.junction}`}
            pathLength={1}
            stroke={`url(#${uid}-rail)`}
            strokeWidth={5}
            strokeLinecap="round"
            className="rail-draw"
            style={{ animationDelay: "0.1s" }}
          />

          {/* Invoices in motion */}
          {!reduced && (
            <g style={{ animation: "fade-in 0.6s ease-out 1.1s both" }}>
              {particles.map((p) => (
                <circle key={p.id} r={4.6} fill={p.color} stroke="white" strokeWidth={1.5} filter={`url(#${uid}-glow)`} opacity={dim(p.key) ? 0.12 : 1}>
                  <animateMotion dur={`${PARTICLE_DUR}s`} begin={`${p.begin.toFixed(2)}s`} repeatCount="indefinite" path={journey(p.key)} />
                </circle>
              ))}
            </g>
          )}

          {/* Stations */}
          {stations.map((s, i) => (
            <Station key={s.eyebrow} {...s} delay={0.15 + i * 0.18} />
          ))}

          {/* Decision junction */}
          <g className="svg-pop" style={{ animationDelay: "0.7s" }}>
            <rect x={ST.junction - 10} y={RAIL_Y - 10} width={20} height={20} rx={4} transform={`rotate(45 ${ST.junction} ${RAIL_Y})`} fill="#4f46e5" stroke="white" strokeWidth={3} />
          </g>

          {/* Segment chips under the trunk */}
          <Chip x={(ST.received + ST.extraction) / 2} label={`${readRate}% read cleanly`} />
          <Chip x={(ST.extraction + ST.controls) / 2 + 30} label="every rule, every invoice" />
          <Chip x={(ST.controls + ST.junction) / 2 + 4} label={`${touchless}% touchless`} tone="emerald" />

          {/* Terminals + outcome cards */}
          {OUTCOMES.map((o, i) => {
            const y = LANE_Y[o.key];
            const live = c[o.key] > 0;
            return (
              <g key={o.key} opacity={dim(o.key) ? 0.35 : 1} style={{ transition: "opacity 200ms ease" }}>
                {live && !reduced && <circle cx={END_X} cy={y} r={6} fill={o.color} className="svg-ping" style={{ animationDelay: `${i * 0.6}s` }} />}
                <circle cx={END_X} cy={y} r={6.5} fill={live ? o.color : "white"} stroke={live ? "white" : "#cbd5e1"} strokeWidth={2.5} />
                <foreignObject x={CARD.x} y={y - CARD.h / 2} width={CARD.w} height={CARD.h}>
                  <OutcomeCard
                    meta={o}
                    count={c[o.key]}
                    sharePct={share(o.key)}
                    metric={effectiveMetric}
                    money={o.key === "failed" ? null : money[o.key as keyof FlowValues]}
                    active={active === o.key}
                    dimmed={false}
                    onActive={(on) => setActive(on ? o.key : null)}
                  />
                </foreignObject>
              </g>
            );
          })}
        </svg>
      </div>

      {/* ---------- Outcome mix bar (all sizes) ---------- */}
      <div className="mt-4">
        <div className="flex h-2.5 gap-0.5 overflow-hidden rounded-full bg-slate-100">
          {OUTCOMES.map((o) =>
            metricValues[o.key] > 0 ? (
              <div
                key={o.key}
                title={`${o.label}: ${share(o.key)}%`}
                className="h-full transition-all duration-700 ease-out first:rounded-l-full last:rounded-r-full"
                style={{ width: `${share(o.key)}%`, background: o.color, opacity: dim(o.key) ? 0.3 : 1 }}
              />
            ) : null,
          )}
        </div>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-slate-500">
          {OUTCOMES.map((o) => (
            <span key={o.key} className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full" style={{ background: o.color }} />
              {o.label} <span className="tabular font-semibold text-slate-800">{share(o.key)}%</span>
            </span>
          ))}
          <span className="ml-auto hidden text-slate-400 md:inline">{effectiveMetric === "value" ? "Share of ₹ value" : "Share of invoices"}</span>
        </div>
      </div>

      {/* ---------- Mobile: outcome list ---------- */}
      <ul className="mt-4 space-y-2 md:hidden">
        {OUTCOMES.map((o) => (
          <li key={o.key} className="h-[58px]">
            <OutcomeCard
              meta={o}
              count={c[o.key]}
              sharePct={share(o.key)}
              metric={effectiveMetric}
              money={o.key === "failed" ? null : money[o.key as keyof FlowValues]}
              active={false}
              dimmed={false}
              onActive={() => undefined}
            />
          </li>
        ))}
      </ul>

      {/* ---------- Insight ---------- */}
      <div className="mt-5 flex items-start gap-3 rounded-xl bg-gradient-to-r from-indigo-50 via-white to-white px-4 py-3 ring-1 ring-inset ring-indigo-100">
        <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-indigo-600 text-white">
          <Lightbulb className="h-4 w-4" />
        </span>
        <p className="text-[13px] leading-relaxed text-slate-600">
          <span className="font-semibold text-slate-900">{touchless}% cleared with zero human touches.</span>{" "}
          {worst && c[worst.key] > 0 ? (
            <>
              Biggest exception:{" "}
              <Link href={worst.href} className={cn("font-semibold underline-offset-2 hover:underline", worst.text)}>
                {c[worst.key]} {worst.verb}
              </Link>{" "}
              ({pct(c[worst.key], totalCount)}% of intake
              {worst.key !== "failed" && money[worst.key as keyof FlowValues] > 0
                ? `, ${formatMoney(money[worst.key as keyof FlowValues], "INR")} ${worst.key === "review" ? "on hold" : "blocked"}`
                : ""}
              ).
            </>
          ) : (
            "No exceptions in this period."
          )}
        </p>
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ pieces */

function Header({ metric, onMetric, canValue }: { metric: Metric; onMetric: (m: Metric) => void; canValue: boolean }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <p className="eyebrow">Decision flow</p>
        <h3 className="mt-1 text-[16px] font-semibold text-slate-900">Where every invoice ended up</h3>
        <p className="mt-0.5 text-[12.5px] text-slate-500">
          Each dot is an invoice riding the line from intake to its decision. Hover an outcome to trace its route.
        </p>
      </div>
      <div className="flex items-center gap-2">
        <div className="flex rounded-lg bg-slate-100 p-0.5" role="tablist" aria-label="Measure">
          {(
            [
              ["count", "Invoices"],
              ["value", "₹ Value"],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={metric === key}
              disabled={key === "value" && !canValue}
              onClick={() => onMetric(key)}
              className={cn(
                "rounded-md px-3 py-1 text-[12.5px] font-medium transition-all disabled:cursor-not-allowed disabled:opacity-40",
                metric === key ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800",
              )}
            >
              {label}
            </button>
          ))}
        </div>
        <span className="hidden items-center gap-1.5 rounded-full bg-indigo-50 px-2.5 py-1 text-[11.5px] font-semibold text-indigo-700 ring-1 ring-inset ring-indigo-100 sm:inline-flex">
          <GitBranch className="h-3.5 w-3.5" /> Last 30 days
        </span>
      </div>
    </div>
  );
}

function Station({
  x,
  icon: Icon,
  eyebrow,
  value,
  caption,
  delay,
}: {
  x: number;
  icon: LucideIcon;
  eyebrow: string;
  value: number;
  caption: string;
  delay: number;
}) {
  const shown = useCountUp(value);
  return (
    <g>
      <g transform={`translate(${x - 20},0)`}>
        <text y={62} fontSize="10.5" fontWeight={700} letterSpacing="0.12em" fill="#94a3b8">
          {eyebrow.toUpperCase()}
        </text>
        <text y={92} fontSize="24" fontWeight={700} fill="#0f172a">
          {Math.round(shown)}
          <tspan dx="6" fontSize="12.5" fontWeight={500} fill="#64748b">
            {caption}
          </tspan>
        </text>
      </g>
      <g className="svg-pop" style={{ animationDelay: `${delay}s` }}>
        <circle cx={x} cy={RAIL_Y} r={20} fill="white" stroke={INDIGO} strokeWidth={3} />
        <Icon x={x - 9} y={RAIL_Y - 9} width={18} height={18} color="#4f46e5" strokeWidth={2.2} />
      </g>
    </g>
  );
}

function Chip({ x, label, tone = "indigo" }: { x: number; label: string; tone?: "indigo" | "emerald" }) {
  const w = label.length * 6.3 + 20;
  const palette = tone === "emerald" ? { bg: "#ecfdf5", stroke: "#a7f3d0", text: "#047857" } : { bg: "#f5f3ff", stroke: "#ddd6fe", text: "#5b21b6" };
  return (
    <g transform={`translate(${x - w / 2},${RAIL_Y + 30})`}>
      <rect width={w} height={22} rx={11} fill={palette.bg} stroke={palette.stroke} />
      <text x={w / 2} y={15} fontSize="11.5" fontWeight={600} fill={palette.text} textAnchor="middle">
        {label}
      </text>
    </g>
  );
}

function OutcomeCard({
  meta,
  count,
  sharePct,
  metric,
  money,
  active,
  dimmed,
  onActive,
}: {
  meta: OutcomeMeta;
  count: number;
  sharePct: number;
  metric: Metric;
  money: number | null;
  active: boolean;
  dimmed: boolean;
  onActive: (on: boolean) => void;
}) {
  const shown = useCountUp(count);
  const Icon = meta.icon;
  const empty = count === 0;
  const main = metric === "value" ? (money ? compactInr(money) : "—") : String(Math.round(shown));
  const sub =
    metric === "value"
      ? `${count} invoice${count === 1 ? "" : "s"} · ${sharePct}%`
      : `${sharePct}%${money ? ` · ${formatMoney(money, "INR")}` : ""}`;
  return (
    <Link
      href={meta.href}
      onMouseEnter={() => onActive(true)}
      onMouseLeave={() => onActive(false)}
      onFocus={() => onActive(true)}
      onBlur={() => onActive(false)}
      aria-label={`${meta.label}: ${count} invoices, ${sharePct}%${money ? `, ${formatMoney(money, "INR")}` : ""}. Open list.`}
      className={cn(
        "group flex h-full items-center gap-3 rounded-xl border bg-white px-3 transition-all duration-200",
        active ? "border-transparent shadow-lift ring-2 ring-inset " + meta.ring : "border-slate-200 hover:border-slate-300",
        empty && "bg-slate-50/60",
        dimmed && "opacity-45",
      )}
    >
      <span className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ring-1 ring-inset", meta.soft, meta.ring, meta.text, empty && "opacity-60")}>
        <Icon className="h-[18px] w-[18px]" />
      </span>
      <span className="min-w-0 flex-1">
        <span className={cn("block truncate text-[13px] font-semibold", empty ? "text-slate-500" : "text-slate-900")}>{meta.label}</span>
        <span className="block truncate text-[11.5px] text-slate-500">{empty ? "None this period" : sub}</span>
      </span>
      <span className={cn("tabular text-[20px] font-bold", empty ? "text-slate-300" : "text-slate-900")}>{main}</span>
      <ChevronRight className="h-4 w-4 shrink-0 text-slate-300 transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-slate-500" />
    </Link>
  );
}
