"use client";

import { Pencil } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { useInvoiceColumns } from "@/components/invoices/invoice-columns";
import { Field } from "@/components/invoices/invoice-sections";
import { PageHeader } from "@/components/layout/page-header";
import { DataTable } from "@/components/tables/data-table";
import { ErrorState } from "@/components/tables/table-states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Can } from "@/components/auth/auth-provider";
import { VendorDialog } from "@/components/vendors/vendor-dialog";
import { useAsync } from "@/hooks/use-async";
import { formatDate, formatMoney, titleCase } from "@/lib/format";
import { invoiceService, purchaseOrderService, vendorService } from "@/services";

export default function VendorDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const vendor = useAsync(() => vendorService.get(id), [id]);
  const invoices = useAsync(() => invoiceService.list({ vendor_id: id, page_size: 10 }), [id]);
  const pos = useAsync(() => purchaseOrderService.list({ vendor_id: id, page_size: 10 }), [id]);
  const columns = useInvoiceColumns();
  const [editing, setEditing] = useState(false);

  if (vendor.error) return <ErrorState message={vendor.error} onRetry={vendor.reload} />;
  if (!vendor.data) return <Skeleton className="h-64" />;
  const v = vendor.data;

  return (
    <>
      <PageHeader
        title={v.vendor_name}
        description={`${v.vendor_code} · added ${formatDate(v.created_at)}`}
        actions={
          <Can permission="masterdata:edit">
            <Button variant="outline" onClick={() => setEditing(true)}>
              <Pencil className="h-4 w-4" /> Edit vendor
            </Button>
          </Can>
        }
      />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader title="Vendor details" />
          <CardBody>
            <dl className="space-y-4">
              <Field label="Status">
                <Badge tone={v.status === "ACTIVE" ? "success" : v.status === "INACTIVE" ? "danger" : "warning"}>{titleCase(v.status)}</Badge>
              </Field>
              <Field label="GSTIN">{v.gstin}</Field>
              <Field label="Address">{v.address}</Field>
              <Field label="Email">{v.email}</Field>
              <Field label="Phone">{v.phone}</Field>
              <Field label="Invoices">{String(v.invoice_count)}</Field>
              <Field label="Total invoice value">{formatMoney(v.total_invoice_value, "INR")}</Field>
            </dl>
            {v.is_demo && <p className="mt-4 text-xs text-muted-foreground">Synthetic demo vendor.</p>}
          </CardBody>
        </Card>
        <div className="space-y-4 lg:col-span-2">
          <Card>
            <CardHeader title="Purchase orders" />
            <CardBody className="divide-y p-0">
              {(pos.data?.items ?? []).length === 0 ? (
                <p className="p-5 text-sm text-muted-foreground">No purchase orders.</p>
              ) : (
                pos.data?.items.map((po) => (
                  <Link key={po.id} href={`/purchase-orders/${po.id}`} className="flex items-center justify-between px-5 py-3 text-sm hover:bg-slate-50">
                    <span className="font-medium">{po.po_number}</span>
                    <span className="tabular text-muted-foreground">Remaining {formatMoney(po.remaining_balance, po.currency)}</span>
                    <Badge tone={po.status === "ACTIVE" ? "success" : "neutral"}>{titleCase(po.status)}</Badge>
                  </Link>
                ))
              )}
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Invoices" />
            <DataTable
              columns={columns}
              data={invoices.data?.items ?? []}
              loading={invoices.loading}
              error={invoices.error}
              onRetry={invoices.reload}
              onRowClick={(row) => router.push(`/invoices/${row.id}`)}
              emptyTitle="No invoices from this vendor"
            />
          </Card>
        </div>
      </div>
      <VendorDialog open={editing} vendor={v} onOpenChange={setEditing} onSaved={vendor.reload} />
    </>
  );
}

