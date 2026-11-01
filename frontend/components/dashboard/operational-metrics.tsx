"use client";

import {
  Activity,
  Bot,
  CheckCircle2,
  Clock,
  Cpu,
  FileCheck,
  FileScan,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
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

  return (
    <div className="space-y-4">
      {/* Section Header with Time Filter */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-t pt-6">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold tracking-tight text-slate-900">
              Operational & AI Performance Analytics
            </h2>
            <span className="rounded bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
              Real Aggregations
            </span>
          </div>
          <p className="text-xs text-slate-500">
            End-to-end processing latencies, technical reliability rates, and model token usage.
          </p>
        </div>

        {/* Time-range filter pills */}
        <div className="flex items-center rounded-lg border bg-white p-0.5 shadow-2xs">
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
            action={<Clock className="h-4 w-4 text-slate-400" />}
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
            <div className="flex items-baseline justify-between">
              <span className="text-xs text-slate-500">Success Rate</span>
              <span className="tabular text-lg font-bold text-emerald-600">
                {reliability.technical_success_rate}%
              </span>
            </div>
            <div className="flex items-baseline justify-between border-t pt-2">
              <span className="text-xs text-slate-500">Failure Rate</span>
              <span className="tabular text-sm font-semibold text-slate-700">
                {reliability.technical_failure_rate}%
              </span>
            </div>
            <div className="flex items-baseline justify-between border-t pt-2">
              <span className="text-xs text-slate-500">Manual Review Rate</span>
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
            description="Digital text vs Tesseract OCR"
            action={<FileScan className="h-4 w-4 text-blue-500" />}
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
              <span className="text-xs text-slate-500">Total Runs Executed</span>
              <span className="tabular text-sm font-semibold text-slate-700">
                {volume.total_runs}
              </span>
            </div>
            <div className="flex items-baseline justify-between border-t pt-2 text-[11px] text-slate-500">
              <span>Avg OCR Duration:</span>
              <span className="font-medium text-slate-700">
                {speed.avg_document_extraction_seconds != null ? `${speed.avg_document_extraction_seconds}s` : "—"}
              </span>
            </div>
          </CardBody>
        </Card>

        {/* AI & Token Telemetry */}
        <Card className="border-slate-200/80 shadow-xs">
          <CardHeader
            title="AI Extraction Usage"
            description="Gemini & provider token telemetry"
            action={<Bot className="h-4 w-4 text-indigo-500" />}
          />
          <CardBody className="space-y-3">
            <div className="flex items-baseline justify-between">
              <span className="text-xs text-slate-500">Total Tokens</span>
              <span className="tabular text-lg font-bold text-indigo-600">
                {ai_usage.total_tokens.toLocaleString()}
              </span>
            </div>
            <div className="flex items-baseline justify-between border-t pt-2">
              <span className="text-xs text-slate-500">Prompt / Output</span>
              <span className="tabular text-sm font-semibold text-slate-700">
                {ai_usage.prompt_tokens.toLocaleString()} / {ai_usage.completion_tokens.toLocaleString()}
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
                      <td className="px-5 py-2 font-medium text-slate-900">{row.stage}</td>
                      <td className="tabular px-3 py-2 text-right">{row.count}</td>
                      <td className="tabular px-3 py-2 text-right font-semibold text-slate-800">
                        {row.avg_seconds}s
                      </td>
                      <td className="tabular px-5 py-2 text-right font-semibold text-amber-700">
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

