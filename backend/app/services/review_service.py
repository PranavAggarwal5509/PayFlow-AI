"""Manual review actions."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models.enums import DecisionStatus, ReviewAction, ReviewStatus
from app.models.invoice import Invoice
from app.models.processing import NotificationDraft, Review
from app.services import po_matcher
from app.services.audit_service import record_audit

OPEN_STATUSES = (ReviewStatus.PENDING.value, ReviewStatus.CLARIFICATION_REQUESTED.value)


def apply_review_decision(
    db: Session, review_id: UUID, action: ReviewAction, comment: str, *, user_id: str
) -> Review:
    """Record a human decision atomically: review row, invoice, PO allocation, audit log."""
    review = db.scalar(select(Review).where(Review.id == review_id).with_for_update())
    if review is None:
        raise NotFoundError("Review not found.")
    if review.review_status not in OPEN_STATUSES:
        raise ConflictError("This review has already been resolved.")
    invoice = db.get(Invoice, review.invoice_id)
    assert invoice is not None
    old_decision = invoice.decision_status

    if action == ReviewAction.APPROVE:
        try:
            # Allocation re-checks the balance under a row lock: a reviewer cannot overspend a PO.
            po_matcher.allocate_to_po(db, invoice, allocated_by=user_id)
        except ValueError as exc:
            raise ConflictError(str(exc)) from exc
        invoice.decision_status = DecisionStatus.APPROVED.value
        review.review_status = ReviewStatus.APPROVED.value
    elif action == ReviewAction.REJECT:
        invoice.decision_status = DecisionStatus.REJECTED.value
        review.review_status = ReviewStatus.REJECTED.value
    else:
        review.review_status = ReviewStatus.CLARIFICATION_REQUESTED.value
        db.add(_clarification_draft(invoice, comment))

    review.reviewer_comment = comment
    review.final_action = action.value
    review.assigned_to = user_id
    record_audit(
        db, action=f"REVIEW_{action.value}", actor_type="USER", actor_id=user_id,
        invoice_id=invoice.id, old_value=old_decision, new_value=invoice.decision_status,
        description=comment,
    )  # fmt: skip
    db.commit()
    return review


def _clarification_draft(invoice: Invoice, comment: str) -> NotificationDraft:
    vendor = invoice.vendor.vendor_name if invoice.vendor else invoice.vendor_name_raw or "Vendor"
    return NotificationDraft(
        invoice_id=invoice.id,
        kind="CLARIFICATION",
        recipient=invoice.vendor.email if invoice.vendor else None,
        subject=f"Clarification needed for invoice {invoice.invoice_number or invoice.original_file_name}",
        body=(
            f"Hello {vendor},\n\nWhile processing your invoice "
            f"{invoice.invoice_number or '(number not found)'} we need clarification:\n\n"
            f"{comment}\n\nPlease reply with the requested details.\n\nAccounts Payable"
        ),
    )

