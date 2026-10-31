"use client";

import { ArrowRight, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { DecisionBadge, ProcessingBadge } from "@/components/invoices/status-badges";
import { ProcessingTracker } from "@/components/invoices/processing-tracker";
import { PageHeader } from "@/components/layout/page-header";
import { ErrorState } from "@/components/tables/table-states";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useRunEvents } from "@/hooks/use-run-events";
import { ApiError } from "@/lib/api";
import { formatDuration } from "@/lib/format";
import { buildTracker } from "@/lib/tracker";
import { STAGE_LABELS } from "@/lib/status";
import { invoiceService } from "@/services";

function useElapsed(startedAt: string | undefined, completedAt: string | null | undefined, running: boolean) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [running]);
  if (!startedAt) return null;
  const end = completedAt ? new Date(completedAt).getTime() : now;
  return Math.max(0, (end - new Date(startedAt).getTime()) / 1000);
}

export default function ProcessingPage() {
  const { runId } = useParams<{ runId: string }>();
  const router = useRouter();
  const { run, error } = useRunEvents(runId);
  const [retrying, setRetrying] = useState(false);
  const running = !!run && (run.status === "QUEUED" || run.status === "RUNNING");
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
  if (!run)
    return (
      <Card>
        <CardBody className="space-y-4">
          <Skeleton className="h-6 w-48" />
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </CardBody>
      </Card>
    );

  const steps = buildTracker(run);
  return (
    <>
      <PageHeader
        title={run.invoice_number ? `Processing ${run.invoice_number}` : "Processing invoice"}
        description={`${run.original_file_name ?? ""} · run #${run.run_number}`}
        actions={
          <>
            {run.can_retry && (
              <Button onClick={retry} disabled={retrying}>
                <RotateCcw className="h-4 w-4" /> Retry processing
              </Button>
            )}
            {run.status === "COMPLETED" && (
              <Button asChild>
                <Link href={`/invoices/${run.invoice_id}`}>
                  View invoice <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            )}
          </>
        }
      />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Pipeline progress" description="Live state from the processing workflow" />
          <CardBody>
            <ProcessingTracker steps={steps} />
          </CardBody>
        </Card>
        <div className="space-y-4">
          <Card>
            <CardBody className="space-y-3 text-sm">
              <Row label="Status">
                <ProcessingBadge status={run.status} />
              </Row>
              <Row label="Current stage">{STAGE_LABELS[run.current_stage ?? ""] ?? "—"}</Row>
              <Row label="Duration">
                <span className="tabular">{formatDuration(elapsed)}</span>
                {running && <span className="ml-1 text-xs text-muted-foreground">(elapsed)</span>}
              </Row>
              {run.status === "COMPLETED" && (
                <Row label="Decision">
                  <DecisionBadge status={run.decision_status} />
                </Row>
              )}
            </CardBody>
          </Card>
          {run.status === "FAILED" && (
            <Card className="border-danger-ring bg-danger-soft/50">
              <CardBody>
                <p className="text-sm font-semibold text-danger">Processing failed</p>
                <p className="mt-1 text-[13px] text-slate-700">{run.error_message ?? "An error occurred."}</p>
                <p className="mt-3 text-xs text-muted-foreground">
                  This is a technical failure. The invoice has <strong>not</strong> been rejected. Retrying creates a new
                  run and keeps this one in the history.
                </p>
              </CardBody>
            </Card>
          )}
          {error && <p className="text-xs text-warning">Connection issue: {error}. Retrying…</p>}
        </div>
      </div>
    </>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{children}</span>
    </div>
  );
}

