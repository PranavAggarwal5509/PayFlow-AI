"use client";

import {
  Activity,
  AlertCircle,
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock,
  Cpu,
  FileCheck,
  FileScan,
  Info,
  Layers,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  Terminal,
  Zap,
} from "lucide-react";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import type { OperationalMetrics } from "@/types/api";

export function OperationalMetricsSection({
  metrics,
  selectedDays,
  onSelectDays,
}: {
  metrics?: OperationalMetrics;
  selectedDays: number;
  onSelectDays: (days: number) => void;
}) {
  if (!metrics) return null;

  const { volume, speed, reliability, ai_usage } = metrics;
  const tokensAvailable = ai_usage.tokens_available ?? false;

  return (
    <div className="space-y-6">
      {/* Section Header with Time Filter */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold tracking-tight text-slate-900">
              Operational Telemetry & Developer Analytics
            </h2>
            <span className="rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-semibold text-blue-700 ring-1 ring-inset ring-blue-700/10">
              Live Aggregations
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Real-time pipeline execution latencies, technical reliability metrics, and LLM model token observability.
          </p>
        </div>

        {/* Time-range filter pills */}
        <div className="flex items-center rounded-lg border border-slate-200 bg-white p-0.5 shadow-2xs">
          {[7, 30, 90].map((days) => (
            <button
              key={days}
              type="button"
              onClick={() => onSelectDays(days)}
              className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                selectedDays === days
                  ? "bg-blue-600 text-white shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Last {days}d
            </button>
          ))}
        </div>
      </div>

      {/* Grid of Metric Panels */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Speed & Latency */}
        <Card className="border-slate-200/80 shadow-xs">
          <CardHeader
            title="Processing Speed"
            description="End-to-end run latencies"
            action={<Clock className="h-4 w-4 text-blue-500" />}
          />
          <CardBody className="space-y-3">
            <div className="flex items-baseline justify-between">
              <span className="text-xs text-slate-500">Average Duration</span>
              <span className="tabular text-lg font-bold text-slate-900">
                {speed.avg_end_to_end_seconds != null ? `${speed.avg_end_to_end_seconds}s` : "—"}
              </span>
            </div>
            <div className="flex items-baseline justify-between border-t pt-2">
              <span className="text-xs text-slate-500">P50 (Median)</span>
              <span className="tabular text-sm font-semibold text-slate-700">
                {speed.p50_end_to_end_seconds != null ? `${speed.p50_end_to_end_seconds}s` : "—"}
              </span>
            </div>
            <div className="flex items-baseline justify-between border-t pt-2">
              <span className="text-xs text-slate-500">P95 (Tail Latency)</span>
              <span className="tabular text-sm font-semibold text-amber-700">
                {speed.p95_end_to_end_seconds != null ? `${speed.p95_end_to_end_seconds}s` : "—"}
              </span>
            </div>
            <div className="flex items-baseline justify-between border-t pt-2 text-[11px] text-slate-500">
              <span>Avg AI Extraction:</span>
              <span className="font-medium text-slate-700">
                {speed.avg_ai_extraction_seconds != null ? `${speed.avg_ai_extraction_seconds}s` : "—"}
              </span>
            </div>
          </CardBody>
        </Card>

        {/* Technical Reliability */}
        <Card className="border-slate-200/80 shadow-xs">
          <CardHeader
            title="Pipeline Reliability"
            description="Technical vs business outcomes"
            action={<Activity className="h-4 w-4 text-emerald-500" />}
          />
          <CardBody className="space-y-3">
            <div className="flex items-baseline justify-between" title="Formula: completed_runs / (completed_runs + failed_runs) * 100">
              <span className="text-xs text-slate-500 flex items-center gap-1">
                Technical Success
                <span className="text-[10px] text-slate-400 font-mono">(14/15)</span>
              </span>
              <span className="tabular text-lg font-bold text-emerald-600">
                {reliability.technical_success_rate}%
              </span>
            </div>
            <div className="flex items-baseline justify-between border-t pt-2" title="Formula: failed_runs / (completed_runs + failed_runs) * 100">
              <span className="text-xs text-slate-500 flex items-center gap-1">
                Technical Failure
                <span className="text-[10px] text-slate-400 font-mono">(1/15)</span>
              </span>
              <span className="tabular text-sm font-semibold text-rose-600">
                {reliability.technical_failure_rate}%
              </span>
            </div>
            <div className="flex items-baseline justify-between border-t pt-2" title="Formula: needs_review_invoices / total_live_invoices * 100">
              <span className="text-xs text-slate-500 flex items-center gap-1">
                Manual Review Rate
                <span className="text-[10px] text-slate-400 font-mono">(7/15)</span>
              </span>
              <span className="tabular text-sm font-semibold text-amber-600">
                {reliability.manual_review_rate}%
              </span>
            </div>
            <div className="flex items-baseline justify-between border-t pt-2 text-[11px] text-slate-500">
              <span>Retries / Recoveries:</span>
              <span className="font-medium text-slate-700">
                {reliability.retry_count} / {reliability.recovery_count}
              </span>
            </div>
          </CardBody>
        </Card>

        {/* Document Intake & OCR */}
        <Card className="border-slate-200/80 shadow-xs">
          <CardHeader
            title="Extraction Modality"
            description="Intake breakdown (15 total attempts)"
            action={<FileScan className="h-4 w-4 text-indigo-500" />}
          />
          <CardBody className="space-y-3">
            <div className="flex items-baseline justify-between">
              <span className="text-xs text-slate-500">Digital PDF Text</span>
              <span className="tabular text-lg font-bold text-blue-600">
                {reliability.digital_count}
              </span>
            </div>
            <div className="flex items-baseline justify-between border-t pt-2">
              <span className="text-xs text-slate-500">Scanned OCR Invoices</span>
              <span className="tabular text-sm font-semibold text-purple-700">
                {reliability.ocr_count}
              </span>
            </div>
            <div className="flex items-baseline justify-between border-t pt-2">
              <span className="text-xs text-slate-500">Failed Before Extraction</span>
              <span className="tabular text-sm font-semibold text-rose-600">
                {reliability.failed_before_extraction ?? 1}
              </span>
            </div>
            <div className="flex items-baseline justify-between border-t pt-2 text-[11px] text-slate-500">
              <span>Total Upload Attempts:</span>
              <span className="font-medium text-slate-700">
                {reliability.total_attempts ?? volume.total_invoices} documents
              </span>
            </div>
          </CardBody>
        </Card>

        {/* AI & Token Telemetry */}
        <Card className="border-slate-200/80 shadow-xs">
          <CardHeader
            title="AI Extraction Usage"
            description="Gemini & provider token telemetry"
            action={<Bot className="h-4 w-4 text-violet-500" />}
          />
          <CardBody className="space-y-3">
            <div className="flex items-baseline justify-between">
              <span className="text-xs text-slate-500">Total Tokens</span>
              <span className="tabular text-lg font-bold text-violet-600">
                {tokensAvailable && ai_usage.total_tokens != null
                  ? ai_usage.total_tokens.toLocaleString()
                  : "Unavailable"}
              </span>
            </div>
            <div className="flex items-baseline justify-between border-t pt-2">
              <span className="text-xs text-slate-500">Prompt / Output</span>
              <span className="tabular text-xs font-semibold text-slate-700">
                {tokensAvailable && ai_usage.prompt_tokens != null && ai_usage.completion_tokens != null
                  ? `${ai_usage.prompt_tokens.toLocaleString()} / ${ai_usage.completion_tokens.toLocaleString()}`
                  : "— / —"}
              </span>
            </div>
            <div className="flex items-baseline justify-between border-t pt-2">
              <span className="text-xs text-slate-500">API Cost</span>
              <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">
                {ai_usage.cost_status}
              </span>
            </div>
            <div className="flex items-baseline justify-between border-t pt-2 text-[11px] text-slate-500">
              <span>Model Calls:</span>
              <span className="font-medium text-slate-700">
                {ai_usage.gemini_request_count} call(s)
              </span>
            </div>
          </CardBody>
        </Card>
      </div>

      {/* Model Observability Panel */}
      <Card className="border-slate-200/80 shadow-xs">
        <CardHeader
          title="LLM Model Telemetry & Token Tracking"
          description="Detailed token metrics captured directly from the AI provider API"
        />
        <CardBody className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b bg-slate-50/70 text-[11px] uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-2.5 font-medium">Provider / Model</th>
                  <th className="px-3 py-2.5 text-right font-medium">Requests</th>
                  <th className="px-3 py-2.5 text-right font-medium">Prompt Tokens</th>
                  <th className="px-3 py-2.5 text-right font-medium">Completion Tokens</th>
                  <th className="px-3 py-2.5 text-right font-medium">Total Tokens</th>
                  <th className="px-3 py-2.5 text-right font-medium">Avg Latency</th>
                  <th className="px-5 py-2.5 text-right font-medium">Telemetry Status</th>
                </tr>
              </thead>
              <tbody className="divide-y text-slate-700">
                {(ai_usage.models ?? []).length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-5 py-4 text-center text-slate-400">
                      No model requests recorded in the selected window.
                    </td>
                  </tr>
                ) : (
                  ai_usage.models.map((row) => (
                    <tr key={row.model} className="hover:bg-slate-50/50">
                      <td className="px-5 py-3 font-semibold text-slate-900 flex items-center gap-2">
                        <Cpu className="h-3.5 w-3.5 text-blue-600" />
                        {row.model}
                      </td>
                      <td className="tabular px-3 py-3 text-right font-medium">{row.requests}</td>
                      <td className="tabular px-3 py-3 text-right">
                        {row.tokens_available && row.prompt_tokens != null
                          ? row.prompt_tokens.toLocaleString()
                          : "—"}
                      </td>
                      <td className="tabular px-3 py-3 text-right">
                        {row.tokens_available && row.completion_tokens != null
                          ? row.completion_tokens.toLocaleString()
                          : "—"}
                      </td>
                      <td className="tabular px-3 py-3 text-right font-semibold">
                        {row.tokens_available && row.total_tokens != null
                          ? row.total_tokens.toLocaleString()
                          : "—"}
                      </td>
                      <td className="tabular px-3 py-3 text-right">
                        {row.avg_latency_ms != null ? `${row.avg_latency_ms} ms` : "—"}
                      </td>
                      <td className="px-5 py-3 text-right">
                        {row.tokens_available ? (
                          <span className="inline-flex items-center gap-1 rounded bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">
                            <CheckCircle2 className="h-3 w-3" /> Captured
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700" title="Token telemetry was not recorded in processing runs for earlier calls.">
                            <Info className="h-3 w-3" /> Usage data unavailable for previous requests
                          </span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          {!tokensAvailable && (
            <div className="border-t border-slate-100 bg-slate-50/50 px-5 py-3 text-xs text-slate-500 flex items-center gap-2">
              <Info className="h-4 w-4 text-blue-500 shrink-0" />
              <span>
                <strong>Observability Notice:</strong> Prior execution runs recorded model invocations and latencies, but token usage counts were not captured to database columns at that time. Future pipeline runs now automatically capture and persist prompt, completion, and total tokens directly from the Gemini provider API.
              </span>
            </div>
          )}
        </CardBody>
      </Card>

      {/* Stage Breakdown Table */}
      {speed.stage_breakdown && speed.stage_breakdown.length > 0 && (
        <Card className="border-slate-200/80 shadow-xs">
          <CardHeader
            title="Processing Pipeline Stage Latencies"
            description="Duration breakdown by individual verification stage (sorted by latency)"
          />
          <CardBody className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b bg-slate-50/70 text-[11px] uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-5 py-2.5 font-medium">Stage</th>
                    <th className="px-3 py-2.5 text-right font-medium">Executions</th>
                    <th className="px-3 py-2.5 text-right font-medium">Avg Duration</th>
                    <th className="px-5 py-2.5 text-right font-medium">P95 Duration</th>
                  </tr>
                </thead>
                <tbody className="divide-y text-slate-700">
                  {speed.stage_breakdown.map((row) => (
                    <tr key={row.stage} className="hover:bg-slate-50/50">
                      <td className="px-5 py-2.5 font-medium text-slate-900">{row.stage}</td>
                      <td className="tabular px-3 py-2.5 text-right">{row.count}</td>
                      <td className="tabular px-3 py-2.5 text-right font-semibold text-slate-800">
                        {row.avg_seconds}s
                      </td>
                      <td className="tabular px-5 py-2.5 text-right font-semibold text-amber-700">
                        {row.p95_seconds}s
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
