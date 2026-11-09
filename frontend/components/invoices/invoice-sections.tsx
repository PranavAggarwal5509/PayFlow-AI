import Link from "next/link";
import { Eye } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { fieldEvidence, lineEvidence, type EvidenceItem } from "@/lib/evidence";
import { formatDate, formatDateTime, formatMoney, titleCase } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { InvoiceDetail } from "@/types/api";

/** Called with the boxes to highlight on the PDF. */
export type ShowEvidence = (items: EvidenceItem[]) => void;

interface EvidenceProps {
  /** Keys currently highlighted on the PDF (to mark the matching value as selected). */
  activeKeys?: Set<string>;
  onShow?: ShowEvidence;
}

/** A value that can be clicked to highlight where it is printed on the PDF. */
export function EvidenceValue({
  item,
  activeKeys,
  onShow,
  children,
  className,
  align = "left",
}: EvidenceProps & { item: EvidenceItem | null; children: ReactNode; className?: string; align?: "left" | "right" }) {
  if (!item || !onShow) return <span className={className}>{children}</span>;
  const on = activeKeys?.has(item.key);
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onShow([item]);
      }}
      title={`Show ${item.label.toLowerCase()} on the PDF`}
      aria-pressed={on}
      className={cn(
        "group/ev -mx-1 inline-flex max-w-full items-center gap-1 rounded px-1 text-left transition-colors",
        align === "right" && "flex-row-reverse text-right",
        on ? "bg-amber-100 text-slate-900 ring-1 ring-amber-300" : "hover:bg-indigo-50 hover:text-indigo-800",
        className,
      )}
    >
      <span className="min-w-0 break-words">{children}</span>
      <Eye className={cn("h-3 w-3 shrink-0 transition-opacity", on ? "text-amber-600 opacity-100" : "text-indigo-500 opacity-0 group-hover/ev:opacity-100")} />
    </button>
  );
}

export function Field({
  label,
  children,
  item = null,
  activeKeys,
  onShow,
}: EvidenceProps & { label: string; children: ReactNode; item?: EvidenceItem | null }) {
  return (
    <div>
      <dt className="flex items-center gap-1.5 text-xs text-muted-foreground">
        {label}
        {item && onShow && <span className="text-[10px] font-medium text-indigo-500">· in PDF</span>}
      </dt>
      <dd className="mt-0.5 text-sm font-medium">
        {children ? (
          <EvidenceValue item={item} activeKeys={activeKeys} onShow={onShow}>
            {children}
          </EvidenceValue>
        ) : (
          <span className="text-slate-400">—</span>
        )}
      </dd>
    </div>
  );
}

const EXTRA_EVIDENCE: Record<string, string> = { bank_account_details: "bank_account_details" };

export function InvoiceInfoCard({ invoice, activeKeys, onShow }: EvidenceProps & { invoice: InvoiceDetail }) {
  const ve = invoice.visual_evidence;
  const ev = (key: string) => fieldEvidence(ve, key);
  const p = { activeKeys, onShow };
  return (
    <Card>
      <CardHeader
        title="Invoice information"
        description={`Extracted using ${invoice.extraction_method === "OCR" ? "OCR" : "PDF text"} · ${invoice.page_count ?? "?"} page(s) · click a value to see it on the PDF`}
      />
      <CardBody>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-4">
          <Field label="Invoice number" item={ev("invoice_number")} {...p}>
            {invoice.invoice_number}
          </Field>
          <Field label="Invoice date" item={ev("invoice_date")} {...p}>
            {formatDate(invoice.invoice_date)}
          </Field>
          <Field label="Due date" item={ev("due_date")} {...p}>
            {formatDate(invoice.due_date)}
          </Field>
          <Field label="Currency" item={ev("currency")} {...p}>
            {invoice.currency}
          </Field>
          <Field label="PO number (on invoice)" item={ev("purchase_order_number")} {...p}>
            {invoice.po_number}
          </Field>
          <Field label="Uploaded">
            {formatDateTime(invoice.uploaded_at)} by {invoice.uploaded_by}
          </Field>
          {Object.entries(invoice.extra).map(([key, value]) => (
            <Field key={key} label={titleCase(key)} item={EXTRA_EVIDENCE[key] ? ev(EXTRA_EVIDENCE[key]) : null} {...p}>
              {Array.isArray(value) ? value.join(", ") : value}
            </Field>
          ))}
        </dl>
      </CardBody>
    </Card>
  );
}

export function VendorCard({ invoice, activeKeys, onShow }: EvidenceProps & { invoice: InvoiceDetail }) {
  const vendor = invoice.vendor;
  const ve = invoice.visual_evidence;
  const p = { activeKeys, onShow };
  return (
    <Card>
      <CardHeader title="Vendor" description={vendor ? "Matched to the vendor register" : "Not confirmed in the vendor register"} />
      <CardBody>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-4">
          <Field label="Name on invoice" item={fieldEvidence(ve, "vendor_name")} {...p}>
            {invoice.vendor_name_raw}
          </Field>
          <Field label="GSTIN on invoice" item={fieldEvidence(ve, "vendor_gstin")} {...p}>
            {invoice.vendor_gstin_raw}
          </Field>
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

export function LineItemsCard({ invoice, activeKeys, onShow }: EvidenceProps & { invoice: InvoiceDetail }) {
  const items = invoice.line_items;
  const ve = invoice.visual_evidence;
  const p = { activeKeys, onShow };
  return (
    <Card>
      <CardHeader
        title="Line items & PO reconciliation"
        description={`${items.length} item(s) · click a row or a number to see it on the PDF`}
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
                const row = lineEvidence(ve, i, "row", item.description);
                const rowOn = !!row && activeKeys?.has(row.key);
                const statusColor =
                  recon?.status === "MATCHED"
                    ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                    : recon?.status === "MATCHED_WITH_VARIANCE"
                      ? "bg-amber-50 text-amber-700 border-amber-200"
                      : "bg-rose-50 text-rose-700 border-rose-200";
                return (
                  <tr
                    key={i}
                    onClick={row && onShow ? () => onShow([row]) : undefined}
                    title={row ? "Show this line on the PDF" : undefined}
                    className={cn(row && onShow && "cursor-pointer", rowOn ? "bg-amber-50" : "hover:bg-slate-50/70")}
                  >
                    <td className="px-5 py-2.5">
                      <div className="flex items-center gap-1.5 font-medium text-slate-900">
                        {item.description ?? "—"}
                        {row && <Eye className={cn("h-3 w-3 shrink-0", rowOn ? "text-amber-600" : "text-indigo-400")} />}
                      </div>
                      {recon?.explanation && <div className="mt-0.5 max-w-[280px] text-[11px] text-slate-500">{recon.explanation}</div>}
                    </td>
                    <td className="tabular px-3 py-2.5 text-right font-medium">
                      <EvidenceValue item={lineEvidence(ve, i, "quantity")} align="right" {...p}>
                        {item.quantity ? Number(item.quantity) : "—"}
                      </EvidenceValue>
                    </td>
                    <td className="tabular px-3 py-2.5 text-right text-slate-600">
                      <EvidenceValue item={lineEvidence(ve, i, "unit_price")} align="right" {...p}>
                        {formatMoney(item.unit_price, invoice.currency)}
                      </EvidenceValue>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-slate-700">
                      {recon?.matched_description ? (
                        <div>
                          <span className="font-medium text-slate-900">{recon.matched_description}</span>
                          <span className="ml-1 text-[10px] text-slate-400">({recon.matching_method})</span>
                        </div>
                      ) : (
                        <span className="italic text-slate-400">No PO match</span>
                      )}
                    </td>
                    <td className="tabular px-3 py-2.5 text-right text-slate-600">
                      {recon?.po_unit_price ? formatMoney(recon.po_unit_price, invoice.currency) : "—"}
                    </td>
                    <td className="tabular px-3 py-2.5 text-right text-xs">
                      {recon?.price_variance != null && Number(recon.price_variance) !== 0 ? (
                        <span className="font-medium text-amber-700">{formatMoney(recon.price_variance, invoice.currency)}</span>
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
                        <span className="text-xs text-slate-400">—</span>
                      )}
                    </td>
                    <td className="tabular px-5 py-2.5 text-right font-semibold text-slate-900">
                      <EvidenceValue item={lineEvidence(ve, i, "total_amount")} align="right" {...p}>
                        {formatMoney(item.total_amount, invoice.currency)}
                      </EvidenceValue>
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

export function FinancialSummaryCard({ invoice, activeKeys, onShow }: EvidenceProps & { invoice: InvoiceDetail }) {
  const ve = invoice.visual_evidence;
  const p = { activeKeys, onShow };
  const rows: { label: string; key: string; value: string; strong?: boolean }[] = [
    { label: "Taxable value (subtotal)", key: "subtotal", value: formatMoney(invoice.subtotal, invoice.currency) },
    { label: "GST", key: "tax_amount", value: formatMoney(invoice.tax_amount, invoice.currency) },
    { label: "Invoice total", key: "total_amount", value: formatMoney(invoice.total_amount, invoice.currency), strong: true },
  ];
  return (
    <Card>
      <CardHeader title="Financial summary" description="Values exactly as extracted — click one to see it on the PDF" />
      <CardBody className="space-y-2 text-sm">
        {rows.map((row) => (
          <div key={row.key} className={cn("flex items-center justify-between", row.strong && "border-t pt-2")}>
            <span className="text-muted-foreground">{row.label}</span>
            <EvidenceValue item={fieldEvidence(ve, row.key)} align="right" className={cn("tabular", row.strong ? "text-base font-semibold" : "font-medium")} {...p}>
              {row.value}
            </EvidenceValue>
          </div>
        ))}
      </CardBody>
    </Card>
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

