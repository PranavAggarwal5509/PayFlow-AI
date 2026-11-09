"use client";

import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  ClipboardCheck,
  FileText,
  Info,
  RotateCcw,
  ShieldCheck,
  Upload,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { toast } from "sonner";

import { ConfettiBurst } from "@/components/processing/confetti";
import { LivePipeline, PIPELINE, stepState } from "@/components/processing/live-pipeline";
import { ErrorState } from "@/components/tables/table-states";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useRunEvents } from "@/hooks/use-run-events";
import { ApiError } from "@/lib/api";
import { formatDate, formatDuration, formatMoney, parseServerDate } from "@/lib/format";
import { ISSUE_LABELS } from "@/lib/status";
import { cn } from "@/lib/utils";
import { invoiceService } from "@/services";
import type { DecisionReason, RunDetail } from "@/types/api";

function useElapsed(startedAt: string | undefined, completedAt: string | null | undefined, running: boolean) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(timer);
  }, [running]);
  if (!startedAt) return null;
  const end = completedAt ? parseServerDate(completedAt).getTime() : now;
  return Math.max(0, (end - parseServerDate(startedAt).getTime()) / 1000);
}

export default function ProcessingPage() {
  const { runId } = useParams<{ runId: string }>();
  const router = useRouter();
  const { run, error } = useRunEvents(runId);
  const [retrying, setRetrying] = useState(false);
  const running = !!run && (run.status === "QUEUED" || run.status === "RUNNING");
  const [watchedLive, setWatchedLive] = useState(false);
  useEffect(() => {
    if (running) setWatchedLive(true);
  }, [running]);
  const elapsed = useElapsed(run?.started_at, run?.completed_at, running);

  const retry = async () => {
    if (!run) return;
    setRetrying(true);
    try {
      const result = await invoiceService.retry(run.invoice_id);
      toast.success("A new processing run has started.");
      router.push(`/processing/${result.run_id}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not retry.");
    } finally {
      setRetrying(false);
    }
  };

  if (error && !run) return <ErrorState message={error} />;
  if (!run) return <LoadingView />;

  const done = PIPELINE.filter((s) => {
    const state = stepState(run, s.key);
    return state !== "WAITING" && state !== "IN_PROGRESS";
  }).length;
  const progress = run.status === "COMPLETED" ? 100 : Math.round((done / PIPELINE.length) * 100);

  return (
    <div className="space-y-5">
      <RunHeader run={run} elapsed={elapsed} running={running} progress={progress} />

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_400px]">
        <Card className="p-5 sm:p-6">
          <div className="mb-5 flex items-center justify-between gap-3">
            <div>
              <p className="eyebrow">Pipeline</p>
              <h3 className="mt-1 text-[15px] font-semibold">Every stage, as it executes</h3>
            </div>
            <span className="tabular text-[12.5px] text-slate-500">
              {done} / {PIPELINE.length} stages · {run.checks.length} checks
            </span>
          </div>
          <LivePipeline run={run} />
        </Card>

        <div className="space-y-5 xl:sticky xl:top-24 xl:self-start">
          <div className="relative">
            {watchedLive && run.decision?.status === "APPROVED" && <ConfettiBurst />}
            <DecisionPanel run={run} />
          </div>
          <CheckScoreboard run={run} />
          <Card className="p-4">
            <div className="flex flex-wrap gap-2">
              {run.can_retry && (
                <Button onClick={retry} disabled={retrying} className="flex-1">
                  <RotateCcw className="h-4 w-4" /> Retry processing
                </Button>
              )}
              {run.status === "COMPLETED" && (
                <Button asChild className="flex-1">
                  <Link href={`/invoices/${run.invoice_id}`}>
                    <FileText className="h-4 w-4" /> Open invoice
                  </Link>
                </Button>
              )}
              {run.decision?.status === "NEEDS_REVIEW" && (
                <Button asChild variant="outline" className="flex-1">
                  <Link href="/review">
                    <ClipboardCheck className="h-4 w-4" /> Review queue
                  </Link>
                </Button>
              )}
              <Button asChild variant="outline" className="flex-1">
                <Link href="/upload">
                  <Upload className="h-4 w-4" /> Process another
                </Link>
              </Button>
            </div>
          </Card>
          {error && <p className="text-xs text-amber-700">Connection issue: {error}. Reconnecting…</p>}
        </div>
      </div>
    </div>
  );
}

function RunHeader({ run, elapsed, running, progress }: { run: RunDetail; elapsed: number | null; running: boolean; progress: number }) {
  const inv = run.invoice;
  const failed = run.status === "FAILED";
  return (
    <div>
      <div className="pb-6 text-white">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              {running ? (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-indigo-500/20 px-2.5 py-0.5 text-[11.5px] font-semibold text-indigo-200 ring-1 ring-inset ring-indigo-400/30">
                  <span className="relative flex h-1.5 w-1.5">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-indigo-300 opacity-75" />
                    <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-indigo-300" />
                  </span>
                  Live run
                </span>
              ) : (
                <span
                  className={cn(
                    "rounded-full px-2.5 py-0.5 text-[11.5px] font-semibold ring-1 ring-inset",
                    failed ? "bg-rose-500/15 text-rose-200 ring-rose-400/30" : "bg-white/10 text-slate-200 ring-white/15",
                  )}
                >
                  {failed ? "Run failed" : "Run complete"}
                </span>
              )}
              <span className="text-[12px] text-slate-400">Run #{run.run_number}</span>
            </div>
            <h1 className="mt-3 truncate text-[28px] font-semibold leading-tight tracking-tight sm:text-[32px]">
              {run.invoice_number ?? (running ? "Reading invoice…" : "Invoice number not found")}
            </h1>
            <p className="mt-1 truncate text-[13px] text-slate-400">{run.original_file_name}</p>
          </div>
          <div className="glass rounded-xl px-4 py-2.5 text-right">
            <p className="text-[10.5px] font-semibold uppercase tracking-[0.14em] text-indigo-300">Elapsed</p>
            <p className="tabular text-[26px] font-semibold leading-tight">{formatDuration(elapsed)}</p>
          </div>
        </div>
        <div className="mt-5 h-1.5 overflow-hidden rounded-full bg-white/10">
          <div
            className={cn(
              "h-full rounded-full transition-[width] duration-500 ease-out",
              failed ? "bg-rose-400" : "bg-gradient-to-r from-indigo-400 to-emerald-400",
            )}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
      <Card className="overflow-hidden">
      <dl className="grid grid-cols-2 divide-slate-100 sm:grid-cols-3 lg:grid-cols-5 lg:divide-x">
        <Fact label="Vendor" loading={!inv?.vendor_name && running}>
          {inv?.vendor_name ?? "—"}
          {inv?.vendor_name && !inv.vendor_matched && run.status === "COMPLETED" && (
            <span className="ml-1.5 text-[11px] font-medium text-amber-600">unconfirmed</span>
          )}
        </Fact>
        <Fact label="Invoice total" loading={!inv?.total_amount && running}>
          <span className="tabular">{inv?.total_amount ? formatMoney(inv.total_amount, inv.currency) : "—"}</span>
        </Fact>
        <Fact label="Purchase order" loading={!inv?.po_number && running}>
          {inv?.po_number ?? "—"}
        </Fact>
        <Fact label="Invoice date" loading={!inv?.invoice_date && running}>
          {inv?.invoice_date ? formatDate(inv.invoice_date) : "—"}
        </Fact>
        <Fact label="Read via" loading={!inv?.extraction_method && running}>
          {inv?.extraction_method
            ? `${inv.extraction_method === "OCR" ? "OCR (scanned)" : "PDF text"} · ${inv.page_count ?? 1} pg · ${inv.line_item_count} lines`
            : "—"}
        </Fact>
      </dl>
      </Card>
    </div>
  );
}

function Fact({ label, loading, children }: { label: string; loading?: boolean; children: ReactNode }) {
  return (
    <div className="min-w-0 px-5 py-3.5">
      <dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">{label}</dt>
      <dd className="mt-1 truncate text-[13.5px] font-medium text-slate-900">
        {loading ? <Skeleton className="h-4 w-24" /> : children}
      </dd>
    </div>
  );
}

const VERDICT = {
  APPROVED: {
    title: "Approved for payment",
    sub: "Every control passed. PO balance has been reserved.",
    icon: CheckCircle2,
    className: "from-emerald-50 to-white ring-emerald-200",
    iconClass: "bg-emerald-500 text-white",
    titleClass: "text-emerald-900",
  },
  NEEDS_REVIEW: {
    title: "Routed to human review",
    sub: "Nothing is paid until a reviewer resolves the flags below.",
    icon: AlertTriangle,
    className: "from-amber-50 to-white ring-amber-200",
    iconClass: "bg-amber-500 text-white",
    titleClass: "text-amber-900",
  },
  REJECTED: {
    title: "Rejected",
    sub: "A hard-stop rule failed. The invoice cannot be paid as submitted.",
    icon: XCircle,
    className: "from-rose-50 to-white ring-rose-200",
    iconClass: "bg-rose-500 text-white",
    titleClass: "text-rose-900",
  },
} as const;

function DecisionPanel({ run }: { run: RunDetail }) {
  if (run.status === "FAILED") {
    return (
      <Card className="bg-gradient-to-b from-rose-50 to-white p-5 ring-1 ring-inset ring-rose-200">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-rose-500 text-white">
            <Ban className="h-5 w-5" />
          </span>
          <div>
            <p className="eyebrow text-rose-700">Technical failure</p>
            <h3 className="text-[16px] font-semibold text-rose-900">Processing could not finish</h3>
          </div>
        </div>
        <p className="mt-3 text-[13px] text-slate-700">{run.error_message ?? "An error occurred."}</p>
        <p className="mt-3 rounded-lg bg-white/70 p-3 text-[12.5px] text-slate-600 ring-1 ring-inset ring-rose-100">
          This is <strong>not</strong> a rejection. The document could not be processed, so no business decision was
          made. Retrying creates a new run and keeps this one in the audit history.
        </p>
      </Card>
    );
  }

  if (!run.decision) {
    return (
      <Card className="p-5">
        <p className="eyebrow">Decision</p>
        <div className="mt-3 flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-50 text-indigo-600 ring-1 ring-inset ring-indigo-100">
            <ShieldCheck className="h-5 w-5" />
          </span>
          <div>
            <h3 className="text-[15px] font-semibold">Evaluating controls…</h3>
            <p className="text-[12.5px] text-slate-500">{run.checks.length} checks evaluated so far</p>
          </div>
        </div>
        <div className="mt-4 h-2 overflow-hidden rounded-full bg-[linear-gradient(90deg,#eef2ff_0%,#c7d2fe_50%,#eef2ff_100%)] bg-[length:200%_100%] animate-shimmer" />
      </Card>
    );
  }

  const verdict = VERDICT[run.decision.status];
  const blocking = run.decision.reasons.filter((r) => r.severity === "BLOCKING");
  const warnings = run.decision.reasons.filter((r) => r.severity === "WARNING");
  const Icon = verdict.icon;
  return (
    <Card className={cn("animate-fade-up bg-gradient-to-b p-5 ring-1 ring-inset", verdict.className)}>
      <p className="eyebrow">Decision</p>
      <div className="mt-3 flex items-center gap-3">
        <span className={cn("stamp flex h-11 w-11 items-center justify-center rounded-full shadow-sm", verdict.iconClass)}>
          <Icon className="h-6 w-6" />
        </span>
        <div>
          <h3 className={cn("text-[17px] font-semibold", verdict.titleClass)}>{verdict.title}</h3>
          <p className="text-[12.5px] text-slate-600">{verdict.sub}</p>
        </div>
      </div>
      {(blocking.length > 0 || warnings.length > 0) && (
        <ul className="mt-4 space-y-2">
          {[...blocking, ...warnings].map((reason) => (
            <ReasonItem key={`${reason.code}-${reason.message}`} reason={reason} />
          ))}
        </ul>
      )}
      <p className="mt-4 flex items-start gap-1.5 border-t border-slate-200/70 pt-3 text-[11.5px] leading-relaxed text-slate-500">
        <Info className="mt-px h-3.5 w-3.5 shrink-0" />
        Decided by deterministic business rules from the check results above — the AI only extracted the data.
      </p>
    </Card>
  );
}

function ReasonItem({ reason }: { reason: DecisionReason }) {
  const blocking = reason.severity === "BLOCKING";
  return (
    <li className="rounded-lg bg-white/80 p-3 ring-1 ring-inset ring-slate-200/80">
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "rounded px-1.5 py-px text-[10px] font-semibold uppercase tracking-wide",
            blocking ? "bg-rose-100 text-rose-700" : "bg-amber-100 text-amber-800",
          )}
        >
          {blocking ? "Blocking" : "Warning"}
        </span>
        <span className="text-[12.5px] font-semibold text-slate-800">{ISSUE_LABELS[reason.code] ?? reason.code}</span>
      </div>
      <p className="mt-1 text-[12.5px] leading-relaxed text-slate-600">{reason.message}</p>
    </li>
  );
}

function CheckScoreboard({ run }: { run: RunDetail }) {
  const counts = {
    PASSED: run.checks.filter((c) => c.status === "PASSED").length,
    WARNING: run.checks.filter((c) => c.status === "WARNING").length,
    FAILED: run.checks.filter((c) => c.status === "FAILED").length,
    SKIPPED: run.checks.filter((c) => c.status === "SKIPPED").length,
  };
  const total = Math.max(run.checks.length, 1);
  const rows = [
    { key: "PASSED", label: "Passed", bar: "bg-emerald-500", value: counts.PASSED },
    { key: "WARNING", label: "Warnings", bar: "bg-amber-500", value: counts.WARNING },
    { key: "FAILED", label: "Failed", bar: "bg-rose-500", value: counts.FAILED },
    { key: "SKIPPED", label: "Not applicable", bar: "bg-slate-300", value: counts.SKIPPED },
  ];
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <p className="eyebrow">Control coverage</p>
        <span className="tabular text-[12px] text-slate-500">{run.checks.length} evaluated</span>
      </div>
      <div className="mt-3 flex h-2.5 overflow-hidden rounded-full bg-slate-100">
        {rows.map((row) => (
          <div key={row.key} className={cn("h-full transition-[width] duration-500", row.bar)} style={{ width: `${(row.value / total) * 100}%` }} />
        ))}
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5">
        {rows.map((row) => (
          <div key={row.key} className="flex items-center justify-between text-[12.5px]">
            <dt className="flex items-center gap-1.5 text-slate-600">
              <span className={cn("h-2 w-2 rounded-full", row.bar)} />
              {row.label}
            </dt>
            <dd className="tabular font-semibold text-slate-900">{row.value}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

function LoadingView() {
  return (
    <div className="space-y-5">
      <Skeleton className="h-40 w-full rounded-lg" />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_400px]">
        <Card className="space-y-5 p-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex gap-4">
              <Skeleton className="h-9 w-9 rounded-full" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-40" />
                <Skeleton className="h-3 w-72" />
              </div>
            </div>
          ))}
        </Card>
        <Skeleton className="h-48 w-full rounded-lg" />
      </div>
    </div>
  );
}

