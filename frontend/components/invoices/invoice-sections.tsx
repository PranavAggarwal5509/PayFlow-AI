import Link from "next/link";
import { Eye } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { formatDate, formatDateTime, formatMoney, titleCase } from "@/lib/format";
import type { FieldEvidence, InvoiceDetail } from "@/types/api";

export function Field({
  label,
  children,
  evidence,
  onSelectEvidence,
}: {
  label: string;
  children: ReactNode;
  evidence?: FieldEvidence | null;
  onSelectEvidence?: (label: string, ev: FieldEvidence) => void;
}) {
  const hasEvidence = !!evidence && evidence.evidence_status !== "NOT_FOUND";
  return (
    <div className="group relative">
      <div className="flex items-center justify-between">
        <dt className="text-xs text-muted-foreground">{label}</dt>
        {hasEvidence && onSelectEvidence && (
          <button
            type="button"
            onClick={() => onSelectEvidence(label, evidence)}
            className="flex items-center gap-1 text-[11px] font-medium text-blue-600 opacity-80 hover:text-blue-800 hover:opacity-100"
            title="Inspect visual evidence in original PDF"
          >
            <Eye className="h-3 w-3" /> View evidence
          </button>
        )}
      </div>
      <dd className="mt-0.5 break-words text-sm font-medium">{children || <span className="text-slate-400">—</span>}</dd>
    </div>
  );
}

export function InvoiceInfoCard({
  invoice,
  onSelectEvidence,
}: {
  invoice: InvoiceDetail;
  onSelectEvidence?: (label: string, ev: FieldEvidence) => void;
}) {
  const ev = (invoice.visual_evidence || {}) as Record<string, FieldEvidence>;
  return (
    <Card>
      <CardHeader title="Invoice information" description={`Extracted using ${invoice.extraction_method === "OCR" ? "OCR" : "PDF text"} · ${invoice.page_count ?? "?"} page(s)`} />
      <CardBody>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-4">
          <Field label="Invoice number" evidence={ev.invoice_number} onSelectEvidence={onSelectEvidence}>
            {invoice.invoice_number}
          </Field>
          <Field label="Invoice date" evidence={ev.invoice_date} onSelectEvidence={onSelectEvidence}>
            {formatDate(invoice.invoice_date)}
          </Field>
          <Field label="Due date" evidence={ev.due_date} onSelectEvidence={onSelectEvidence}>
            {formatDate(invoice.due_date)}
          </Field>
          <Field label="Currency" evidence={ev.currency} onSelectEvidence={onSelectEvidence}>
            {invoice.currency}
          </Field>
          <Field label="PO number (on invoice)" evidence={ev.purchase_order_number} onSelectEvidence={onSelectEvidence}>
            {invoice.po_number}
          </Field>
          <Field label="Uploaded">
            {formatDateTime(invoice.uploaded_at)} by {invoice.uploaded_by}
          </Field>
          {Object.entries(invoice.extra).map(([key, value]) => (
            <Field key={key} label={titleCase(key)}>
              {Array.isArray(value) ? value.join(", ") : value}
            </Field>
          ))}
        </dl>
      </CardBody>
    </Card>
  );
}

export function VendorCard({
  invoice,
  onSelectEvidence,
}: {
  invoice: InvoiceDetail;
  onSelectEvidence?: (label: string, ev: FieldEvidence) => void;
}) {
  const vendor = invoice.vendor;
  const ev = (invoice.visual_evidence || {}) as Record<string, FieldEvidence>;
  return (
    <Card>
      <CardHeader title="Vendor" description={vendor ? "Matched to the vendor register" : "Not confirmed in the vendor register"} />
      <CardBody>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-4">
          <Field label="Name on invoice" evidence={ev.vendor_name} onSelectEvidence={onSelectEvidence}>
            {invoice.vendor_name_raw}
          </Field>
          <Field label="GSTIN on invoice" evidence={ev.vendor_gstin} onSelectEvidence={onSelectEvidence}>
            {invoice.vendor_gstin_raw}
          </Field>
          <Field label="GSTIN on invoice">{invoice.vendor_gstin_raw}</Field>
          {vendor && (
            <>
              <Field label="Registered vendor">
                <Link href={`/vendors/${vendor.id}`} className="text-primary hover:underline">
                  {vendor.vendor_name}
                </Link>
              </Field>
              <Field label="Vendor code">{vendor.vendor_code}</Field>
              <Field label="Registered GSTIN">{vendor.gstin}</Field>
              <Field label="Status">
                <Badge tone={vendor.status === "ACTIVE" ? "success" : vendor.status === "INACTIVE" ? "danger" : "warning"}>{titleCase(vendor.status)}</Badge>
              </Field>
            </>
          )}
        </dl>
      </CardBody>
    </Card>
  );
}

export function PurchaseOrderCard({ invoice }: { invoice: InvoiceDetail }) {
  const po = invoice.purchase_order;
  return (
    <Card>
      <CardHeader title="Purchase order" description={po ? undefined : "No matching purchase order"} />
      <CardBody>
        {po ? (
          <dl className="grid grid-cols-2 gap-x-6 gap-y-4">
            <Field label="PO number">
              <Link href={`/purchase-orders/${po.id}`} className="text-primary hover:underline">
                {po.po_number}
              </Link>
            </Field>
            <Field label="Status">
              <Badge tone={po.status === "ACTIVE" ? "success" : "warning"}>{titleCase(po.status)}</Badge>
            </Field>
            <Field label="PO amount">{formatMoney(po.total_amount, po.currency)}</Field>
            <Field label="Approved & consumed">{formatMoney(po.consumed_amount, po.currency)}</Field>
            <Field label="Remaining balance">{formatMoney(po.remaining_balance, po.currency)}</Field>
            <Field label="PO vendor">{po.vendor_name}</Field>
          </dl>
        ) : (
          <p className="text-sm text-muted-foreground">
            {invoice.po_number ? `PO ${invoice.po_number} was not found.` : "The invoice does not reference a purchase order."}
          </p>
        )}
      </CardBody>
    </Card>
  );
}

export function LineItemsCard({ invoice }: { invoice: InvoiceDetail }) {
  const items = invoice.line_items;
  return (
    <Card>
      <CardHeader
        title="Line items & PO reconciliation"
        description={`${items.length} item(s) · Granular 3-way matching and PO quantity checks`}
      />
      {items.length === 0 ? (
        <p className="p-5 text-sm text-muted-foreground">No line items were extracted.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-slate-50/70 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-5 py-2 font-medium">Invoice item</th>
                <th className="px-3 py-2 text-right font-medium">Inv qty</th>
                <th className="px-3 py-2 text-right font-medium">Inv price</th>
                <th className="px-4 py-2 font-medium">Matched PO line</th>
                <th className="px-3 py-2 text-right font-medium">PO price</th>
                <th className="px-3 py-2 text-right font-medium">Variance</th>
                <th className="px-3 py-2 text-right font-medium">PO rem qty</th>
                <th className="px-3 py-2 text-center font-medium">Status</th>
                <th className="px-5 py-2 text-right font-medium">Total</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {items.map((item, i) => {
                const recon = item.reconciliation;
                const statusColor =
                  recon?.status === "MATCHED"
                    ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                    : recon?.status === "MATCHED_WITH_VARIANCE"
                    ? "bg-amber-50 text-amber-700 border-amber-200"
                    : "bg-rose-50 text-rose-700 border-rose-200";

                return (
                  <tr key={i} className="hover:bg-slate-50/50">
                    <td className="px-5 py-2.5">
                      <div className="font-medium text-slate-900">{item.description ?? "—"}</div>
                      {recon?.explanation && (
                        <div className="text-[11px] text-slate-500 mt-0.5 max-w-[280px]">
                          {recon.explanation}
                        </div>
                      )}
                    </td>
                    <td className="tabular px-3 py-2.5 text-right font-medium">
                      {item.quantity ? Number(item.quantity) : "—"}
                    </td>
                    <td className="tabular px-3 py-2.5 text-right text-slate-600">
                      {formatMoney(item.unit_price, invoice.currency)}
                    </td>
                    <td className="px-4 py-2.5 text-xs text-slate-700">
                      {recon?.matched_description ? (
                        <div>
                          <span className="font-medium text-slate-900">{recon.matched_description}</span>
                          <span className="ml-1 text-[10px] text-slate-400">({recon.matching_method})</span>
                        </div>
                      ) : (
                        <span className="text-slate-400 italic">No PO match</span>
                      )}
                    </td>
                    <td className="tabular px-3 py-2.5 text-right text-slate-600">
                      {recon?.po_unit_price ? formatMoney(recon.po_unit_price, invoice.currency) : "—"}
                    </td>
                    <td className="tabular px-3 py-2.5 text-right text-xs">
                      {recon?.price_variance != null && Number(recon.price_variance) !== 0 ? (
                        <span className="font-medium text-amber-700">
                          {formatMoney(recon.price_variance, invoice.currency)}
                        </span>
                      ) : (
                        <span className="text-slate-400">0.00</span>
                      )}
                    </td>
                    <td className="tabular px-3 py-2.5 text-right font-medium text-slate-700">
                      {recon?.remaining_quantity != null ? Number(recon.remaining_quantity) : "—"}
                    </td>
                    <td className="px-3 py-2.5 text-center">
                      {recon?.status ? (
                        <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${statusColor}`}>
                          {recon.status.replace(/_/g, " ")}
                        </span>
                      ) : (
                        <span className="text-slate-400 text-xs">—</span>
                      )}
                    </td>
                    <td className="tabular px-5 py-2.5 text-right font-semibold text-slate-900">
                      {formatMoney(item.total_amount, invoice.currency)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

export function FinancialSummaryCard({
  invoice,
  onSelectEvidence,
}: {
  invoice: InvoiceDetail;
  onSelectEvidence?: (label: string, ev: FieldEvidence) => void;
}) {
  const ev = (invoice.visual_evidence || {}) as Record<string, FieldEvidence>;
  return (
    <Card>
      <CardHeader title="Financial summary" description="Values exactly as extracted — click to view document evidence" />
      <CardBody className="space-y-2 text-sm">
        <SummaryRow
          label="Subtotal"
          value={formatMoney(invoice.subtotal, invoice.currency)}
          evidence={ev.subtotal}
          onSelectEvidence={onSelectEvidence}
        />
        <SummaryRow
          label="Tax"
          value={formatMoney(invoice.tax_amount, invoice.currency)}
          evidence={ev.tax_amount}
          onSelectEvidence={onSelectEvidence}
        />
        <div className="border-t pt-2">
          <SummaryRow
            label="Total"
            value={formatMoney(invoice.total_amount, invoice.currency)}
            strong
            evidence={ev.total_amount}
            onSelectEvidence={onSelectEvidence}
          />
        </div>
      </CardBody>
    </Card>
  );
}

function SummaryRow({
  label,
  value,
  strong,
  evidence,
  onSelectEvidence,
}: {
  label: string;
  value: string;
  strong?: boolean;
  evidence?: FieldEvidence | null;
  onSelectEvidence?: (label: string, ev: FieldEvidence) => void;
}) {
  const hasEvidence = !!evidence && evidence.evidence_status !== "NOT_FOUND";
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span className="text-muted-foreground">{label}</span>
        {hasEvidence && onSelectEvidence && (
          <button
            type="button"
            onClick={() => onSelectEvidence(label, evidence)}
            className="flex items-center gap-0.5 text-[10px] font-medium text-blue-600 hover:text-blue-800"
            title="Inspect visual evidence"
          >
            <Eye className="h-2.5 w-2.5" /> View
          </button>
        )}
      </div>
      <span className={`tabular ${strong ? "text-base font-semibold" : "font-medium"}`}>{value}</span>
    </div>
  );
}

const ACTION_LABELS: Record<string, string> = {
  INVOICE_UPLOADED: "Invoice uploaded",
  RUN_CREATED: "Processing run created",
  RUN_STARTED: "Workflow started",
  AI_EXTRACTION: "AI extraction",
  DECISION: "Decision made",
  RUN_COMPLETED: "Run completed",
  RUN_FAILED: "Run failed",
  RUN_RETRY: "Retry requested",
  REVIEW_APPROVE: "Manually approved",
  REVIEW_REJECT: "Manually rejected",
  REVIEW_REQUEST_CLARIFICATION: "Clarification requested",
  NOTIFICATION_DRAFTED: "Notification drafted",
};

export function HistoryCard({ invoice }: { invoice: InvoiceDetail }) {
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader title="Processing runs" />
        <CardBody className="divide-y p-0">
          {invoice.runs.map((run) => (
            <Link key={run.id} href={`/processing/${run.id}`} className="flex items-center justify-between px-5 py-3 text-sm hover:bg-slate-50">
              <span className="font-medium">Run #{run.run_number}</span>
              <span className="text-muted-foreground">{formatDateTime(run.started_at)}</span>
              <Badge tone={run.status === "FAILED" ? "danger" : run.status === "COMPLETED" ? "success" : "info"}>{titleCase(run.status)}</Badge>
            </Link>
          ))}
        </CardBody>
      </Card>
      <Card>
        <CardHeader title="Audit trail" description="Append-only history of everything that happened to this invoice" />
        <CardBody className="space-y-4">
          {invoice.audit_trail.map((entry) => (
            <div key={entry.id} className="flex gap-3 text-sm">
              <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-slate-300" />
              <div className="min-w-0">
                <p className="font-medium">{ACTION_LABELS[entry.action] ?? titleCase(entry.action)}</p>
                {entry.description && <p className="break-words text-[13px] text-slate-600">{entry.description}</p>}
                <p className="text-xs text-muted-foreground">
                  {entry.actor_id ?? entry.actor_type} · {formatDateTime(entry.created_at)}
                  {entry.old_value && entry.new_value && entry.action.startsWith("REVIEW") && ` · ${titleCase(entry.old_value)} → ${titleCase(entry.new_value)}`}
                </p>
              </div>
            </div>
          ))}
        </CardBody>
      </Card>
    </div>
  );
}

