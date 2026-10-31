"""Invoice read-side queries and response assembly."""

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.invoice import Invoice
from app.models.processing import AuditLog, Decision, ProcessingRun, Review, ValidationResult
from app.models.vendor_po import PurchaseOrder, Vendor
from app.repositories.vendor_repository import vendor_out
from app.schemas.invoice import (
    AuditLogOut,
    DecisionOut,
    DecisionReasonOut,
    InvoiceDetail,
    InvoiceListItem,
    LineItemOut,
    POSummary,
    ReviewOut,
    RunSummary,
    ValidationOut,
)
from app.services.checks import LABELS
from app.services.po_matcher import consumed_amount

SORT_COLUMNS = {
    "uploaded_at": Invoice.uploaded_at,
    "invoice_date": Invoice.invoice_date,
    "total_amount": Invoice.total_amount,
    "invoice_number": Invoice.invoice_number,
    "decision_status": Invoice.decision_status,
    "processing_status": Invoice.processing_status,
}


@dataclass
class InvoiceFilters:
    q: str | None = None
    decision_status: str | None = None
    processing_status: str | None = None
    vendor_id: UUID | None = None
    currency: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    po_number: str | None = None


def apply_filters(stmt: Select, f: InvoiceFilters) -> Select:
    if f.q:
        like = f"%{f.q.strip()}%"
        stmt = stmt.outerjoin(Vendor, Invoice.vendor_id == Vendor.id).where(
            or_(
                Invoice.invoice_number.ilike(like),
                Invoice.vendor_name_raw.ilike(like),
                Vendor.vendor_name.ilike(like),
                Invoice.po_number_raw.ilike(like),
                Invoice.original_file_name.ilike(like),
            )
        )
    if f.decision_status:
        stmt = stmt.where(Invoice.decision_status == f.decision_status)
    if f.processing_status:
        stmt = stmt.where(Invoice.processing_status == f.processing_status)
    if f.vendor_id:
        stmt = stmt.where(Invoice.vendor_id == f.vendor_id)
    if f.po_number:
        stmt = stmt.where(Invoice.po_number_raw.ilike(f"%{f.po_number.strip()}%"))
    if f.currency:
        stmt = stmt.where(Invoice.currency == f.currency.upper())
    if f.date_from:
        stmt = stmt.where(Invoice.uploaded_at >= datetime.combine(f.date_from, time.min))
    if f.date_to:
        stmt = stmt.where(Invoice.uploaded_at <= datetime.combine(f.date_to, time.max))
    if f.min_amount is not None:
        stmt = stmt.where(Invoice.total_amount >= f.min_amount)
    if f.max_amount is not None:
        stmt = stmt.where(Invoice.total_amount <= f.max_amount)
    return stmt


def list_invoices(
    db: Session, filters: InvoiceFilters, sort_by: str, descending: bool, page: int, page_size: int
) -> tuple[list[InvoiceListItem], int]:
    base = apply_filters(select(Invoice.id), filters)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0

    column = SORT_COLUMNS.get(sort_by, Invoice.uploaded_at)
    order = column.desc().nulls_last() if descending else column.asc().nulls_last()
    stmt = (
        apply_filters(select(Invoice), filters)
        .options(
            selectinload(Invoice.vendor), selectinload(Invoice.purchase_order),
            selectinload(Invoice.runs),
        )  # fmt: skip
        .order_by(order, Invoice.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    invoices = list(db.scalars(stmt).unique())
    issues = _issues_for(db, invoices)
    return [to_list_item(inv, issues.get(inv.id)) for inv in invoices], total


def _issues_for(db: Session, invoices: list[Invoice]) -> dict[UUID, str]:
    """Primary blocking reason (or failure message) for each invoice — one query for the page."""
    issues: dict[UUID, str] = {}
    run_ids = {inv.runs[-1].id: inv for inv in invoices if inv.runs}
    if not run_ids:
        return issues
    for decision in db.scalars(select(Decision).where(Decision.processing_run_id.in_(run_ids))):
        reason = next((r for r in decision.reasons if r["severity"] != "INFO"), None)
        if reason:
            issues[decision.invoice_id] = reason["message"]
    for inv in run_ids.values():
        run = inv.runs[-1]
        if run.error_message:
            issues[inv.id] = run.error_message
    return issues


def to_list_item(inv: Invoice, issue: str | None = None) -> InvoiceListItem:
    latest = inv.runs[-1] if inv.runs else None
    return InvoiceListItem(
        id=inv.id,
        invoice_number=inv.invoice_number,
        vendor_id=inv.vendor_id,
        vendor_name=inv.vendor.vendor_name if inv.vendor else inv.vendor_name_raw,
        po_number=inv.purchase_order.po_number if inv.purchase_order else inv.po_number_raw,
        currency=inv.currency,
        total_amount=inv.total_amount,
        invoice_date=inv.invoice_date,
        uploaded_at=inv.uploaded_at,
        processing_status=inv.processing_status,
        decision_status=inv.decision_status,
        original_file_name=inv.original_file_name,
        latest_run_id=latest.id if latest else None,
        current_stage=latest.current_stage if latest else None,
        issue=issue,
    )


def run_summary(run: ProcessingRun, invoice: Invoice | None = None) -> RunSummary:
    invoice = invoice or run.invoice
    end = run.completed_at
    duration = None
    if end:
        duration = max(0.0, (_naive(end) - _naive(run.started_at)).total_seconds())
    return RunSummary(
        id=run.id,
        invoice_id=run.invoice_id,
        invoice_number=invoice.invoice_number,
        original_file_name=invoice.original_file_name,
        run_number=run.run_number,
        status=run.status,
        current_stage=run.current_stage,
        started_at=run.started_at,
        completed_at=run.completed_at,
        duration_seconds=duration,
        error_message=run.error_message,
        decision_status=invoice.decision_status,
    )


def _naive(value: datetime) -> datetime:
    return value.replace(tzinfo=None)


def po_summary(db: Session, po: PurchaseOrder) -> POSummary:
    consumed = consumed_amount(db, po.id)
    return POSummary(
        id=po.id,
        po_number=po.po_number,
        vendor_name=po.vendor.vendor_name,
        currency=po.currency,
        total_amount=po.total_amount,
        consumed_amount=consumed,
        remaining_balance=po.total_amount - consumed,
        status=po.status,
    )


def get_invoice_detail(db: Session, invoice_id: UUID) -> InvoiceDetail | None:
    inv = db.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(
            selectinload(Invoice.vendor), selectinload(Invoice.purchase_order),
            selectinload(Invoice.runs), selectinload(Invoice.line_items),
        )  # fmt: skip
    )
    if inv is None:
        return None
    latest = inv.runs[-1] if inv.runs else None

    validations: list[ValidationOut] = []
    decision: DecisionOut | None = None
    if latest:
        rows = db.scalars(
            select(ValidationResult)
            .where(ValidationResult.processing_run_id == latest.id)
            .order_by(ValidationResult.created_at)
        )
        validations = [
            ValidationOut.model_validate(r).model_copy(
                update={"label": LABELS.get(r.validation_type, r.validation_type)}
            )
            for r in rows
        ]
        d = db.scalar(select(Decision).where(Decision.processing_run_id == latest.id))
        if d:
            decision = DecisionOut(
                status=d.status,
                reasons=[DecisionReasonOut(**r) for r in d.reasons],
                created_at=d.created_at,
            )

    review = db.scalar(select(Review).where(Review.invoice_id == inv.id))
    audit = db.scalars(
        select(AuditLog).where(AuditLog.invoice_id == inv.id).order_by(AuditLog.created_at.desc())
    )
    data = inv.extracted_data or {}
    extra = {
        k: data.get(k)
        for k in (
            "vendor_address", "payment_terms", "bank_account_details", "payment_instructions",
            "other_references",
        )  # fmt: skip
        if data.get(k)
    }
    issue = None
    if decision:
        issue = next((r.message for r in decision.reasons if r.severity != "INFO"), None)
    base = to_list_item(inv, issue)
    return InvoiceDetail(
        **base.model_dump(),
        due_date=inv.due_date,
        subtotal=inv.subtotal,
        tax_amount=inv.tax_amount,
        page_count=inv.page_count,
        extraction_method=inv.extraction_method,
        uploaded_by=inv.uploaded_by,
        vendor_name_raw=inv.vendor_name_raw,
        vendor_gstin_raw=inv.vendor_gstin_raw,
        vendor=vendor_out(db, inv.vendor) if inv.vendor else None,
        purchase_order=po_summary(db, inv.purchase_order) if inv.purchase_order else None,
        line_items=[LineItemOut.model_validate(li) for li in inv.line_items],
        validations=validations,
        decision=decision,
        runs=[run_summary(r, inv) for r in inv.runs],
        review=ReviewOut.model_validate(review) if review else None,
        audit_trail=[AuditLogOut.model_validate(a) for a in audit],
        extra=extra,
        error_message=latest.error_message if latest else None,
    )
