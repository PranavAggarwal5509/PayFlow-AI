"use client";

import { AlertCircle, AlertTriangle, CheckCircle2, Circle, Loader2 } from "lucide-react";

import { formatDateTime } from "@/lib/format";
import type { TrackerStep } from "@/lib/tracker";
import { cn } from "@/lib/utils";
import { StageBadge } from "@/components/invoices/status-badges";

const ICON = {
  WAITING: <Circle className="h-5 w-5 text-slate-300" />,
  IN_PROGRESS: <Loader2 className="h-5 w-5 animate-spin text-primary" />,
  COMPLETED: <CheckCircle2 className="h-5 w-5 text-success" />,
  FAILED: <AlertCircle className="h-5 w-5 text-danger" />,
  NEEDS_ATTENTION: <AlertTriangle className="h-5 w-5 text-amber-500" />,
} as const;

export function ProcessingTracker({ steps }: { steps: TrackerStep[] }) {
  return (
    <ol className="relative" aria-label="Processing stages">
      {steps.map((step, index) => (
        <li key={step.key} className="relative flex gap-4 pb-6 last:pb-0" data-status={step.status}>
          {index < steps.length - 1 && (
            <span
              className={cn(
                "absolute left-[9.5px] top-6 h-[calc(100%-1.25rem)] w-px",
                step.status === "COMPLETED" || step.status === "NEEDS_ATTENTION" ? "bg-success/40" : "bg-slate-200",
              )}
            />
          )}
          <div className="relative z-10 bg-white">{ICON[step.status]}</div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <p className={cn("text-sm font-medium", step.status === "WAITING" && "text-slate-400")}>{step.label}</p>
              <StageBadge status={step.status} />
            </div>
            {step.message && step.status !== "WAITING" && (
              <p className={cn("mt-1 text-[13px]", step.status === "FAILED" ? "text-danger" : "text-muted-foreground")}>{step.message}</p>
            )}
            {step.startedAt && (
              <p className="tabular mt-0.5 text-xs text-slate-400">
                Started {formatDateTime(step.startedAt)}
                {step.completedAt && ` · finished ${formatDateTime(step.completedAt)}`}
              </p>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}

