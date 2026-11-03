"use client";

import type { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo } from "react";

import { InvoiceStateBadge } from "@/components/invoices/status-badges";
import { DataTable } from "@/components/tables/data-table";
import { formatDate, formatMoney } from "@/lib/format";
import type { InvoiceListItem } from "@/types/api";

/** Shared invoice column definitions (dashboard + invoices page). */
export function useInvoiceColumns(options: { sortable?: boolean } = {}): ColumnDef<InvoiceListItem, unknown>[] {
  const sortable = options.sortable ?? false;
  return useMemo(
    () => [
      {
        id: "invoice_number",
        header: "Invoice",
        enableSorting: sortable,
        cell: ({ row }) => {
          const isHistorical = row.original.source_origin === "SEED_HISTORY";
          return (
            <div>
              <div className="flex items-center gap-1.5">
                <Link
                  href={`/invoices/${row.original.id}`}
                  className="font-medium text-foreground hover:text-primary"
                  onClick={(event) => event.stopPropagation()}
                >
                  {row.original.invoice_number ?? <span className="text-slate-400">No number</span>}
                </Link>
                {isHistorical ? (
                  <span className="inline-flex items-center rounded-sm bg-purple-50 px-1.5 py-0.5 text-[10px] font-semibold text-purple-700 ring-1 ring-inset ring-purple-600/20">
                    HISTORICAL
                  </span>
                ) : (
                  <span className="inline-flex items-center rounded-sm bg-blue-50 px-1.5 py-0.5 text-[10px] font-semibold text-blue-700 ring-1 ring-inset ring-blue-600/20">
                    LIVE UPLOAD
                  </span>
                )}
              </div>
              <p className="max-w-[200px] truncate text-xs text-muted-foreground">{row.original.original_file_name}</p>
            </div>
          );
        },
      },
      {
        id: "vendor",
        header: "Vendor",
        enableSorting: false,
        cell: ({ row }) => <span>{row.original.vendor_name ?? <span className="text-slate-400">Unknown</span>}</span>,
      },
      {
        id: "total_amount",
        header: "Amount",
        enableSorting: sortable,
        cell: ({ row }) => (
          <span className="tabular font-medium">{formatMoney(row.original.total_amount, row.original.currency)}</span>
        ),
      },
      {
        id: "uploaded_at",
        header: "Uploaded",
        enableSorting: sortable,
        cell: ({ row }) => <span className="text-slate-600">{formatDate(row.original.uploaded_at)}</span>,
      },
      {
        id: "processing_status",
        header: "Processing",
        enableSorting: sortable,
        cell: ({ row }) => (
          <span className="text-[13px] text-slate-600">
            {row.original.processing_status === "COMPLETED" ? "Completed" : row.original.processing_status === "FAILED" ? "Failed" : "In progress"}
          </span>
        ),
      },
      {
        id: "decision_status",
        header: "Decision",
        enableSorting: sortable,
        cell: ({ row }) => (
          <InvoiceStateBadge processing={row.original.processing_status} decision={row.original.decision_status} />
        ),
      },
    ],
    [sortable],
  );
}

export function RecentInvoicesTable({
  data,
  loading,
  error,
  onRetry,
}: {
  data: InvoiceListItem[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  const router = useRouter();
  const columns = useInvoiceColumns();
  return (
    <DataTable
      columns={columns}
      data={data}
      loading={loading}
      error={error}
      onRetry={onRetry}
      onRowClick={(row) =>
        router.push(row.processing_status === "PROCESSING" && row.latest_run_id ? `/processing/${row.latest_run_id}` : `/invoices/${row.id}`)
      }
      emptyTitle="No invoices yet"
      emptyDescription="Upload your first invoice to see it appear here."
    />
  );
}

