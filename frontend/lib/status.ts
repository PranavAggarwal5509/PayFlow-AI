import type { CheckStatus, DecisionStatus, ProcessingStatus, ReviewStatus, RunStatus, StageStatus } from "@/types/api";

export type Tone = "success" | "warning" | "danger" | "info" | "neutral";

export const DECISION_META: Record<DecisionStatus, { label: string; tone: Tone }> = {
  APPROVED: { label: "Approved", tone: "success" },
  NEEDS_REVIEW: { label: "Needs review", tone: "warning" },
  REJECTED: { label: "Rejected", tone: "danger" },
};

export const PROCESSING_META: Record<ProcessingStatus | RunStatus, { label: string; tone: Tone }> = {
  PROCESSING: { label: "Processing", tone: "info" },
  COMPLETED: { label: "Completed", tone: "neutral" },
  FAILED: { label: "Processing failed", tone: "danger" },
  QUEUED: { label: "Queued", tone: "neutral" },
  RUNNING: { label: "Running", tone: "info" },
};

export const REVIEW_META: Record<ReviewStatus, { label: string; tone: Tone }> = {
  PENDING: { label: "Pending", tone: "warning" },
  CLARIFICATION_REQUESTED: { label: "Awaiting clarification", tone: "info" },
  APPROVED: { label: "Approved", tone: "success" },
  REJECTED: { label: "Rejected", tone: "danger" },
};

export const CHECK_META: Record<CheckStatus, { label: string; tone: Tone }> = {
  PASSED: { label: "Passed", tone: "success" },
  WARNING: { label: "Needs attention", tone: "warning" },
  FAILED: { label: "Failed", tone: "danger" },
  SKIPPED: { label: "Not checked", tone: "neutral" },
};

export const STAGE_STATUS_META: Record<StageStatus | "WAITING", { label: string; tone: Tone }> = {
  WAITING: { label: "Waiting", tone: "neutral" },
  IN_PROGRESS: { label: "In progress", tone: "info" },
  COMPLETED: { label: "Completed", tone: "success" },
  FAILED: { label: "Failed", tone: "danger" },
  NEEDS_ATTENTION: { label: "Needs attention", tone: "warning" },
};

/** Tracker stages shown to users. FINANCIAL_VALIDATION is folded into "Data validation". */
export const TRACKER_STAGES: { key: string; label: string; backend: string[] }[] = [
  { key: "UPLOAD_RECEIVED", label: "Upload received", backend: ["UPLOAD_RECEIVED"] },
  { key: "DOCUMENT_EXTRACTION", label: "Document extraction", backend: ["DOCUMENT_EXTRACTION"] },
  { key: "AI_EXTRACTION", label: "AI extraction", backend: ["AI_EXTRACTION"] },
  { key: "DATA_VALIDATION", label: "Data validation", backend: ["DATA_VALIDATION", "FINANCIAL_VALIDATION"] },
  { key: "VENDOR_VERIFICATION", label: "Vendor verification", backend: ["VENDOR_VERIFICATION"] },
  { key: "PO_MATCHING", label: "Purchase order matching", backend: ["PO_MATCHING"] },
  { key: "DUPLICATE_CHECK", label: "Duplicate detection", backend: ["DUPLICATE_CHECK"] },
  { key: "DECISION", label: "Final decision", backend: ["DECISION"] },
];

export const STAGE_LABELS: Record<string, string> = {
  UPLOAD_RECEIVED: "Upload received",
  DOCUMENT_EXTRACTION: "Document extraction",
  AI_EXTRACTION: "AI extraction",
  DATA_VALIDATION: "Data validation",
  VENDOR_VERIFICATION: "Vendor verification",
  PO_MATCHING: "PO matching",
  DUPLICATE_CHECK: "Duplicate detection",
  FINANCIAL_VALIDATION: "Financial validation",
  DECISION: "Final decision",
};

/** Issue categories shown in the review queue (validation codes from the backend). */
export const ISSUE_LABELS: Record<string, string> = {
  REQUIRED_FIELDS: "Missing fields",
  INVOICE_DATE: "Invoice date",
  CURRENCY_SUPPORTED: "Unsupported currency",
  AMOUNTS_VALID: "Invalid amounts",
  LINE_ITEMS_VALID: "Line items",
  EXTRACTION_QUALITY: "Uncertain extraction",
  TOTAL_ARITHMETIC: "Arithmetic mismatch",
  LINE_ITEM_MATH: "Line item maths",
  LINE_ITEMS_SUM: "Line items vs subtotal",
  VENDOR_MATCH: "Vendor not confirmed",
  VENDOR_STATUS: "Vendor status",
  VENDOR_GSTIN: "GSTIN issue",
  PO_EXISTS: "PO missing / inferred",
  PO_VENDOR: "PO vendor mismatch",
  PO_STATUS: "PO not active",
  PO_CURRENCY: "Currency mismatch",
  PO_BALANCE: "Exceeds PO balance",
  PO_LINE_ITEMS: "PO line items",
  DUP_FILE: "Exact duplicate",
  DUP_BUSINESS: "Duplicate invoice number",
  DUP_POTENTIAL: "Potential duplicate",
  VENDOR_BANK: "Bank details changed",
  TAX_RATES: "GST rate issue",
  APPROVAL_LIMIT: "Above approval limit",
};

export const toneClasses: Record<Tone, string> = {
  success: "bg-success-soft text-success ring-success-ring",
  warning: "bg-warning-soft text-warning ring-warning-ring",
  danger: "bg-danger-soft text-danger ring-danger-ring",
  info: "bg-blue-50 text-blue-700 ring-blue-200",
  neutral: "bg-slate-100 text-slate-600 ring-slate-200",
};

export const poTone = (status: string): Tone => {
  switch (status) {
    case "ACTIVE":
      return "success";
    case "CLOSED":
      return "neutral";
    case "CANCELLED":
      return "danger";
    default:
      return "neutral";
  }
};


