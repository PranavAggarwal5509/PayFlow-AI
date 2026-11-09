from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import ReviewAction
from app.schemas.common import ORMModel
from app.schemas.master_data import VendorOut


class LineItemReconciliationOut(ORMModel):
    id: UUID
    invoice_line_item_id: UUID
    purchase_order_item_id: UUID | None
    status: str
    matching_method: str
    matched_description: str | None
    invoice_quantity: Decimal | None
    ordered_quantity: Decimal | None
    allocated_quantity: Decimal | None
    remaining_quantity: Decimal | None
    unit_of_measure: str | None
    invoice_unit_price: Decimal | None
    po_unit_price: Decimal | None
    price_variance: Decimal | None
    expected_line_amount: Decimal | None
    actual_line_amount: Decimal | None
    explanation: str | None


class LineItemOut(ORMModel):
    id: UUID
    description: str | None
    quantity: Decimal | None
    unit_price: Decimal | None
    tax_percentage: Decimal | None
    total_amount: Decimal | None
    reconciliation: LineItemReconciliationOut | None = None


class ValidationOut(ORMModel):
    validation_type: str
    label: str = ""
    status: str
    impact: str
    expected_value: str | None
    actual_value: str | None
    message: str
    created_at: datetime


class DecisionReasonOut(BaseModel):
    code: str
    severity: str
    message: str


class DecisionOut(BaseModel):
    status: str
    reasons: list[DecisionReasonOut]
    created_at: datetime


class StageEventOut(ORMModel):
    stage: str
    status: str
    message: str | None
    started_at: datetime
    completed_at: datetime | None


class RunSummary(ORMModel):
    id: UUID
    invoice_id: UUID
    invoice_number: str | None = None
    original_file_name: str | None = None
    run_number: int
    status: str
    current_stage: str | None
    started_at: datetime
    completed_at: datetime | None
    duration_seconds: float | None = None
    error_message: str | None
    decision_status: str | None = None


class RunCheck(BaseModel):
    validation_type: str
    label: str
    stage: str
    status: str
    impact: str
    message: str
    expected_value: str | None = None
    actual_value: str | None = None


class RunDecision(BaseModel):
    status: str
    reasons: list[dict]


class RunInvoiceSnapshot(BaseModel):
    vendor_name: str | None = None
    vendor_matched: bool = False
    total_amount: Decimal | None = None
    currency: str | None = None
    po_number: str | None = None
    invoice_date: date | None = None
    extraction_method: str | None = None
    page_count: int | None = None
    line_item_count: int = 0


class RunDetail(RunSummary):
    stages: list[StageEventOut]
    can_retry: bool
    checks: list[RunCheck] = []
    decision: RunDecision | None = None
    invoice: RunInvoiceSnapshot | None = None


class AuditLogOut(ORMModel):
    id: UUID
    actor_type: str
    actor_id: str | None
    action: str
    old_value: str | None
    new_value: str | None
    description: str | None
    created_at: datetime


class ReviewOut(ORMModel):
    id: UUID
    invoice_id: UUID
    review_status: str
    reviewer_comment: str | None
    final_action: str | None
    issue_type: str | None
    assigned_to: str | None
    created_at: datetime
    updated_at: datetime


class POSummary(BaseModel):
    id: UUID
    po_number: str
    vendor_name: str
    currency: str
    total_amount: Decimal
    consumed_amount: Decimal
    remaining_balance: Decimal
    status: str


class InvoiceListItem(BaseModel):
    id: UUID
    invoice_number: str | None
    vendor_id: UUID | None
    vendor_name: str | None
    po_number: str | None
    currency: str | None
    total_amount: Decimal | None
    invoice_date: date | None
    uploaded_at: datetime
    processing_status: str
    decision_status: str | None
    original_file_name: str
    latest_run_id: UUID | None
    current_stage: str | None
    issue: str | None = None
    source_origin: str = "LIVE_UPLOAD"


class InvoiceDetail(InvoiceListItem):
    due_date: date | None
    subtotal: Decimal | None
    tax_amount: Decimal | None
    page_count: int | None
    extraction_method: str | None
    uploaded_by: str
    vendor_name_raw: str | None
    vendor_gstin_raw: str | None
    vendor: VendorOut | None
    purchase_order: POSummary | None
    line_items: list[LineItemOut]
    validations: list[ValidationOut]
    decision: DecisionOut | None
    runs: list[RunSummary]
    review: ReviewOut | None
    audit_trail: list[AuditLogOut]
    extra: dict[str, Any]  # payment terms, bank details, address … shown as labelled fields
    visual_evidence: dict[str, Any] | None = None
    error_message: str | None


class UploadResult(BaseModel):
    invoice_id: UUID
    run_id: UUID
    invoice_number: str | None
    processing_status: str


class ReviewListItem(BaseModel):
    id: UUID
    invoice_id: UUID
    invoice_number: str | None
    vendor_name: str | None
    currency: str | None
    total_amount: Decimal | None
    issue: str | None
    issue_type: str | None
    uploaded_at: datetime
    review_status: str
    review_run_id: UUID | None = None  # the processing run whose decision opened this review


REVIEW_COMMENT_MIN = 10


class ReviewDecisionIn(BaseModel):
    action: ReviewAction
    comment: str = Field(max_length=2000)

    @field_validator("comment")
    @classmethod
    def _meaningful(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < REVIEW_COMMENT_MIN:
            raise ValueError(f"A reason of at least {REVIEW_COMMENT_MIN} characters is required for every review decision.")
        return cleaned


class ReviewDetail(BaseModel):
    review: ReviewOut
    invoice: InvoiceDetail


# ------------------------------------------------------------------ internal API
class RunRef(BaseModel):
    invoice_id: UUID
    run_id: UUID


class ExtractRequest(RunRef):
    mode: str = Field(pattern="^(document|ai)$")
    allow_ocr: bool = False


class ValidateRequest(RunRef):
    scope: str = Field(pattern="^(data|financial)$")


class StageUpdate(BaseModel):
    stage: str | None = None  # optional only for FAILED (defaults to the run's current stage)
    status: str = Field(default="IN_PROGRESS", pattern="^(IN_PROGRESS|COMPLETED|FAILED|NEEDS_ATTENTION)$")
    action: str | None = Field(default=None, pattern="^(claim)$")
    message: str | None = None
    error_category: str | None = None


class DraftRequest(BaseModel):
    invoice_id: UUID | None = None
    run_id: UUID | None = None
    kind: str = Field(pattern="^(PROCESSING_FAILED|CLARIFICATION|REVIEW_NEEDED)$")


class CheckOut(BaseModel):
    validation_type: str
    status: str
    impact: str
    message: str

