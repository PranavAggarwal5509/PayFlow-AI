import type { FieldEvidence, LineItemEvidence, VisualEvidence } from "@/types/api";

/** One box to highlight on the PDF. */
export interface EvidenceItem {
  key: string;
  label: string;
  evidence: FieldEvidence;
}

export const FIELD_LABELS: Record<string, string> = {
  invoice_number: "Invoice number",
  invoice_date: "Invoice date",
  due_date: "Due date",
  vendor_name: "Vendor name",
  vendor_gstin: "Vendor GSTIN",
  purchase_order_number: "PO number",
  currency: "Currency",
  subtotal: "Taxable value",
  tax_amount: "GST",
  total_amount: "Invoice total",
  bank_account_details: "Bank account",
  bank_account_number: "Account number",
  bank_ifsc: "IFSC",
};

const located = (ev: unknown): ev is FieldEvidence =>
  !!ev && typeof ev === "object" && "norm_bbox" in ev && !!(ev as FieldEvidence).norm_bbox && (ev as FieldEvidence).evidence_status !== "NOT_FOUND";

/** Evidence for a header field, or null when the value was not found on the page. */
export function fieldEvidence(ve: VisualEvidence | null | undefined, key: string): EvidenceItem | null {
  const ev = ve?.[key];
  return located(ev) ? { key, label: FIELD_LABELS[key] ?? key.replace(/_/g, " "), evidence: ev } : null;
}

export type LinePart = "row" | "description" | "quantity" | "unit_price" | "total_amount";
const PART_LABELS: Record<LinePart, string> = {
  row: "",
  description: "description",
  quantity: "quantity",
  unit_price: "rate",
  total_amount: "amount",
};

/** Evidence for one line item (whole row or a single cell). */
export function lineEvidence(ve: VisualEvidence | null | undefined, index: number, part: LinePart, name?: string | null): EvidenceItem | null {
  const lines = ve?.line_items as LineItemEvidence[] | undefined;
  const line = lines?.find((l) => l.line_index === index);
  const ev = line?.[part as keyof LineItemEvidence];
  if (!located(ev)) return null;
  const base = `Line ${index + 1}${name ? ` · ${name}` : ""}`;
  return { key: `line_${index}_${part}`, label: part === "row" ? base : `Line ${index + 1} ${PART_LABELS[part]}`, evidence: ev };
}

function allLineRows(ve: VisualEvidence | null | undefined): EvidenceItem[] {
  const lines = (ve?.line_items as LineItemEvidence[] | undefined) ?? [];
  return lines.map((l) => lineEvidence(ve, l.line_index, "row")).filter((x): x is EvidenceItem => !!x);
}

/** Which printed values each control looked at. "lines" = every line-item row. */
const CHECK_FIELDS: Record<string, string[]> = {
  REQUIRED_FIELDS: ["invoice_number", "invoice_date", "vendor_name", "total_amount"],
  INVOICE_DATE: ["invoice_date", "due_date"],
  CURRENCY_SUPPORTED: ["currency", "total_amount"],
  AMOUNTS_VALID: ["subtotal", "tax_amount", "total_amount"],
  LINE_ITEMS_VALID: ["lines"],
  TOTAL_ARITHMETIC: ["subtotal", "tax_amount", "total_amount"],
  LINE_ITEM_MATH: ["lines"],
  LINE_ITEMS_SUM: ["lines", "subtotal"],
  TAX_RATES: ["lines", "tax_amount"],
  APPROVAL_LIMIT: ["total_amount"],
  VENDOR_MATCH: ["vendor_name", "vendor_gstin"],
  VENDOR_STATUS: ["vendor_name"],
  VENDOR_GSTIN: ["vendor_gstin"],
  VENDOR_BANK: ["bank_account_details"],
  PO_EXISTS: ["purchase_order_number"],
  PO_VENDOR: ["purchase_order_number", "vendor_name"],
  PO_STATUS: ["purchase_order_number"],
  PO_CURRENCY: ["purchase_order_number", "currency"],
  PO_BALANCE: ["purchase_order_number", "total_amount"],
  PO_LINE_ITEMS: ["lines"],
  DUP_BUSINESS: ["invoice_number", "vendor_name"],
  DUP_POTENTIAL: ["invoice_number", "invoice_date", "total_amount"],
};

/** Boxes for a validation check (by code) or a single field (by key). */
export function evidenceFor(ve: VisualEvidence | null | undefined, codeOrKey: string): EvidenceItem[] {
  const keys = CHECK_FIELDS[codeOrKey] ?? [codeOrKey];
  return keys.flatMap((k) => (k === "lines" ? allLineRows(ve) : [fieldEvidence(ve, k)].filter((x): x is EvidenceItem => !!x)));
}

/** Whether a check maps to printed values at all (file hash / extraction checks do not). */
export const checkHasEvidence = (code: string) => code in CHECK_FIELDS;

/** Every located box on the document (for the "Show all" overlay). */
export function allEvidence(ve: VisualEvidence | null | undefined): EvidenceItem[] {
  if (!ve) return [];
  const header = Object.keys(ve)
    .filter((k) => k !== "line_items" && k !== "bank_account_number" && k !== "bank_ifsc")
    .map((k) => fieldEvidence(ve, k))
    .filter((x): x is EvidenceItem => !!x);
  return [...header, ...allLineRows(ve)];
}
