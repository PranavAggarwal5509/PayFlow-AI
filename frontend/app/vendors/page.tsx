"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Pencil, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { PageHeader } from "@/components/layout/page-header";
import { DataTable } from "@/components/tables/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { VendorDialog } from "@/components/vendors/vendor-dialog";
import { useAsync } from "@/hooks/use-async";
import { useDebounce } from "@/hooks/use-debounce";
import { useListState } from "@/hooks/use-list-state";
import { formatMoney, titleCase } from "@/lib/format";
import { vendorService } from "@/services";
import type { Vendor } from "@/types/api";

const vendorTone = (status: string) => (status === "ACTIVE" ? "success" : status === "INACTIVE" ? "danger" : "warning");

export default function VendorsPage() {
  const router = useRouter();
  const list = useListState({ q: "", status: "" }, [{ id: "vendor_name", desc: false }]);
  const query = useDebounce(list.filters.q);
  const params = { ...list.filters, q: query, ...list.sortParams, page: list.page, page_size: 15 };
  const vendors = useAsync(() => vendorService.list(params), [JSON.stringify(params)]);
  const [dialog, setDialog] = useState<{ open: boolean; vendor: Vendor | null }>({ open: false, vendor: null });

  const columns = useMemo<ColumnDef<Vendor, unknown>[]>(
    () => [
      { id: "vendor_code", header: "Code", cell: ({ row }) => <span className="font-mono text-[13px]">{row.original.vendor_code}</span> },
      {
        id: "vendor_name",
        header: "Vendor",
        cell: ({ row }) => (
          <div>
            <p className="font-medium">{row.original.vendor_name}</p>
            <p className="text-xs text-muted-foreground">{row.original.email ?? ""}</p>
          </div>
        ),
      },
      { id: "gstin", header: "GSTIN", enableSorting: false, cell: ({ row }) => <span className="font-mono text-[13px]">{row.original.gstin ?? "—"}</span> },
      { id: "status", header: "Status", cell: ({ row }) => <Badge tone={vendorTone(row.original.status)}>{titleCase(row.original.status)}</Badge> },
      { id: "invoices", header: "Invoices", enableSorting: false, cell: ({ row }) => <span className="tabular">{row.original.invoice_count}</span> },
      {
        id: "value",
        header: "Total value",
        enableSorting: false,
        cell: ({ row }) => <span className="tabular font-medium">{formatMoney(row.original.total_invoice_value, "INR")}</span>,
      },
      {
        id: "actions",
        header: "",
        enableSorting: false,
        cell: ({ row }) => (
          <Button
            variant="ghost"
            size="icon"
            aria-label={`Edit ${row.original.vendor_name}`}
            onClick={(e) => {
              e.stopPropagation();
              setDialog({ open: true, vendor: row.original });
            }}
          >
            <Pencil className="h-4 w-4" />
          </Button>
        ),
      },
    ],
    [],
  );

  return (
    <>
      <PageHeader
        title="Vendors"
        description="The vendor register used for verification."
        actions={
          <Button onClick={() => setDialog({ open: true, vendor: null })}>
            <Plus className="h-4 w-4" /> Add vendor
          </Button>
        }
      />
      <Card>
        <div className="grid grid-cols-2 gap-3 border-b p-4 md:grid-cols-4">
          <Input className="col-span-2" value={list.filters.q} onChange={(e) => list.setFilter("q", e.target.value)} placeholder="Search name, code or GSTIN…" aria-label="Search vendors" />
          <Select value={list.filters.status} onChange={(e) => list.setFilter("status", e.target.value)} aria-label="Status">
            <option value="">All statuses</option>
            <option value="ACTIVE">Active</option>
            <option value="INACTIVE">Inactive</option>
            <option value="PENDING">Pending</option>
          </Select>
          {list.active && (
            <Button variant="ghost" onClick={list.clear}>
              Clear filters
            </Button>
          )}
        </div>
        <DataTable
          columns={columns}
          data={vendors.data?.items ?? []}
          loading={vendors.loading}
          error={vendors.error}
          onRetry={vendors.reload}
          meta={vendors.data?.meta}
          onPageChange={list.setPage}
          sorting={list.sorting}
          onSortingChange={(s) => {
            list.setSorting(s);
            list.setPage(1);
          }}
          filtered={list.active}
          onRowClick={(row) => router.push(`/vendors/${row.id}`)}
          emptyTitle="No vendors yet"
          emptyAction={<Button size="sm" onClick={() => setDialog({ open: true, vendor: null })}>Add vendor</Button>}
        />
      </Card>
      <VendorDialog open={dialog.open} vendor={dialog.vendor} onOpenChange={(open) => setDialog((d) => ({ ...d, open }))} onSaved={vendors.reload} />
    </>
  );
}

