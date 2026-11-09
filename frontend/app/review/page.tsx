"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { ExternalLink, PlayCircle } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo } from "react";

import { ReviewBadge } from "@/components/invoices/status-badges";
import { PageHeader } from "@/components/layout/page-header";
import { ReviewActions } from "@/components/review/review-actions";
import { DataTable } from "@/components/tables/data-table";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { useAsync } from "@/hooks/use-async";
import { useDebounce } from "@/hooks/use-debounce";
import { useListState } from "@/hooks/use-list-state";
import { documentUrl } from "@/lib/api";
import { formatDate, formatMoney } from "@/lib/format";
import { ISSUE_LABELS } from "@/lib/status";
import { reviewService, vendorService } from "@/services";
import type { ReviewListItem } from "@/types/api";

const INITIAL = { q: "", review_status: "OPEN", issue_type: "", vendor_id: "", date_from: "", date_to: "" };

/** Where a review row leads: the processing run whose decision opened the review. */
const runHref = (row: ReviewListItem): string =>
  row.review_run_id ? `/processing/${row.review_run_id}` : `/invoices/${row.invoice_id}`;

export default function ReviewQueuePage() {
  const router = useRouter();
  const list = useListState(INITIAL, []);
  const query = useDebounce(list.filters.q);
  const vendors = useAsync(() => vendorService.list({ page_size: 100 }), []);
  const params = { ...list.filters, q: query, page: list.page, page_size: 15 };
  const reviews = useAsync(() => reviewService.list(params), [JSON.stringify(params)]);

  const columns = useMemo<ColumnDef<ReviewListItem, unknown>[]>(
    () => [
      {
        id: "invoice",
        header: "Invoice",
        enableSorting: false,
        cell: ({ row }) => (
          <div>
            <Link
              href={runHref(row.original)}
              onClick={(e) => e.stopPropagation()}
              className="font-semibold text-slate-900 hover:text-indigo-600"
            >
              {row.original.invoice_number ?? <span className="text-slate-400">No number</span>}
            </Link>
            <span className="mt-0.5 flex items-center gap-1 text-[11.5px] font-medium text-indigo-600 opacity-0 transition-opacity group-hover:opacity-100">
              <PlayCircle className="h-3 w-3" /> View the run that flagged it
            </span>
          </div>
        ),
      },
      { id: "vendor", header: "Vendor", enableSorting: false, cell: ({ row }) => row.original.vendor_name ?? "Unknown" },
      {
        id: "amount",
        header: "Amount",
        enableSorting: false,
        cell: ({ row }) => <span className="tabular font-medium">{formatMoney(row.original.total_amount, row.original.currency)}</span>,
      },
      {
        id: "issue",
        header: "Issue",
        enableSorting: false,
        cell: ({ row }) => (
          <div className="min-w-[220px] max-w-[380px]">
            {row.original.issue_type && (
              <span className="inline-flex rounded bg-amber-50 px-1.5 py-px text-[11px] font-semibold text-amber-800 ring-1 ring-inset ring-amber-200">
                {ISSUE_LABELS[row.original.issue_type] ?? row.original.issue_type}
              </span>
            )}
            <p className="mt-1 line-clamp-2 text-[13px] leading-snug text-slate-600" title={row.original.issue ?? undefined}>
              {row.original.issue ?? "—"}
            </p>
          </div>
        ),
      },
      { id: "uploaded", header: "Uploaded", enableSorting: false, cell: ({ row }) => formatDate(row.original.uploaded_at) },
      { id: "status", header: "Status", enableSorting: false, cell: ({ row }) => <ReviewBadge status={row.original.review_status} /> },
      {
        id: "actions",
        header: "Action",
        enableSorting: false,
        cell: ({ row }) => {
          const open = row.original.review_status === "PENDING" || row.original.review_status === "CLARIFICATION_REQUESTED";
          return (
            <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
              <Button asChild variant="ghost" size="icon" aria-label="View original PDF" title="View original PDF">
                <a href={documentUrl(row.original.invoice_id)} target="_blank" rel="noreferrer">
                  <ExternalLink className="h-4 w-4" />
                </a>
              </Button>
              {open && (
                <ReviewActions size="sm" reviewId={row.original.id} invoiceLabel={row.original.invoice_number ?? "invoice"} onDone={reviews.reload} />
              )}
            </div>
          );
        },
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [reviews.reload],
  );

  return (
    <>
      <PageHeader eyebrow="Accounts payable" title="Review queue" description="Invoices the rules engine could not clear on its own. Every action you take is audited." />
      <Card>
        <div className="grid grid-cols-2 gap-3 border-b p-4 md:grid-cols-3 xl:grid-cols-6">
          <Input value={list.filters.q} onChange={(e) => list.setFilter("q", e.target.value)} placeholder="Search…" aria-label="Search reviews" />
          <Select value={list.filters.review_status} onChange={(e) => list.setFilter("review_status", e.target.value)} aria-label="Review status">
            <option value="OPEN">Open</option>
            <option value="PENDING">Pending</option>
            <option value="CLARIFICATION_REQUESTED">Awaiting clarification</option>
            <option value="APPROVED">Approved</option>
            <option value="REJECTED">Rejected</option>
          </Select>
          <Select value={list.filters.issue_type} onChange={(e) => list.setFilter("issue_type", e.target.value)} aria-label="Issue type">
            <option value="">All issues</option>
            {Object.entries(ISSUE_LABELS).map(([code, label]) => (
              <option key={code} value={code}>
                {label}
              </option>
            ))}
          </Select>
          <Select value={list.filters.vendor_id} onChange={(e) => list.setFilter("vendor_id", e.target.value)} aria-label="Vendor">
            <option value="">All vendors</option>
            {(vendors.data?.items ?? []).map((v) => (
              <option key={v.id} value={v.id}>
                {v.vendor_name}
              </option>
            ))}
          </Select>
          <Input type="date" value={list.filters.date_from} onChange={(e) => list.setFilter("date_from", e.target.value)} aria-label="From date" />
          <Input type="date" value={list.filters.date_to} onChange={(e) => list.setFilter("date_to", e.target.value)} aria-label="To date" />
          {list.active && (
            <Button variant="ghost" onClick={list.clear}>
              Clear filters
            </Button>
          )}
        </div>
        <DataTable
          columns={columns}
          data={reviews.data?.items ?? []}
          loading={reviews.loading}
          error={reviews.error}
          onRetry={reviews.reload}
          meta={reviews.data?.meta}
          onPageChange={list.setPage}
          filtered={list.active}
          onRowClick={(row) => router.push(runHref(row))}
          emptyTitle="Nothing to review"
          emptyDescription="Invoices that need manual attention will show up here."
        />
      </Card>
    </>
  );
}

