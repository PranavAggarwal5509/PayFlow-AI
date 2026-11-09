"use client";

import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  ClipboardCheck,
  Clock,
  FileText,
  RefreshCw,
  ShieldCheck,
  Upload,
  UserCheck,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState, type CSSProperties } from "react";

import { ThroughputChart } from "@/components/dashboard/throughput-chart";
import { ExceptionsByControl } from "@/components/dashboard/control-insights";
import { DecisionFlow } from "@/components/dashboard/decision-flow";
import { HeroGauge } from "@/components/dashboard/hero-gauge";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { useAuth } from "@/components/auth/auth-provider";
import { RecentDecisions } from "@/components/dashboard/recent-decisions";
import { Card, CardHeader } from "@/components/ui/card";
import { useAsync } from "@/hooks/use-async";
import { useCountUp } from "@/hooks/use-motion";
import { formatDateTime, formatDuration } from "@/lib/format";
import { STAGE_LABELS } from "@/lib/status";
import { cn } from "@/lib/utils";
import { dashboardService, invoiceService } from "@/services";

const REFRESH_MS = 15000;

/** Which invoices the overview summarises. Live uploads are the demo runs; history is the seed. */
const SOURCES = [
  { key: "ALL", label: "All invoices" },
  { key: "LIVE_UPLOAD", label: "Live uploads" },
  { key: "SEED_HISTORY", label: "Seeded history" },
] as const;
type Source = (typeof SOURCES)[number]["key"];

const REVIEW_ACTION_LABEL: Record<string, string> = {
  REVIEW_APPROVE: "approved",
  REVIEW_REJECT: "rejected",
  REVIEW_REQUEST_CLARIFICATION: "asked for clarification on",
};

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

const delay = (ms: number): CSSProperties => ({ ["--d" as string]: `${ms}ms` });

/** Last `days` days of counts, zero-filled, oldest first. */
function dailySeries(rows: { date: string; count: number }[], days = 14): number[] {
  const byDate = new Map(rows.map((r) => [r.date, r.count]));
  const out: number[] = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    out.push(byDate.get(key) ?? 0);
  }
  return out;
}

export default function DashboardPage() {
  const [source, setSource] = useState<Source>("ALL");
  // Remember the choice in the URL (?source=LIVE_UPLOAD) so it survives refreshes and can be shared.
  useEffect(() => {
    const fromUrl = new URLSearchParams(window.location.search).get("source");
    if (SOURCES.some((s) => s.key === fromUrl)) setSource(fromUrl as Source);
  }, []);
  const chooseSource = (next: Source) => {
    setSource(next);
    const url = new URL(window.location.href);
    if (next === "ALL") url.searchParams.delete("source");
    else url.searchParams.set("source", next);
    window.history.replaceState(null, "", url.toString());
  };
  const sourceLabel = SOURCES.find((s) => s.key === source)?.label ?? "All invoices";
  const listHref = (extra = "") => `/invoices?source_origin=${source}${extra}`;

  const stats = useAsync(() => dashboardService.stats(30, source), [source]);
  const recent = useAsync(
    () => invoiceService.list({ page_size: 6, sort_by: "uploaded_at", sort_dir: "desc", source_origin: source }),
    [source],
  );
  const activity = useAsync(() => dashboardService.activity(30, source), [source]);
  const { user, can } = useAuth();
  const [refreshing, setRefreshing] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());

  const data = stats.data;
  const firstLoad = stats.loading && !data;

  // Quiet auto-refresh so the page reflects runs finishing in another tab.
  useEffect(() => {
    const timer = setInterval(() => {
      if (document.visibilityState !== "visible") return;
      stats.reload();
      recent.reload();
      activity.reload();
    }, REFRESH_MS);
    const clock = setInterval(() => setNow(Date.now()), 1000);
    return () => {
      clearInterval(timer);
      clearInterval(clock);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    if (data) setUpdatedAt(Date.now());
  }, [data]);

  const total = data?.kpis.total.value ?? 0;
  const spark = useMemo(() => dailySeries(data?.daily_volume ?? []), [data?.daily_volume]);
  const inr = (bucket: Record<string, string | number> | undefined) => Number(bucket?.INR ?? 0);
  const reviewActivity = (activity.data ?? []).filter((a) => a.action.startsWith("REVIEW_")).slice(0, 5);
  const firstName = (user?.name ?? "there").split(" ")[0];
  // Time-of-day text is computed after mount: the page is pre-rendered at build time.
  const [clockText, setClockText] = useState<{ greet: string; today: string } | null>(null);
  useEffect(() => {
    setClockText({
      greet: greeting(),
      today: new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" }),
    });
  }, []);
  const pending = useCountUp(data?.pending_reviews ?? 0);

  const handleRefresh = async () => {
    setRefreshing(true);
    await Promise.all([stats.reload(), recent.reload(), activity.reload()]);
    setTimeout(() => setRefreshing(false), 600);
  };

  const ago = updatedAt ? Math.max(0, Math.round((now - updatedAt) / 1000)) : null;

  return (
    <div className="space-y-6">
      {/* ---------- Hero ---------- */}
      <section className="relative isolate flex flex-col gap-6 pb-2 before:absolute before:-bottom-6 before:-top-12 before:left-1/2 before:-z-10 before:w-screen before:-translate-x-1/2 before:bg-[#0b1222] lg:flex-row lg:items-center lg:justify-between lg:before:hidden">
        <div className="reveal max-w-2xl">
          <div className="flex flex-wrap items-center gap-3">
            <p className="min-w-[10ch] text-[11px] font-semibold uppercase tracking-[0.14em] text-indigo-300">{clockText?.today ?? " "}</p>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-400/10 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-300 ring-1 ring-inset ring-emerald-400/25">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-300 opacity-60 motion-reduce:hidden" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-300" />
              </span>
              Live · {ago === null ? "connecting" : ago < 5 ? "just updated" : `updated ${ago}s ago`}
            </span>
            <div role="radiogroup" aria-label="Dataset" className="glass inline-flex rounded-full p-0.5">
              {SOURCES.map((s) => (
                <button
                  key={s.key}
                  type="button"
                  role="radio"
                  aria-checked={source === s.key}
                  onClick={() => chooseSource(s.key)}
                  className={cn(
                    "rounded-full px-3 py-1 text-[11.5px] font-semibold transition-colors",
                    source === s.key ? "bg-white text-navy-900 shadow-sm" : "text-slate-300 hover:text-white",
                  )}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>
          <h1 className="mt-3 text-[32px] font-semibold leading-[1.1] tracking-tight text-white sm:text-[40px]">
            {clockText?.greet ?? "Welcome back"}, {firstName}.
            <span className="block bg-gradient-to-r from-indigo-200 via-white to-emerald-200 bg-clip-text text-transparent">
              Here’s your payables pulse.
            </span>
          </h1>
          <p className="mt-3 text-[15px] text-slate-300">
            {data ? (
              <>
                <span className="tabular font-semibold text-amber-300">{Math.round(pending)}</span> invoice
                {data.pending_reviews === 1 ? "" : "s"} waiting for a reviewer ·{" "}
                <span className="tabular font-semibold text-white">{total}</span>{" "}
                {source === "ALL" ? "invoices processed in total" : source === "LIVE_UPLOAD" ? "live uploads processed" : "seeded history invoices"}
              </>
            ) : (
              "Loading your accounts-payable workload…"
            )}
          </p>
          <div className="mt-6 flex flex-wrap items-center gap-2">
            {can("invoices:upload") && (
            <Link
              href="/upload"
              className="group inline-flex h-11 items-center gap-2 rounded-xl bg-white px-5 text-[14px] font-semibold text-navy-900 shadow-[0_10px_30px_-10px_rgba(255,255,255,0.5)] transition-transform duration-200 hover:-translate-y-0.5"
            >
              <Upload className="h-4 w-4 transition-transform duration-200 group-hover:-translate-y-0.5" /> Process invoice
            </Link>
            )}
            <Link
              href="/review"
              className="glass inline-flex h-11 items-center gap-2 rounded-xl px-4 text-[14px] font-medium text-slate-100 transition-colors hover:bg-white/10"
            >
              <ClipboardCheck className="h-4 w-4" /> Review queue
              {!!data?.pending_reviews && (
                <span className="rounded-full bg-amber-400 px-1.5 text-[11px] font-bold text-navy-950">{data.pending_reviews}</span>
              )}
            </Link>
            <button
              type="button"
              onClick={handleRefresh}
              disabled={refreshing}
              aria-label="Refresh dashboard"
              className="glass inline-flex h-11 w-11 items-center justify-center rounded-xl text-slate-200 transition-colors hover:bg-white/10 disabled:opacity-60"
            >
              <RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} />
            </button>
          </div>
        </div>
        <div className="reveal" style={delay(120)}>
          <HeroGauge
            rate={data?.approval_rate}
            cleared={inr(data?.value_at_risk?.approved)}
            held={inr(data?.value_at_risk?.held)}
            blocked={inr(data?.value_at_risk?.blocked)}
            loading={firstLoad}
          />
        </div>
      </section>

      {stats.error && !data && (
        <div role="alert" className="flex items-center justify-between rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          <span className="flex items-center gap-2">
            <AlertOctagon className="h-4 w-4 text-rose-600" /> Could not load metrics: {stats.error}
          </span>
          <button className="font-semibold underline" onClick={stats.reload}>
            Retry
          </button>
        </div>
      )}

      {/* ---------- KPIs ---------- */}
      <section aria-label="Key metrics" className="grid grid-cols-2 gap-4 lg:grid-cols-4 [&>*]:min-w-0">
        <KpiCard
          className="reveal"
          style={delay(180)}
          label="Invoices processed"
          kpi={data?.kpis.total}
          icon={<FileText className="h-[18px] w-[18px]" />}
          loading={firstLoad}
          href={listHref()}
          caption="in the last 30 days"
          spark={spark}
        />
        <KpiCard
          className="reveal"
          style={delay(240)}
          label="Auto-approved"
          kpi={data?.kpis.approved}
          accent="success"
          icon={<CheckCircle2 className="h-[18px] w-[18px]" />}
          loading={firstLoad}
          total={total}
          href={listHref("&decision_status=APPROVED")}
          caption="cleared with zero touches"
        />
        <KpiCard
          className="reveal"
          style={delay(300)}
          label="Needs review"
          kpi={data?.kpis.needs_review}
          accent="warning"
          icon={<AlertTriangle className="h-[18px] w-[18px]" />}
          loading={firstLoad}
          total={total}
          href="/review"
          caption="routed to a human"
        />
        <KpiCard
          className="reveal"
          style={delay(360)}
          label="Rejected"
          kpi={data?.kpis.rejected}
          accent="danger"
          icon={<XCircle className="h-[18px] w-[18px]" />}
          loading={firstLoad}
          total={total}
          href={listHref("&decision_status=REJECTED")}
          caption="stopped by a hard rule"
        />
      </section>

      {/* ---------- Decision flow (full width) ---------- */}
      <section className="reveal" style={delay(420)}>
          <DecisionFlow
            origin={source}
            scopeLabel={sourceLabel}
            loading={firstLoad}
            counts={
              data
                ? {
                    total,
                    approved: data.kpis.approved.value,
                    review: data.kpis.needs_review.value,
                    rejected: data.kpis.rejected.value,
                    failed: data.kpis.failed.value,
                  }
                : null
            }
            values={
              data
                ? {
                    approved: inr(data.value_at_risk?.approved),
                    review: inr(data.value_at_risk?.held),
                    rejected: inr(data.value_at_risk?.blocked),
                  }
                : null
            }
          />
      </section>

      {/* ---------- Exceptions + throughput + health ---------- */}
      <section className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3 [&>*]:min-w-0">
        <div className="reveal" style={delay(480)}>
          <ExceptionsByControl data={data?.exceptions_by_control} loading={firstLoad} />
        </div>
        <div className="reveal" style={delay(540)}>
          <ThroughputChart data={data?.daily_volume ?? []} />
        </div>
        <div className="reveal lg:col-span-2 xl:col-span-1" style={delay(600)}>
          <PipelineHealth
            loading={firstLoad}
            avg={data?.average_processing_seconds}
            pending={data?.pending_reviews ?? 0}
            failed={data?.kpis.failed.value ?? 0}
            failedRuns={data?.recent_failed_runs ?? []}
          />
        </div>
      </section>

      {/* ---------- Latest decisions + reviewers ---------- */}
      <section className="grid gap-4 xl:grid-cols-3 [&>*]:min-w-0">
        <Card className="reveal overflow-hidden xl:col-span-2" style={delay(660)}>
          <CardHeader
            title="Latest decisions"
            description="Most recent invoices and where they landed"
            action={
              <Link href="/invoices" className="inline-flex items-center gap-1 text-[13px] font-semibold text-indigo-600 hover:text-indigo-700">
                All invoices <ArrowUpRight className="h-3.5 w-3.5" />
              </Link>
            }
          />
          <RecentDecisions items={recent.data?.items ?? []} loading={recent.loading && !recent.data} />
        </Card>

        <Card className="reveal flex flex-col" style={delay(720)}>
          <CardHeader title="Reviewer activity" description="Human decisions, all audited" />
          <div className="flex-1 p-3">
            {reviewActivity.length === 0 ? (
              <div className="flex h-full min-h-[200px] flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 text-center">
                <UserCheck className="h-6 w-6 text-slate-300" />
                <p className="mt-2 text-[13px] font-medium text-slate-600">No reviewer actions yet</p>
                <p className="text-[12px] text-slate-400">Approve or reject from the review queue.</p>
              </div>
            ) : (
              <ol className="relative ml-2 space-y-1 border-l border-slate-100 pl-3">
                {reviewActivity.map((item) => {
                  const tone =
                    item.action === "REVIEW_APPROVE" ? "bg-emerald-500" : item.action === "REVIEW_REJECT" ? "bg-rose-500" : "bg-indigo-500";
                  return (
                    <li key={item.id} className="relative">
                      <span className={cn("absolute -left-[17px] top-4 h-2.5 w-2.5 rounded-full ring-4 ring-white", tone)} />
                      <Link href={`/invoices/${item.invoice_id}`} className="block rounded-lg p-2.5 transition-colors hover:bg-slate-50">
                        <span className="text-[13px]">
                          <span className="font-medium text-slate-900">{item.actor}</span>{" "}
                          <span className="text-slate-500">{REVIEW_ACTION_LABEL[item.action] ?? item.action}</span>{" "}
                          <span className="font-semibold text-slate-900">{item.invoice_number}</span>
                        </span>
                        <span className="mt-0.5 block text-[11.5px] text-slate-400">{formatDateTime(item.created_at)}</span>
                      </Link>
                    </li>
                  );
                })}
              </ol>
            )}
          </div>
        </Card>
      </section>
    </div>
  );
}

function PipelineHealth({
  loading,
  avg,
  pending,
  failed,
  failedRuns,
}: {
  loading: boolean;
  avg: number | null | undefined;
  pending: number;
  failed: number;
  failedRuns: { run_id: string; invoice_number: string; stage: string | null; started_at: string }[];
}) {
  const rows = [
    { icon: Clock, label: "Avg. time to decision", value: formatDuration(avg), tone: "bg-indigo-50 text-indigo-600 ring-indigo-100" },
    { icon: ClipboardCheck, label: "Waiting for a reviewer", value: String(pending), tone: "bg-amber-50 text-amber-600 ring-amber-100", href: "/review" },
    { icon: AlertOctagon, label: "Technical failures", value: String(failed), tone: "bg-slate-100 text-slate-600 ring-slate-200" },
    { icon: ShieldCheck, label: "Controls per invoice", value: "24", tone: "bg-emerald-50 text-emerald-600 ring-emerald-100", href: "/settings" },
  ];
  return (
    <Card className="flex h-full flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="eyebrow">Operations</p>
          <h3 className="mt-1 text-[16px] font-semibold">Pipeline health</h3>
          <p className="mt-0.5 text-[12.5px] text-slate-500">Speed, backlog and failures.</p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-[11.5px] font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> Operational
        </span>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2">
        {rows.map((row) => {
          const inner = (
            <div className="h-full rounded-xl border border-slate-100 p-3 transition-all duration-200 hover:-translate-y-0.5 hover:border-slate-200 hover:shadow-card">
              <span className={cn("flex h-8 w-8 items-center justify-center rounded-lg ring-1 ring-inset", row.tone)}>
                <row.icon className="h-4 w-4" />
              </span>
              <p className="tabular mt-3 text-[22px] font-semibold leading-none text-slate-900">{loading ? "—" : row.value}</p>
              <p className="mt-1 text-[12px] text-slate-500">{row.label}</p>
            </div>
          );
          return row.href ? (
            <Link key={row.label} href={row.href} className="block">
              {inner}
            </Link>
          ) : (
            <div key={row.label}>{inner}</div>
          );
        })}
      </div>
      {failedRuns.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {failedRuns.slice(0, 2).map((run) => (
            <Link
              key={run.run_id}
              href={`/processing/${run.run_id}`}
              className="flex items-center gap-2 rounded-lg bg-rose-50/70 px-2.5 py-1.5 text-[12px] text-rose-800 hover:bg-rose-50"
            >
              <Activity className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">
                {run.invoice_number || "Unreadable document"} halted at {STAGE_LABELS[run.stage ?? ""] ?? run.stage}
              </span>
            </Link>
          ))}
        </div>
      )}
    </Card>
  );
}
