"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { ShoppingCart } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo } from "react";

import { PageHeader } from "@/components/layout/page-header";
import { DataTable } from "@/components/tables/data-table";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { useAsync } from "@/hooks/use-async";
import { useDebounce } from "@/hooks/use-debounce";
import { useListState } from "@/hooks/use-list-state";
import { formatDate, formatMoney, titleCase } from "@/lib/format";
import { poTone } from "@/lib/status";
import { purchaseOrderService } from "@/services";
import type { PurchaseOrder } from "@/types/api";

export default function PurchaseOrdersPage() {
  const router = useRouter();
  const list = useListState({ q: "", status: "" }, [{ id: "po_date", desc: true }]);
  const debouncedQuery = useDebounce(list.filters.q);
  const params = {
    ...list.filters,
    q: debouncedQuery,
    ...list.sortParams,
    page: list.page,
    page_size: 15,
  };

  const pos = useAsync(() => purchaseOrderService.list(params), [JSON.stringify(params)]);

  const columns = useMemo<ColumnDef<PurchaseOrder, unknown>[]>(
    () => [
      {
        id: "po_number",
        header: "PO Number",
        cell: ({ row }) => (
          <Link
            href={`/purchase-orders/${row.original.id}`}
            className="font-mono text-[13px] font-semibold text-primary hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            {row.original.po_number}
          </Link>
        ),
      },
      {
        id: "vendor_name",
        header: "Vendor",
        cell: ({ row }) => (
          <div>
            <Link
              href={`/vendors/${row.original.vendor_id}`}
              className="font-medium hover:text-primary hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              {row.original.vendor_name}
            </Link>
          </div>
        ),
      },
      {
        id: "po_date",
        header: "PO Date",
        cell: ({ row }) => (
          <span className="text-muted-foreground">{formatDate(row.original.po_date)}</span>
        ),
      },
      {
        id: "total_amount",
        header: "Total Amount",
        cell: ({ row }) => (
          <span className="tabular font-medium">
            {formatMoney(row.original.total_amount, row.original.currency)}
          </span>
        ),
      },
      {
        id: "consumed_amount",
        header: "Consumed",
        enableSorting: false,
        cell: ({ row }) => (
          <span className="tabular text-muted-foreground">
            {formatMoney(row.original.consumed_amount, row.original.currency)}
          </span>
        ),
      },
      {
        id: "remaining_balance",
        header: "Remaining Balance",
        enableSorting: false,
        cell: ({ row }) => {
          const balance = Number(row.original.remaining_balance);
          const isZero = balance <= 0;
          return (
            <span
              className={`tabular font-semibold ${
                isZero ? "text-amber-600" : "text-emerald-700"
              }`}
            >
              {formatMoney(row.original.remaining_balance, row.original.currency)}
            </span>
          );
        },
      },
      {
        id: "status",
        header: "Status",
        cell: ({ row }) => (
          <Badge tone={poTone(row.original.status)}>{titleCase(row.original.status)}</Badge>
        ),
      },
    ],
    [],
  );

  return (
    <>
      <PageHeader
        title="Purchase Orders"
        description="Active and historical purchase orders used for 2-way and 3-way matching."
      />

      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b p-4">
          <div className="w-full sm:w-64">
            <Input
              placeholder="Search by PO number or vendor…"
              value={list.filters.q}
              onChange={(e) => list.setFilter("q", e.target.value)}
              aria-label="Search purchase orders"
            />
          </div>

          <div className="w-full sm:w-44">
            <Select
              value={list.filters.status}
              onChange={(e) => list.setFilter("status", e.target.value)}
              aria-label="Filter by status"
            >
              <option value="">All statuses</option>
              <option value="ACTIVE">Active</option>
              <option value="CLOSED">Closed</option>
              <option value="CANCELLED">Cancelled</option>
            </Select>
          </div>

          {list.active && (
            <button
              type="button"
              onClick={list.clear}
              className="text-xs font-medium text-slate-500 hover:text-foreground"
            >
              Clear filters
            </button>
          )}
        </div>

        <DataTable
          columns={columns}
          data={pos.data?.items ?? []}
          loading={pos.loading}
          error={pos.error}
          onRetry={pos.reload}
          meta={pos.data?.meta}
          onPageChange={list.setPage}
          sorting={list.sorting}
          onSortingChange={list.setSorting}
          onRowClick={(po) => router.push(`/purchase-orders/${po.id}`)}
          emptyTitle="No purchase orders found"
          emptyDescription="There are no purchase orders matching your filter criteria."
          filtered={list.active}
        />
      </Card>
    </>
  );
}
