"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Activity, AlertCircle, ArrowUpRight, CheckCircle2, Clock, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo } from "react";

import { DecisionBadge, ProcessingBadge } from "@/components/invoices/status-badges";
import { PageHeader } from "@/components/layout/page-header";
import { DataTable } from "@/components/tables/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { useAsync } from "@/hooks/use-async";
import { useDebounce } from "@/hooks/use-debounce";
import { useListState } from "@/hooks/use-list-state";
import { formatDateTime, titleCase } from "@/lib/format";
import { runService } from "@/services";
import type { RunSummary } from "@/types/api";

function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 1) return "< 1s";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const mins = Math.floor(seconds / 60);
  const rem = Math.round(seconds % 60);
  return `${mins}m ${rem}s`;
}

export default function ActivityPage() {
  const router = useRouter();
  const list = useListState({ status: "" }, [{ id: "started_at", desc: true }]);
  const params = {
    ...list.filters,
    page: list.page,
    page_size: 20,
  };

  const runs = useAsync(() => runService.list(params), [JSON.stringify(params)]);

  const columns = useMemo<ColumnDef<RunSummary, unknown>[]>(
    () => [
      {
        id: "id",
        header: "Run ID",
        cell: ({ row }) => (
          <Link
            href={`/processing/${row.original.id}`}
            className="font-mono text-[12px] font-semibold text-primary hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            {row.original.id.slice(0, 8)}…
          </Link>
        ),
      },
      {
        id: "invoice",
        header: "Invoice / Document",
        cell: ({ row }) => (
          <div>
            {row.original.invoice_number ? (
              <Link
                href={`/invoices/${row.original.invoice_id}`}
                className="font-mono text-[13px] font-medium text-primary hover:underline"
                onClick={(e) => e.stopPropagation()}
              >
                {row.original.invoice_number}
              </Link>
            ) : (
              <Link
                href={`/invoices/${row.original.invoice_id}`}
                className="text-xs text-muted-foreground hover:underline"
                onClick={(e) => e.stopPropagation()}
              >
                {row.original.original_file_name || "Invoice Record"}
              </Link>
            )}
            <p className="text-[11px] text-muted-foreground">Run #{row.original.run_number}</p>
          </div>
        ),
      },
      {
        id: "status",
        header: "Execution Status",
        cell: ({ row }) => <ProcessingBadge status={row.original.status} />,
      },
      {
        id: "current_stage",
        header: "Stage",
        cell: ({ row }) => (
          <span className="text-xs font-medium text-slate-700">
            {row.original.current_stage ? titleCase(row.original.current_stage) : "—"}
          </span>
        ),
      },
      {
        id: "started_at",
        header: "Started At",
        cell: ({ row }) => (
          <span className="text-xs text-muted-foreground">
            {formatDateTime(row.original.started_at)}
          </span>
        ),
      },
      {
        id: "duration",
        header: "Duration",
        cell: ({ row }) => (
          <span className="tabular text-xs font-medium text-slate-600">
            {formatDuration(row.original.duration_seconds)}
          </span>
        ),
      },
      {
        id: "decision_status",
        header: "Decision",
        cell: ({ row }) => <DecisionBadge status={row.original.decision_status} />,
      },
      {
        id: "error",
        header: "Details / Error",
        cell: ({ row }) => {
          if (row.original.error_message) {
            return (
              <span
                className="inline-flex items-center gap-1 text-xs text-rose-600 max-w-[220px] truncate"
                title={row.original.error_message}
              >
                <AlertCircle className="h-3 w-3 shrink-0" />
                {row.original.error_message}
              </span>
            );
          }
          return <span className="text-slate-400 text-xs">—</span>;
        },
      },
      {
        id: "actions",
        header: "",
        cell: ({ row }) => (
          <Button
            variant="ghost"
            size="sm"
            asChild
            className="h-7 text-xs gap-1"
            onClick={(e) => e.stopPropagation()}
          >
            <Link href={`/processing/${row.original.id}`}>
              Live Tracker <ArrowUpRight className="h-3 w-3" />
            </Link>
          </Button>
        ),
      },
    ],
    [],
  );

  return (
    <>
      <PageHeader
        title="Processing Activity"
        description="System-wide audit trail of all background pipeline executions and runs."
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() => runs.reload()}
            className="gap-1.5"
            disabled={runs.loading}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${runs.loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        }
      />

      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b p-4">
          <div className="w-full sm:w-48">
            <Select
              value={list.filters.status}
              onChange={(e) => list.setFilter("status", e.target.value)}
              aria-label="Filter by run status"
            >
              <option value="">All run statuses</option>
              <option value="RUNNING">Running</option>
              <option value="COMPLETED">Completed</option>
              <option value="FAILED">Failed</option>
              <option value="QUEUED">Queued</option>
            </Select>
          </div>

          {list.active && (
            <button
              type="button"
              onClick={list.clear}
              className="text-xs font-medium text-slate-500 hover:text-foreground"
            >
              Clear filter
            </button>
          )}
        </div>

        <DataTable
          columns={columns}
          data={runs.data?.items ?? []}
          loading={runs.loading}
          error={runs.error}
          onRetry={runs.reload}
          meta={runs.data?.meta}
          onPageChange={list.setPage}
          onRowClick={(run) => router.push(`/processing/${run.id}`)}
          emptyTitle="No processing runs found"
          emptyDescription="There are no processing runs recorded for the selected filter."
          filtered={list.active}
        />
      </Card>
    </>
  );
}
