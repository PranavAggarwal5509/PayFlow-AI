// Mirrors backend/app/schemas. Money values arrive as decimal strings (never floats).

export type Money = string;

export interface PageMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface ApiEnvelope<T> {
  data: T | null;
  meta: PageMeta | null;
  error: { code: string; message: string; details?: unknown } | null;
}

export interface Paginated<T> {
  items: T[];
  meta: PageMeta;
}

export type DecisionStatus = "APPROVED" | "NEEDS_REVIEW" | "REJECTED";
export type ProcessingStatus = "PROCESSING" | "COMPLETED" | "FAILED";
export type RunStatus = "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";
export type StageStatus = "IN_PROGRESS" | "COMPLETED" | "FAILED" | "NEEDS_ATTENTION";
export type CheckStatus = "PASSED" | "WARNING" | "FAILED" | "SKIPPED";
export type ReviewStatus = "PENDING" | "CLARIFICATION_REQUESTED" | "APPROVED" | "REJECTED";
export type ReviewAction = "APPROVE" | "REJECT" | "REQUEST_CLARIFICATION";
export type VendorStatus = "ACTIVE" | "INACTIVE" | "PENDING";
export type POStatus = "ACTIVE" | "CLOSED" | "CANCELLED";

export interface InvoiceListItem {
  id: string;
  invoice_number: string | null;
  vendor_id: string | null;
  vendor_name: string | null;
  po_number: string | null;
  currency: string | null;
  total_amount: Money | null;
  invoice_date: string | null;
  uploaded_at: string;
  processing_status: ProcessingStatus;
  decision_status: DecisionStatus | null;
  original_file_name: string;
  latest_run_id: string | null;
  current_stage: string | null;
  issue: string | null;
  source_origin?: "LIVE_UPLOAD" | "SEED_HISTORY" | string;
}

export interface Vendor {
  id: string;
  vendor_code: string;
  vendor_name: string;
  gstin: string | null;
  address: string | null;
  email: string | null;
  phone: string | null;
  status: VendorStatus;
  is_demo: boolean;
  created_at: string;
  invoice_count: number;
  total_invoice_value: Money;
}

export interface POSummary {
  id: string;
  po_number: string;
  vendor_name: string;
  currency: string;
  total_amount: Money;
  consumed_amount: Money;
  remaining_balance: Money;
  status: POStatus;
}

export interface PurchaseOrder extends POSummary {
  vendor_id: string;
  po_date: string;
  description: string | null;
  is_demo: boolean;
}

export interface POItem {
  id: string;
  description: string;
  quantity: string;
  unit_price: Money;
  total_amount: Money;
}

export interface LinkedInvoice {
  id: string;
  invoice_number: string | null;
  total_amount: Money | null;
  currency: string | null;
  decision_status: DecisionStatus | null;
  allocated: boolean;
}

export interface PurchaseOrderDetail extends PurchaseOrder {
  items: POItem[];
  invoices: LinkedInvoice[];
}

export type LineMatchStatus =
  | "MATCHED"
  | "MATCHED_WITH_VARIANCE"
  | "UNMATCHED"
  | "AMBIGUOUS"
  | "QUANTITY_EXCEEDED"
  | "PRICE_MISMATCH"
  | "UNIT_MISMATCH"
  | "BUNDLED_REQUIRES_REVIEW";

export interface LineItemReconciliation {
  id: string;
  invoice_line_item_id: string;
  purchase_order_item_id: string | null;
  status: LineMatchStatus;
  matching_method: string;
  matched_description: string | null;
  invoice_quantity: string | null;
  ordered_quantity: string | null;
  allocated_quantity: string | null;
  remaining_quantity: string | null;
  unit_of_measure: string | null;
  invoice_unit_price: Money | null;
  po_unit_price: Money | null;
  price_variance: Money | null;
  expected_line_amount: Money | null;
  actual_line_amount: Money | null;
  explanation: string | null;
}

export interface LineItem {
  id?: string;
  description: string | null;
  quantity: string | null;
  unit_price: Money | null;
  tax_percentage: string | null;
  total_amount: Money | null;
  reconciliation?: LineItemReconciliation | null;
}

export interface ValidationResult {
  validation_type: string;
  label: string;
  status: CheckStatus;
  impact: "NONE" | "REVIEW" | "REJECT";
  expected_value: string | null;
  actual_value: string | null;
  message: string;
  created_at: string;
}

export interface DecisionReason {
  code: string;
  severity: "BLOCKING" | "WARNING" | "INFO";
  message: string;
}

export interface Decision {
  status: DecisionStatus;
  reasons: DecisionReason[];
  created_at: string;
}

export interface RunSummary {
  id: string;
  invoice_id: string;
  invoice_number: string | null;
  original_file_name: string | null;
  run_number: number;
  status: RunStatus;
  current_stage: string | null;
  started_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
  error_message: string | null;
  decision_status: DecisionStatus | null;
}

export interface StageEvent {
  stage: string;
  status: StageStatus;
  message: string | null;
  started_at: string;
  completed_at: string | null;
}

export interface RunDetail extends RunSummary {
  stages: StageEvent[];
  can_retry: boolean;
}

export interface AuditEntry {
  id: string;
  actor_type: string;
  actor_id: string | null;
  action: string;
  old_value: string | null;
  new_value: string | null;
  description: string | null;
  created_at: string;
}

export interface Review {
  id: string;
  invoice_id: string;
  review_status: ReviewStatus;
  reviewer_comment: string | null;
  final_action: string | null;
  issue_type: string | null;
  assigned_to: string | null;
  created_at: string;
  updated_at: string;
}

export interface FieldEvidence {
  page: number;
  bbox: [number, number, number, number] | null;
  norm_bbox: [number, number, number, number] | null;
  source: "pdf_text" | "tesseract";
  evidence_status: "VERIFIED" | "AMBIGUOUS" | "NOT_FOUND";
  text?: string;
  page_width?: number;
  page_height?: number;
}

export interface LineItemEvidence {
  line_index: number;
  description?: FieldEvidence;
  quantity?: FieldEvidence;
  unit_price?: FieldEvidence;
  total_amount?: FieldEvidence;
}

export type VisualEvidence = Record<string, FieldEvidence | LineItemEvidence[] | unknown>;

export interface InvoiceDetail extends InvoiceListItem {
  due_date: string | null;
  subtotal: Money | null;
  tax_amount: Money | null;
  page_count: number | null;
  extraction_method: "TEXT" | "OCR" | null;
  uploaded_by: string;
  vendor_name_raw: string | null;
  vendor_gstin_raw: string | null;
  vendor: Vendor | null;
  purchase_order: POSummary | null;
  line_items: LineItem[];
  validations: ValidationResult[];
  decision: Decision | null;
  runs: RunSummary[];
  review: Review | null;
  audit_trail: AuditEntry[];
  extra: Record<string, string | string[]>;
  visual_evidence?: VisualEvidence | null;
  error_message: string | null;
}

export interface ReviewListItem {
  id: string;
  invoice_id: string;
  invoice_number: string | null;
  vendor_name: string | null;
  currency: string | null;
  total_amount: Money | null;
  issue: string | null;
  issue_type: string | null;
  uploaded_at: string;
  review_status: ReviewStatus;
}

export interface UploadResult {
  invoice_id: string;
  run_id: string;
  invoice_number: string | null;
  processing_status: ProcessingStatus;
}

export interface Kpi {
  value: number;
  change_percent: number | null;
  last_30_days: number;
}

export interface OperationalMetrics {
  period_days: number;
  volume: {
    total_invoices: number;
    total_runs: number;
    completed_runs: number;
    failed_runs: number;
    approved: number;
    needs_review: number;
    rejected: number;
  };
  speed: {
    avg_end_to_end_seconds: number | null;
    p50_end_to_end_seconds: number | null;
    p95_end_to_end_seconds: number | null;
    avg_ai_extraction_seconds: number | null;
    avg_document_extraction_seconds: number | null;
    stage_breakdown: {
      stage: string;
      avg_seconds: number;
      p95_seconds: number;
      count: number;
    }[];
  };
  reliability: {
    technical_success_rate: number;
    technical_failure_rate: number;
    manual_review_rate: number;
    retry_count: number;
    recovery_count: number;
    ocr_count: number;
    digital_count: number;
    failed_before_extraction?: number;
    total_attempts?: number;
    technical_success_formula?: string;
    technical_failure_formula?: string;
    manual_review_formula?: string;
  };
  ai_usage: {
    gemini_request_count: number;
    tokens_available?: boolean;
    prompt_tokens: number | null;
    completion_tokens: number | null;
    total_tokens: number | null;
    unavailable_message?: string | null;
    models: {
      model: string;
      requests: number;
      prompt_tokens: number | null;
      completion_tokens: number | null;
      total_tokens: number | null;
      tokens_available?: boolean;
      avg_latency_ms: number | null;
    }[];
    cost_status: string;
    cost_details: unknown;
  };
}

export interface PortfolioGroup {
  total: number;
  approved: number;
  needs_review: number;
  rejected: number;
  failed: number;
}

export interface DashboardStats {
  kpis: { total: Kpi; approved: Kpi; needs_review: Kpi; rejected: Kpi; failed: Kpi };
  portfolio?: {
    all: PortfolioGroup;
    live: PortfolioGroup;
    historical: PortfolioGroup;
  };
  approval_rate: number | null;
  pending_reviews: number;
  total_value_by_currency: Record<string, Money>;
  average_processing_seconds: number | null;
  monthly_volume: { month: string; count: number; value: Money }[];
  daily_volume: { date: string; count: number }[];
  decision_distribution: { status: string; count: number }[];
  decision_distribution_detailed?: {
    live: PortfolioGroup;
    historical: PortfolioGroup;
    combined: PortfolioGroup;
  };
  recent_failed_runs: {
    run_id: string;
    invoice_id: string;
    invoice_number: string;
    stage: string | null;
    message: string | null;
    started_at: string;
  }[];
  analytics?: OperationalMetrics;
}

export interface ActivityItem {
  id: string;
  invoice_id: string;
  invoice_number: string;
  action: string;
  actor: string;
  description: string | null;
  new_value: string | null;
  created_at: string;
}

export interface AppSettings {
  user: { id: string; name: string; role: string };
  environment: string;
  llm_provider?: string;
  llm_model: string;
  llm_configured: boolean;
  max_upload_size_mb: number;
  supported_currencies: string[];
  inr_rounding_tolerance: string;
  default_rounding_tolerance: string;
  require_gstin_for_approval: boolean;
  vendor_fuzzy_threshold: number;
  duplicate_number_similarity: number;
}

