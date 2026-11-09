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
                  className="font-semibold text-slate-900 hover:text-indigo-600"
                  onClick={(event) => event.stopPropagation()}
                >
                  {row.original.invoice_number ?? <span className="text-slate-400">No number</span>}
                </Link>
                {isHistorical && (
                  <span className="inline-flex items-center rounded bg-slate-100 px-1.5 py-px text-[10px] font-medium text-slate-500 ring-1 ring-inset ring-slate-200">
                    History
                  </span>
                )}
              </div>
              <p className="max-w-[220px] truncate font-mono text-[11px] text-slate-400">{row.original.original_file_name}</p>
            </div>
          );
        },
      },
      {
        id: "vendor",
        header: "Vendor",
        enableSorting: false,
        cell: ({ row }) => <VendorCell name={row.original.vendor_name} />,
      },
      {
        id: "total_amount",
        header: () => <span className="block text-right">Amount</span>,
        enableSorting: sortable,
        cell: ({ row }) => (
          <span className="tabular block text-right font-semibold text-slate-900">
            {formatMoney(row.original.total_amount, row.original.currency)}
          </span>
        ),
      },
      {
        id: "uploaded_at",
        header: "Uploaded",
        enableSorting: sortable,
        cell: ({ row }) => <span className="text-slate-600">{formatDate(row.original.uploaded_at)}</span>,
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


const AVATAR_TONES = [
  "bg-indigo-100 text-indigo-700",
  "bg-emerald-100 text-emerald-700",
  "bg-amber-100 text-amber-800",
  "bg-sky-100 text-sky-700",
  "bg-violet-100 text-violet-700",
  "bg-rose-100 text-rose-700",
];

export function VendorCell({ name }: { name: string | null }) {
  if (!name) return <span className="text-slate-400">Unknown vendor</span>;
  const initials = name
    .replace(/[^A-Za-z ]/g, " ")
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();
  const tone = AVATAR_TONES[[...name].reduce((a, c) => a + c.charCodeAt(0), 0) % AVATAR_TONES.length];
  return (
    <span className="flex items-center gap-2.5">
      <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[11px] font-bold ${tone}`}>{initials}</span>
      <span className="max-w-[240px] truncate text-slate-700">{name}</span>
    </span>
  );
}
