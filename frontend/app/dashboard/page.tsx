"use client";

import {
  AlertOctagon,
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  Clock,
  Coins,
  FileText,
  Percent,
  RefreshCw,
  Sparkles,
  Upload,
  UserCheck,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { DecisionChart, MonthlyValueChart, VolumeChart } from "@/components/dashboard/charts";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { RecentInvoicesTable } from "@/components/invoices/invoice-columns";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { useAsync } from "@/hooks/use-async";
import { formatDateTime, formatDuration, formatMoney } from "@/lib/format";
import { STAGE_LABELS } from "@/lib/status";
import { dashboardService, invoiceService } from "@/services";

const REVIEW_ACTION_LABEL: Record<string, string> = {
  REVIEW_APPROVE: "approved",
  REVIEW_REJECT: "rejected",
  REVIEW_REQUEST_CLARIFICATION: "requested clarification on",
};

export default function DashboardPage() {
  const [selectedDays, setSelectedDays] = useState(30);
  const stats = useAsync(() => dashboardService.stats(selectedDays), [selectedDays]);
  const recent = useAsync(() => invoiceService.list({ page_size: 7, sort_by: "uploaded_at", sort_dir: "desc" }), []);
  const activity = useAsync(() => dashboardService.activity(30), []);
  const [refreshing, setRefreshing] = useState(false);

  const data = stats.data;
  const reviewActivity = (activity.data ?? []).filter((a) => a.action.startsWith("REVIEW_")).slice(0, 4);

  const handleRefresh = async () => {
    setRefreshing(true);
    await Promise.all([stats.reload(), recent.reload(), activity.reload()]);
    setRefreshing(false);
  };

  return (
    <div className="space-y-6">
      {/* Top Header Banner */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Operations Command Center</h1>
            <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700 ring-1 ring-inset ring-blue-700/10">
              <Sparkles className="h-3 w-3 text-blue-600" />
              Live Pipeline
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Real-time telemetry, automated 3-way matching, validation checks, and human review queues.
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={refreshing || stats.loading}
            className="border-slate-200 bg-white shadow-xs hover:bg-slate-50"
          >
            <RefreshCw className={`mr-1.5 h-3.5 w-3.5 text-slate-500 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button asChild size="sm" className="bg-blue-600 shadow-sm hover:bg-blue-700">
            <Link href="/upload">
              <Upload className="mr-1.5 h-3.5 w-3.5" />
              Upload Invoice
            </Link>
          </Button>
        </div>
      </div>

      {stats.error && (
        <div role="alert" className="flex items-center justify-between rounded-xl border border-red-200 bg-red-50/80 px-4 py-3 text-sm text-red-800 shadow-xs">
          <div className="flex items-center gap-2">
            <AlertOctagon className="h-4 w-4 shrink-0 text-red-600" />
            <span>Failed to load live telemetry: {stats.error}</span>
          </div>
          <button className="font-semibold underline hover:text-red-900" onClick={stats.reload}>
            Retry
          </button>
        </div>
      )}

      {/* KPI Cards Strip */}
      <section aria-label="Key performance indicators" className="grid grid-cols-2 gap-3.5 sm:grid-cols-3 lg:grid-cols-5">
        <KpiCard
          label="Total Invoices"
          kpi={data?.kpis.total}
          icon={<FileText className="h-4 w-4 text-slate-700" />}
          loading={stats.loading}
          href="/invoices?source_origin=LIVE_UPLOAD"
        />
        <KpiCard
          label="Auto-Approved"
          kpi={data?.kpis.approved}
          accent="success"
          icon={<CheckCircle2 className="h-4 w-4 text-emerald-600" />}
          loading={stats.loading}
          href="/invoices?source_origin=LIVE_UPLOAD&decision_status=APPROVED"
        />
        <KpiCard
          label="Needs Review"
          kpi={data?.kpis.needs_review}
          accent="warning"
          icon={<AlertTriangle className="h-4 w-4 text-amber-600" />}
          loading={stats.loading}
          href="/review"
        />
        <KpiCard
          label="Auto-Rejected"
          kpi={data?.kpis.rejected}
          accent="danger"
          icon={<XCircle className="h-4 w-4 text-rose-600" />}
          loading={stats.loading}
          href="/invoices?source_origin=LIVE_UPLOAD&decision_status=REJECTED"
        />
        <KpiCard
          label="Pipeline Failed"
          kpi={data?.kpis.failed}
          accent="danger"
          icon={<AlertOctagon className="h-4 w-4 text-red-600" />}
          loading={stats.loading}
          href="/invoices?source_origin=LIVE_UPLOAD&processing_status=FAILED"
        />
      </section>

      {/* Invoice Portfolio Breakdown (All 90 Records Reconciled) */}
      {data?.portfolio && (
        <section aria-label="Invoice Portfolio" className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b pb-4">
            <div>
              <h2 className="text-base font-semibold text-slate-900">Invoice Portfolio Reconciled Dataset</h2>
              <p className="text-xs text-muted-foreground">
                Complete multi-source breakdown distinguishing AI-processed live invoices from seeded historical reference data.
              </p>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1 font-semibold text-slate-700">
                <span className="h-2 w-2 rounded-full bg-slate-500" />
                Total Portfolio: {data.portfolio.all.total}
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 font-semibold text-blue-700">
                <span className="h-2 w-2 rounded-full bg-blue-600" />
                Live: {data.portfolio.live.total}
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-purple-50 px-3 py-1 font-semibold text-purple-700">
                <span className="h-2 w-2 rounded-full bg-purple-600" />
                Historical: {data.portfolio.historical.total}
              </span>
            </div>
          </div>

          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            {/* All Invoices Card */}
            <div className="rounded-lg border border-slate-200/80 bg-slate-50/50 p-4">
              <div className="flex items-center justify-between border-b border-slate-200/60 pb-2">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-600">Combined Portfolio</span>
                <Link
                  href="/invoices?source_origin=ALL"
                  className="text-xs font-semibold text-primary hover:underline"
                >
                  View all ({data.portfolio.all.total}) →
                </Link>
              </div>
              <div className="mt-3 space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-slate-500 font-medium">Approved</span>
                  <span className="tabular font-semibold text-emerald-700">{data.portfolio.all.approved}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-500 font-medium">Needs Review</span>
                  <span className="tabular font-semibold text-amber-600">{data.portfolio.all.needs_review}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-500 font-medium">Rejected</span>
                  <span className="tabular font-semibold text-rose-600">{data.portfolio.all.rejected}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-500 font-medium">Technical Failures</span>
                  <span className="tabular font-semibold text-slate-600">{data.portfolio.all.failed}</span>
                </div>
                <div className="mt-2 border-t pt-2 flex items-center justify-between font-semibold text-slate-900">
                  <span>Reconciled Sum</span>
                  <span className="tabular">
                    {data.portfolio.all.approved +
                      data.portfolio.all.needs_review +
                      data.portfolio.all.rejected +
                      data.portfolio.all.failed}{" "}
                    / {data.portfolio.all.total}
                  </span>
                </div>
              </div>
            </div>

            {/* Historical Reference Data Card */}
            <div className="rounded-lg border border-purple-200/70 bg-purple-50/30 p-4">
              <div className="flex items-center justify-between border-b border-purple-200/60 pb-2">
                <span className="text-xs font-bold uppercase tracking-wider text-purple-900">Historical Reference</span>
                <Link
                  href="/invoices?source_origin=SEED_HISTORY"
                  className="text-xs font-semibold text-purple-700 hover:underline"
                >
                  View historical ({data.portfolio.historical.total}) →
                </Link>
              </div>
              <div className="mt-3 space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-purple-700/80 font-medium">Historical Approved</span>
                  <span className="tabular font-semibold text-emerald-700">{data.portfolio.historical.approved}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-purple-700/80 font-medium">Historical Needs Review</span>
                  <span className="tabular font-semibold text-amber-600">{data.portfolio.historical.needs_review}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-purple-700/80 font-medium">Historical Rejected</span>
                  <span className="tabular font-semibold text-rose-600">{data.portfolio.historical.rejected}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-purple-700/80 font-medium">Technical Failures</span>
                  <span className="tabular font-semibold text-slate-600">{data.portfolio.historical.failed}</span>
                </div>
                <div className="mt-2 border-t border-purple-200/60 pt-2 flex items-center justify-between font-semibold text-purple-950">
                  <span>Reconciled Sum</span>
                  <span className="tabular">
                    {data.portfolio.historical.approved +
                      data.portfolio.historical.needs_review +
                      data.portfolio.historical.rejected +
                      data.portfolio.historical.failed}{" "}
                    / {data.portfolio.historical.total}
                  </span>
                </div>
              </div>
            </div>

            {/* Live Operational Invoices Card */}
            <div className="rounded-lg border border-blue-200/70 bg-blue-50/30 p-4">
              <div className="flex items-center justify-between border-b border-blue-200/60 pb-2">
                <span className="text-xs font-bold uppercase tracking-wider text-blue-900">Live AI Processing</span>
                <Link
                  href="/invoices?source_origin=LIVE_UPLOAD"
                  className="text-xs font-semibold text-blue-700 hover:underline"
                >
                  View live ({data.portfolio.live.total}) →
                </Link>
              </div>
              <div className="mt-3 space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-blue-700/80 font-medium">Live Approved</span>
                  <span className="tabular font-semibold text-emerald-700">{data.portfolio.live.approved}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-blue-700/80 font-medium">Live Needs Review</span>
                  <span className="tabular font-semibold text-amber-600">{data.portfolio.live.needs_review}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-blue-700/80 font-medium">Live Rejected</span>
                  <span className="tabular font-semibold text-rose-600">{data.portfolio.live.rejected}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-blue-700/80 font-medium">Technical Failures</span>
                  <span className="tabular font-semibold text-red-600">{data.portfolio.live.failed}</span>
                </div>
                <div className="mt-2 border-t border-blue-200/60 pt-2 flex items-center justify-between font-semibold text-blue-950">
                  <span>Reconciled Sum</span>
                  <span className="tabular">
                    {data.portfolio.live.approved +
                      data.portfolio.live.needs_review +
                      data.portfolio.live.rejected +
                      data.portfolio.live.failed}{" "}
                    / {data.portfolio.live.total}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Primary Analytics Grid: Volume Flow & Decision Distribution */}
      <section className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <VolumeChart data={data?.daily_volume ?? []} />
        </div>
        <div className="lg:col-span-1">
          <DecisionChart
            data={data?.decision_distribution ?? []}
            detailed={data?.decision_distribution_detailed}
          />
        </div>
      </section>

      {/* Secondary Analytics: Value Throughput & Operations Health */}
      <section className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <MonthlyValueChart data={data?.monthly_volume ?? []} />
        </div>

        <Card className="flex flex-col justify-between border-slate-200/80 shadow-xs">
          <div>
            <CardHeader
              title="System Telemetry"
              description="Real-time pipeline health and throughput"
            />
            <CardBody className="space-y-4 pt-1">
              <StatItem
                icon={<Clock className="h-4 w-4 text-blue-600" />}
                iconBg="bg-blue-50"
                label="Avg Processing Time"
                value={formatDuration(data?.average_processing_seconds)}
                subtext="End-to-end ingestion to decision"
              />
              <StatItem
                icon={<Percent className="h-4 w-4 text-emerald-600" />}
                iconBg="bg-emerald-50"
                label="Direct Approval Rate"
                value={data?.approval_rate != null ? `${data.approval_rate}%` : "—"}
                subtext="Invoices passed straight-through"
              />
              <StatItem
                icon={<UserCheck className="h-4 w-4 text-amber-600" />}
                iconBg="bg-amber-50"
                label="Pending Review Queue"
                value={String(data?.pending_reviews ?? "0")}
                subtext="Awaiting manual operator audit"
                href="/review"
              />

              <div className="rounded-xl border border-slate-200/70 bg-slate-50/60 p-3.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
                    <Coins className="h-3.5 w-3.5 text-slate-400" />
                    <span>Processed Currency Totals</span>
                  </div>
                </div>
                <div className="mt-2.5 space-y-1.5">
                  {data && Object.keys(data.total_value_by_currency).length > 0 ? (
                    Object.entries(data.total_value_by_currency).map(([currency, total]) => (
                      <div key={currency} className="tabular flex items-center justify-between text-xs">
                        <span className="font-medium text-slate-500">{currency} Settlement</span>
                        <span className="font-semibold text-slate-900">{formatMoney(total, currency)}</span>
                      </div>
                    ))
                  ) : (
                    <p className="text-xs text-slate-400">No finalized amounts recorded yet</p>
                  )}
                </div>
              </div>
            </CardBody>
          </div>

          <div className="border-t border-slate-100 px-5 py-3 text-xs text-slate-400">
            Deterministic Rule Engine: <span className="font-semibold text-emerald-600">Active</span> · Strict 3-Way Mode
          </div>
        </Card>
      </section>

      {/* Bottom Section: Recent Invoices & Operational Exceptions / Activity */}
      <section className="grid gap-4 lg:grid-cols-3">
        <Card className="border-slate-200/80 shadow-xs lg:col-span-2">
          <CardHeader
            title="Recent Invoices"
            description="Live feed of incoming documents and their current pipeline state"
            action={
              <Button asChild variant="ghost" size="sm" className="text-xs font-semibold text-blue-600 hover:text-blue-700">
                <Link href="/invoices" className="flex items-center gap-1">
                  View full ledger
                  <ArrowUpRight className="h-3.5 w-3.5" />
                </Link>
              </Button>
            }
          />
          <RecentInvoicesTable
            data={recent.data?.items ?? []}
            loading={recent.loading}
            error={recent.error}
            onRetry={recent.reload}
          />
        </Card>

        <div className="space-y-4">
          {/* Failed pipeline runs */}
          <Card className="border-slate-200/80 shadow-xs">
            <CardHeader
              title="Execution Exceptions"
              description="Pipeline crashes or syntax parser failures"
            />
            <CardBody className="space-y-2.5 pt-0">
              {(data?.recent_failed_runs ?? []).length === 0 ? (
                <div className="rounded-lg border border-dashed border-slate-200 p-4 text-center">
                  <CheckCircle2 className="mx-auto h-5 w-5 text-emerald-500" />
                  <p className="mt-1 text-xs font-medium text-slate-600">Zero pipeline crashes</p>
                  <p className="text-[11px] text-slate-400">All extraction services operating cleanly</p>
                </div>
              ) : (
                data?.recent_failed_runs.map((run) => (
                  <Link
                    key={run.run_id}
                    href={`/processing/${run.run_id}`}
                    className="flex items-start gap-2.5 rounded-lg border border-slate-200/70 p-2.5 transition-colors hover:border-slate-300 hover:bg-slate-50"
                  >
                    <div className="rounded bg-rose-50 p-1 text-rose-600">
                      <AlertTriangle className="h-3.5 w-3.5" />
                    </div>
                    <div className="min-w-0 flex-1 text-xs">
                      <div className="flex items-center justify-between">
                        <p className="truncate font-medium text-slate-900">{run.invoice_number || "Unnamed document"}</p>
                        <span className="font-mono text-[10px] text-slate-400">#{run.run_id.slice(0, 6)}</span>
                      </div>
                      <p className="mt-0.5 text-[11px] text-slate-500">
                        Halted at <span className="font-medium text-slate-700">{STAGE_LABELS[run.stage ?? ""] ?? run.stage}</span> · {formatDateTime(run.started_at)}
                      </p>
                    </div>
                  </Link>
                ))
              )}
            </CardBody>
          </Card>

          {/* Audit trail of human reviews */}
          <Card className="border-slate-200/80 shadow-xs">
            <CardHeader
              title="Manual Review Feed"
              description="Audited decisions confirmed by operators"
            />
            <CardBody className="space-y-2 pt-0">
              {reviewActivity.length === 0 ? (
                <div className="rounded-lg border border-dashed border-slate-200 p-4 text-center">
                  <UserCheck className="mx-auto h-5 w-5 text-slate-400" />
                  <p className="mt-1 text-xs font-medium text-slate-600">No manual actions recorded</p>
                  <p className="text-[11px] text-slate-400">All reviews currently up to date</p>
                </div>
              ) : (
                reviewActivity.map((item) => (
                  <Link
                    key={item.id}
                    href={`/invoices/${item.invoice_id}`}
                    className="block rounded-lg border border-slate-200/60 p-2.5 text-xs transition-colors hover:border-slate-300 hover:bg-slate-50"
                  >
                    <div className="flex items-center justify-between text-slate-700">
                      <span className="font-medium text-slate-900">{item.actor}</span>
                      <span className="text-[10px] text-slate-400">{formatDateTime(item.created_at)}</span>
                    </div>
                    <p className="mt-0.5 text-slate-500">
                      {REVIEW_ACTION_LABEL[item.action] ?? item.action}{" "}
                      <span className="font-semibold text-slate-800">{item.invoice_number}</span>
                    </p>
                  </Link>
                ))
              )}
            </CardBody>
          </Card>
        </div>
      </section>
    </div>
  );
}

function StatItem({
  icon,
  iconBg,
  label,
  value,
  subtext,
  href,
}: {
  icon: React.ReactNode;
  iconBg: string;
  label: string;
  value: string;
  subtext?: string;
  href?: string;
}) {
  const content = (
    <div className="group flex items-center justify-between rounded-lg p-1.5 transition-colors hover:bg-slate-50">
      <div className="flex items-center gap-3">
        <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${iconBg} shadow-2xs`}>
          {icon}
        </div>
        <div>
          <p className="text-xs font-medium text-slate-600">{label}</p>
          {subtext && <p className="text-[11px] text-slate-400">{subtext}</p>}
        </div>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="tabular text-base font-semibold text-slate-900">{value}</span>
        {href && <ArrowUpRight className="h-3.5 w-3.5 text-slate-400 group-hover:text-slate-600" />}
      </div>
    </div>
  );

  return href ? <Link href={href} className="block">{content}</Link> : content;
}
