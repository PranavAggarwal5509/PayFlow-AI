"""Three-level duplicate detection.

Determinism / idempotency rule: an invoice is only compared with invoices that were uploaded
*before* it (uploaded_at, id). Re-running the check, retrying a run, or two simultaneous
uploads of the same document therefore always yield the same answer: the earliest upload is the
original and every later copy is the duplicate.
"""

from datetime import timedelta

from rapidfuzz import fuzz
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.enums import CheckStatus, DecisionStatus, ProcessingStatus
from app.models.invoice import Invoice
from app.services.checks import Check, CheckResult, money, passed, reject, review, skipped
from app.utils.normalize import normalize_invoice_number


def _earlier_than(invoice: Invoice):
    return or_(
        Invoice.uploaded_at < invoice.uploaded_at,
        and_(Invoice.uploaded_at == invoice.uploaded_at, Invoice.id < invoice.id),
    )


def _usable():
    """Invoices that never reached a business outcome because of a technical failure don't count."""
    return Invoice.processing_status != ProcessingStatus.FAILED.value


def detect_duplicates(db: Session, invoice: Invoice, settings: Settings) -> list[CheckResult]:
    return [
        _file_duplicate(db, invoice),
        _business_duplicate(db, invoice),
        _potential_duplicate(db, invoice, settings),
    ]


def _describe(other: Invoice) -> str:
    when = other.uploaded_at.strftime("%d %b %Y") if other.uploaded_at else "earlier"
    return f"{other.invoice_number or other.original_file_name} (uploaded {when})"


def _file_duplicate(db: Session, invoice: Invoice) -> CheckResult:
    original = db.scalar(
        select(Invoice)
        .where(Invoice.file_hash == invoice.file_hash, Invoice.id != invoice.id)
        .where(_earlier_than(invoice), _usable())
        .order_by(Invoice.uploaded_at, Invoice.id)
        .limit(1)
    )
    if original:
        return reject(
            Check.DUP_FILE,
            f"This exact file was already uploaded as invoice {_describe(original)}.",
            actual=invoice.file_hash[:12],
        )
    return passed(Check.DUP_FILE, "No identical file has been uploaded before.")


def _business_duplicate(db: Session, invoice: Invoice) -> CheckResult:
    if invoice.vendor_id is None or not invoice.invoice_number:
        return skipped(Check.DUP_BUSINESS, "Vendor or invoice number unavailable.")
    wanted = normalize_invoice_number(invoice.invoice_number)
    candidates = db.scalars(
        select(Invoice)
        .where(Invoice.vendor_id == invoice.vendor_id, Invoice.id != invoice.id)
        .where(Invoice.invoice_number.is_not(None))
        .where(_earlier_than(invoice), _usable())
        .where(Invoice.decision_status != DecisionStatus.REJECTED.value)
        .order_by(Invoice.uploaded_at)
    )
    for other in candidates:
        if normalize_invoice_number(other.invoice_number) == wanted:
            return reject(
                Check.DUP_BUSINESS,
                f"Invoice number {invoice.invoice_number} was already submitted by this vendor: "
                f"{_describe(other)}.",
                actual=invoice.invoice_number,
            )
    return passed(Check.DUP_BUSINESS, "No existing invoice has this vendor and invoice number.")


def _potential_duplicate(db: Session, invoice: Invoice, settings: Settings) -> CheckResult:
    if invoice.vendor_id is None or invoice.total_amount is None:
        return skipped(Check.DUP_POTENTIAL, "Vendor or amount unavailable.")
    tolerance = settings.tolerance_for(invoice.currency)
    window = timedelta(days=settings.duplicate_window_days)
    candidates = db.scalars(
        select(Invoice)
        .where(Invoice.vendor_id == invoice.vendor_id, Invoice.id != invoice.id)
        .where(_earlier_than(invoice), _usable())
        .where(Invoice.decision_status != DecisionStatus.REJECTED.value)
        .where(
            func.abs(Invoice.total_amount - invoice.total_amount) <= tolerance,
        )
    )
    wanted = normalize_invoice_number(invoice.invoice_number)
    for other in candidates:
        # Recurring invoices (rent, retainers) legitimately repeat amounts; only nearby dates count.
        if invoice.invoice_date and other.invoice_date and abs(invoice.invoice_date - other.invoice_date) > window:
            continue
        same_number = normalize_invoice_number(other.invoice_number) == wanted and wanted
        if same_number:
            continue  # handled as a business duplicate
        similarity = fuzz.ratio(wanted, normalize_invoice_number(other.invoice_number))
        same_date = bool(invoice.invoice_date) and invoice.invoice_date == other.invoice_date
        if same_date or similarity >= settings.duplicate_number_similarity:
            reason = (
                "same invoice date" if same_date else f"{similarity:.0f}% similar invoice number"
            )
            return review(
                Check.DUP_POTENTIAL,
                f"Possible duplicate of {_describe(other)}: same vendor and amount "
                f"{money(other.total_amount, other.currency)}, {reason}.",
                actual=money(invoice.total_amount, invoice.currency),
                status=CheckStatus.WARNING,
            )
    return passed(Check.DUP_POTENTIAL, "No suspiciously similar invoice found.")
