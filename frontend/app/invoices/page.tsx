"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { useInvoiceColumns } from "@/components/invoices/invoice-columns";
import {
  EMPTY_INVOICE_FILTERS,
  InvoiceFilters,
  type InvoiceFilterValues,
} from "@/components/invoices/invoice-filters";
import { PageHeader } from "@/components/layout/page-header";
import { DataTable } from "@/components/tables/data-table";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useAsync } from "@/hooks/use-async";
import { useDebounce } from "@/hooks/use-debounce";
import { useListState } from "@/hooks/use-list-state";
import { invoiceService, vendorService } from "@/services";

function InvoicesContent() {
  const router = useRouter();
  const search = useSearchParams();
  const initial: InvoiceFilterValues = {
    ...EMPTY_INVOICE_FILTERS,
    q: search.get("q") ?? "",
    decision_status: search.get("decision_status") ?? "",
    processing_status: search.get("processing_status") ?? "",
  };
  const list = useListState<InvoiceFilterValues>(initial, [{ id: "uploaded_at", desc: true }]);
  const debouncedQuery = useDebounce(list.filters.q);
  const vendors = useAsync(() => vendorService.list({ page_size: 100 }), []);
  const columns = useInvoiceColumns({ sortable: true });

  const params = { ...list.filters, q: debouncedQuery, ...list.sortParams, page: list.page, page_size: 15 };
  const invoices = useAsync(
    () => invoiceService.list(params),
    [JSON.stringify(params)],
  );

  return (
    <>
      <PageHeader
        title="Invoices"
        description="Every uploaded invoice with its processing status and decision."
        actions={
          <Button asChild>
            <Link href="/upload">Upload invoice</Link>
          </Button>
        }
      />
      <Card>
        <InvoiceFilters
          values={list.filters}
          onChange={list.setFilter}
          onClear={list.clear}
          active={list.active}
          vendors={vendors.data?.items ?? []}
        />
        <DataTable
          columns={columns}
          data={invoices.data?.items ?? []}
          loading={invoices.loading}
          error={invoices.error}
          onRetry={invoices.reload}
          meta={invoices.data?.meta}
          onPageChange={list.setPage}
          sorting={list.sorting}
          onSortingChange={(s) => {
            list.setSorting(s);
            list.setPage(1);
          }}
          filtered={list.active}
          onRowClick={(row) =>
            router.push(
              row.processing_status === "PROCESSING" && row.latest_run_id
                ? `/processing/${row.latest_run_id}`
                : `/invoices/${row.id}`,
            )
          }
          emptyTitle="No invoices yet"
          emptyDescription="Upload a PDF invoice to start processing."
          emptyAction={
            <Button asChild size="sm">
              <Link href="/upload">Upload invoice</Link>
            </Button>
          }
        />
      </Card>
    </>
  );
}

export default function InvoicesPage() {
  return (
    <Suspense fallback={null}>
      <InvoicesContent />
    </Suspense>
  );
}

