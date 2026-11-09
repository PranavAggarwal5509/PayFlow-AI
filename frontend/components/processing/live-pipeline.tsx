"use client";

import {
  AlertTriangle,
  Ban,
  Building2,
  Check,
  CircleDashed,
  Copy,
  FileScan,
  FileUp,
  Gavel,
  Loader2,
  Receipt,
  ScanText,
  ShoppingCart,
  Sparkles,
  X,
  type LucideIcon,
} from "lucide-react";

import { parseServerDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { RunCheck, RunDetail, StageStatus } from "@/types/api";

export type StepState = StageStatus | "WAITING";

export interface PipelineStep {
  key: string;
  label: string;
  detail: string;
  icon: LucideIcon;
}

/** The nine real backend stages, in execution order, with what each one does in plain words. */
export const PIPELINE: PipelineStep[] = [
  { key: "UPLOAD_RECEIVED", label: "Invoice received", detail: "File stored and fingerprinted (SHA-256) for exact-duplicate detection.", icon: FileUp },
  { key: "DOCUMENT_EXTRACTION", label: "Document reading", detail: "Reads the PDF text layer; scanned pages fall back to OCR.", icon: FileScan },
  { key: "AI_EXTRACTION", label: "AI field extraction", detail: "The LLM maps text into a strict schema. It never makes the decision.", icon: Sparkles },
  { key: "DATA_VALIDATION", label: "Data quality", detail: "Required fields, dates, currency, amounts and line items.", icon: ScanText },
  { key: "VENDOR_VERIFICATION", label: "Vendor verification", detail: "Vendor register, status, GSTIN checksum and bank-account fraud control.", icon: Building2 },
  { key: "PO_MATCHING", label: "Purchase order match", detail: "PO lookup or inference, ownership, balance and line-level 3-way match.", icon: ShoppingCart },
  { key: "DUPLICATE_CHECK", label: "Duplicate detection", detail: "Same file, same invoice number, or near-duplicate within 90 days.", icon: Copy },
  { key: "FINANCIAL_VALIDATION", label: "Financial controls", detail: "Arithmetic, GST rates and the approval-authority limit.", icon: Receipt },
  { key: "DECISION", label: "Decision", detail: "A deterministic rules engine turns check results into a verdict.", icon: Gavel },
];

export function stepState(run: RunDetail, key: string): StepState {
  const event = run.stages.find((s) => s.stage === key);
  return event ? event.status : "WAITING";
}

function stepDuration(run: RunDetail, key: string): string | null {
  const event = run.stages.find((s) => s.stage === key);
  if (!event?.completed_at) return null;
  const ms = parseServerDate(event.completed_at).getTime() - parseServerDate(event.started_at).getTime();
  if (ms < 1000) return `${Math.max(ms, 1)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

const NODE: Record<StepState, string> = {
  WAITING: "border-slate-200 bg-white text-slate-300",
  IN_PROGRESS: "border-indigo-500 bg-indigo-600 text-white animate-pulse-ring",
  COMPLETED: "border-emerald-500 bg-emerald-500 text-white",
  NEEDS_ATTENTION: "border-amber-500 bg-amber-500 text-white",
  FAILED: "border-rose-500 bg-rose-500 text-white",
};

function NodeIcon({ state, icon: Icon }: { state: StepState; icon: LucideIcon }) {
  if (state === "IN_PROGRESS") return <Loader2 className="h-4 w-4 animate-spin" />;
  if (state === "COMPLETED") return <Check className="h-4 w-4" strokeWidth={3} />;
  if (state === "NEEDS_ATTENTION") return <AlertTriangle className="h-4 w-4" strokeWidth={2.5} />;
  if (state === "FAILED") return <X className="h-4 w-4" strokeWidth={3} />;
  return <Icon className="h-4 w-4" />;
}

const STATE_TEXT: Record<StepState, { label: string; className: string }> = {
  WAITING: { label: "Queued", className: "text-slate-400" },
  IN_PROGRESS: { label: "Running", className: "text-indigo-600" },
  COMPLETED: { label: "Passed", className: "text-emerald-600" },
  NEEDS_ATTENTION: { label: "Flagged", className: "text-amber-600" },
  FAILED: { label: "Failed", className: "text-rose-600" },
};

export function LivePipeline({ run }: { run: RunDetail }) {
  return (
    <ol className="relative">
      {PIPELINE.map((step, index) => {
        const state = stepState(run, step.key);
        const event = run.stages.find((s) => s.stage === step.key);
        const checks = run.checks.filter((c) => c.stage === step.key);
        const last = index === PIPELINE.length - 1;
        const duration = stepDuration(run, step.key);
        return (
          <li key={step.key} className="relative flex gap-4 pb-6 last:pb-0">
            {!last && (
              <span
                aria-hidden
                className={cn(
                  "absolute left-[17px] top-10 h-[calc(100%-2.5rem)] w-0.5 rounded-full transition-colors duration-500",
                  state === "WAITING" || state === "IN_PROGRESS" ? "bg-slate-200" : "bg-emerald-200",
                )}
              />
            )}
            <span
              className={cn(
                "relative z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-2 transition-all duration-300",
                NODE[state],
              )}
            >
              <NodeIcon state={state} icon={step.icon} />
            </span>
            <div className={cn("min-w-0 flex-1 pt-1", state === "WAITING" && "opacity-55")}>
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
                <h4 className="text-[14px] font-semibold text-slate-900">{step.label}</h4>
                <span className={cn("text-[12px] font-medium", STATE_TEXT[state].className)}>
                  {STATE_TEXT[state].label}
                </span>
                {duration && <span className="tabular text-[11.5px] text-slate-400">{duration}</span>}
              </div>
              <p className="mt-0.5 text-[12.5px] text-slate-500">{step.detail}</p>
              {event?.message && state !== "IN_PROGRESS" && checks.length === 0 && (
                <p className="mt-1.5 text-[12.5px] text-slate-700">{event.message}</p>
              )}
              {checks.some((c) => c.status !== "PASSED") && (
                <ul className="mt-3 divide-y divide-slate-100 overflow-hidden rounded-lg border border-slate-200 bg-white">
                  {checks
                    .filter((c) => c.status !== "PASSED")
                    .map((check, i) => (
                      <CheckRow key={check.validation_type} check={check} delay={i * 60} />
                    ))}
                </ul>
              )}
              {checks.some((c) => c.status === "PASSED") && (
                <div className="mt-2.5 flex flex-wrap gap-1.5">
                  {checks
                    .filter((c) => c.status === "PASSED")
                    .map((check, i) => (
                      <span
                        key={check.validation_type}
                        title={check.message}
                        className="inline-flex animate-fade-up items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11.5px] font-medium text-emerald-700 ring-1 ring-inset ring-emerald-200/70"
                        style={{ animationDelay: `${i * 50}ms` }}
                      >
                        <Check className="h-3 w-3" strokeWidth={3} />
                        {check.label}
                      </span>
                    ))}
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

const CHECK_ICON: Record<RunCheck["status"], { icon: LucideIcon; className: string }> = {
  PASSED: { icon: Check, className: "bg-emerald-50 text-emerald-600 ring-emerald-200" },
  WARNING: { icon: AlertTriangle, className: "bg-amber-50 text-amber-600 ring-amber-200" },
  FAILED: { icon: X, className: "bg-rose-50 text-rose-600 ring-rose-200" },
  SKIPPED: { icon: CircleDashed, className: "bg-slate-50 text-slate-400 ring-slate-200" },
};

function CheckRow({ check, delay }: { check: RunCheck; delay: number }) {
  const meta = CHECK_ICON[check.status];
  const Icon = check.impact === "REJECT" && check.status === "FAILED" ? Ban : meta.icon;
  const showValues = check.status !== "PASSED" && (check.expected_value || check.actual_value);
  return (
    <li className="flex animate-fade-up gap-3 px-3.5 py-2.5" style={{ animationDelay: `${delay}ms` }}>
      <span className={cn("mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full ring-1 ring-inset", meta.className)}>
        <Icon className="h-3 w-3" strokeWidth={3} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[13px] font-medium text-slate-900">{check.label}</span>
          {check.status === "FAILED" && check.impact === "REJECT" && (
            <span className="rounded bg-rose-600 px-1.5 py-px text-[10px] font-semibold uppercase tracking-wide text-white">
              Hard stop
            </span>
          )}
        </div>
        <p className="mt-0.5 text-[12.5px] leading-relaxed text-slate-600">{check.message}</p>
        {showValues && (
          <div className="mt-1.5 flex flex-wrap gap-1.5 text-[11.5px]">
            {check.expected_value && (
              <span className="rounded-md bg-slate-100 px-2 py-0.5 text-slate-600">
                Expected <span className="font-medium tabular text-slate-900">{check.expected_value}</span>
              </span>
            )}
            {check.actual_value && (
              <span className="rounded-md bg-slate-100 px-2 py-0.5 text-slate-600">
                Found <span className="font-medium tabular text-slate-900">{check.actual_value}</span>
              </span>
            )}
          </div>
        )}
      </div>
    </li>
  );
}
