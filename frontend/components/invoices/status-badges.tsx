import { Badge } from "@/components/ui/badge";
import {
  CHECK_META,
  DECISION_META,
  PROCESSING_META,
  REVIEW_META,
  STAGE_STATUS_META,
} from "@/lib/status";
import type {
  CheckStatus,
  DecisionStatus,
  ProcessingStatus,
  ReviewStatus,
  RunStatus,
  StageStatus,
} from "@/types/api";

export function DecisionBadge({ status }: { status: DecisionStatus | null }) {
  if (!status) return <span className="text-slate-400">—</span>;
  const meta = DECISION_META[status];
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}

export function ProcessingBadge({ status }: { status: ProcessingStatus | RunStatus }) {
  const meta = PROCESSING_META[status];
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}

export function ReviewBadge({ status }: { status: ReviewStatus }) {
  const meta = REVIEW_META[status];
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}

export function CheckBadge({ status }: { status: CheckStatus }) {
  const meta = CHECK_META[status];
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}

export function StageBadge({ status }: { status: StageStatus | "WAITING" }) {
  const meta = STAGE_STATUS_META[status];
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}

/** Combined state for list rows: a failed run is shown as a technical failure, never "rejected". */
export function InvoiceStateBadge({
  processing,
  decision,
}: {
  processing: ProcessingStatus;
  decision: DecisionStatus | null;
}) {
  if (processing === "FAILED") return <ProcessingBadge status="FAILED" />;
  if (processing === "PROCESSING") return <ProcessingBadge status="PROCESSING" />;
  return <DecisionBadge status={decision} />;
}

