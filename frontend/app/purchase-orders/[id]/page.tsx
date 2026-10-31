"use client";

import { ArrowLeft, Building2, Calendar, CheckCircle2, DollarSign, FileText, ShoppingCart } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { DecisionBadge } from "@/components/invoices/status-badges";
import { PageHeader } from "@/components/layout/page-header";
import { ErrorState } from "@/components/tables/table-states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAsync } from "@/hooks/use-async";
import { formatDate, formatMoney, titleCase } from "@/lib/format";
import { poTone } from "@/lib/status";
import { purchaseOrderService } from "@/services";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 break-words text-sm font-medium">
        {children || <span className="text-slate-400">—</span>}
      </dd>
    </div>
  );
}

export default function PurchaseOrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const po = useAsync(() => purchaseOrderService.get(id), [id]);

  if (po.error) return <ErrorState message={po.error} onRetry={po.reload} />;
  if (!po.data) return <Skeleton className="h-64" />;

  const p = po.data;
  const consumed = Number(p.consumed_amount);
  const total = Number(p.total_amount);
  const remaining = Number(p.remaining_balance);
  const percentConsumed = total > 0 ? Math.min(100, Math.round((consumed / total) * 100)) : 0;

  return (
    <>
      <div className="mb-4">
        <Link
          href="/purchase-orders"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-foreground"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Back to Purchase Orders
        </Link>
      </div>

      <PageHeader
        title={`Purchase Order: ${p.po_number}`}
        description={`Issued to ${p.vendor_name} on ${formatDate(p.po_date)}`}
        actions={
          <Badge tone={poTone(p.status)} className="text-sm px-3 py-1">
            {titleCase(p.status)}
          </Badge>
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Left Column: PO Overview & Vendor info */}
        <div className="space-y-4 lg:col-span-1">
          <Card>
            <CardHeader title="Overview" />
            <CardBody>
              <dl className="space-y-4">
                <Field label="PO Number">{p.po_number}</Field>
                <Field label="Vendor">
                  <Link
                    href={`/vendors/${p.vendor_id}`}
                    className="font-medium text-primary hover:underline"
                  >
                    {p.vendor_name}
                  </Link>
                </Field>
                <Field label="PO Date">{formatDate(p.po_date)}</Field>
                <Field label="Currency">{p.currency}</Field>
                <Field label="Status">
                  <Badge tone={poTone(p.status)}>{titleCase(p.status)}</Badge>
                </Field>
                {p.description && <Field label="Description">{p.description}</Field>}
              </dl>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Budget & Balance" />
            <CardBody>
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between text-xs font-medium mb-1.5">
                    <span className="text-muted-foreground">Allocation Progress</span>
                    <span>{percentConsumed}%</span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                    <div
                      className={`h-full ${
                        percentConsumed >= 100
                          ? "bg-amber-500"
                          : percentConsumed > 80
                          ? "bg-blue-500"
                          : "bg-emerald-500"
                      }`}
                      style={{ width: `${percentConsumed}%` }}
                    />
                  </div>
                </div>

                <dl className="space-y-3 pt-2 border-t">
                  <div className="flex justify-between items-center text-sm">
                    <dt className="text-muted-foreground">Total Budget:</dt>
                    <dd className="font-semibold">{formatMoney(p.total_amount, p.currency)}</dd>
                  </div>
                  <div className="flex justify-between items-center text-sm">
                    <dt className="text-muted-foreground">Consumed Amount:</dt>
                    <dd className="font-semibold text-slate-700">
                      {formatMoney(p.consumed_amount, p.currency)}
                    </dd>
                  </div>
                  <div className="flex justify-between items-center text-sm pt-2 border-t">
                    <dt className="text-muted-foreground font-medium">Remaining Balance:</dt>
                    <dd
                      className={`font-bold ${
                        remaining <= 0 ? "text-amber-600" : "text-emerald-700"
                      }`}
                    >
                      {formatMoney(p.remaining_balance, p.currency)}
                    </dd>
                  </div>
                </dl>
              </div>
            </CardBody>
          </Card>
        </div>

        {/* Right Column: Line Items & Linked Invoices */}
        <div className="space-y-4 lg:col-span-2">
          {/* Line Items Table */}
          <Card>
            <CardHeader
              title="Line Items"
              description={`${p.items.length} line item(s) ordered`}
            />
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 border-y text-xs uppercase tracking-wider text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2.5 font-semibold">Description</th>
                    <th className="px-4 py-2.5 font-semibold text-right">Quantity</th>
                    <th className="px-4 py-2.5 font-semibold text-right">Unit Price</th>
                    <th className="px-4 py-2.5 font-semibold text-right">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {p.items.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="px-4 py-6 text-center text-muted-foreground">
                        No line items listed for this purchase order.
                      </td>
                    </tr>
                  ) : (
                    p.items.map((item) => (
                      <tr key={item.id} className="hover:bg-slate-50/50">
                        <td className="px-4 py-3 font-medium">{item.description}</td>
                        <td className="px-4 py-3 text-right tabular text-muted-foreground">
                          {item.quantity}
                        </td>
                        <td className="px-4 py-3 text-right tabular text-muted-foreground">
                          {formatMoney(item.unit_price, p.currency)}
                        </td>
                        <td className="px-4 py-3 text-right tabular font-semibold">
                          {formatMoney(item.total_amount, p.currency)}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Linked Invoices & Allocation History */}
          <Card>
            <CardHeader
              title="Linked Invoices & Allocation History"
              description="Invoices matched against this purchase order"
            />
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 border-y text-xs uppercase tracking-wider text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2.5 font-semibold">Invoice Number</th>
                    <th className="px-4 py-2.5 font-semibold">Decision</th>
                    <th className="px-4 py-2.5 font-semibold">Allocation</th>
                    <th className="px-4 py-2.5 font-semibold text-right">Total Amount</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {p.invoices.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="px-4 py-6 text-center text-muted-foreground">
                        No invoices linked to this purchase order yet.
                      </td>
                    </tr>
                  ) : (
                    p.invoices.map((inv) => (
                      <tr key={inv.id} className="hover:bg-slate-50/50">
                        <td className="px-4 py-3 font-medium">
                          <Link
                            href={`/invoices/${inv.id}`}
                            className="font-mono text-primary hover:underline"
                          >
                            {inv.invoice_number || "Untitled Invoice"}
                          </Link>
                        </td>
                        <td className="px-4 py-3">
                          <DecisionBadge status={inv.decision_status} />
                        </td>
                        <td className="px-4 py-3">
                          {inv.allocated ? (
                            <Badge tone="success" className="gap-1">
                              <CheckCircle2 className="h-3 w-3" /> Committed
                            </Badge>
                          ) : (
                            <Badge tone="neutral">Unallocated</Badge>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right tabular font-semibold">
                          {formatMoney(inv.total_amount, inv.currency || p.currency)}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      </div>
    </>
  );
}
