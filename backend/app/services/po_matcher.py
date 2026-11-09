"""Purchase-order matching and balance accounting.

Remaining balance = PO total − Σ ACTIVE allocations. An allocation row exists only for invoices
that were approved, so pending / rejected invoices never consume balance.
"""

from decimal import Decimal

from rapidfuzz import fuzz
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.enums import CheckStatus, POStatus
from app.models.invoice import Invoice
from app.models.vendor_po import POAllocation, PurchaseOrder
from app.services.checks import Check, CheckResult, money, passed, review, skipped
from app.utils.normalize import normalize_po_number

LINE_DESCRIPTION_THRESHOLD = 60
LINE_PRICE_TOLERANCE = Decimal("0.05")


def find_purchase_order(db: Session, po_number: str | None) -> PurchaseOrder | None:
    wanted = normalize_po_number(po_number)
    if not wanted:
        return None
    stmt = select(PurchaseOrder).where(
        func.upper(func.replace(PurchaseOrder.po_number, " ", "")) == wanted
    )
    return db.scalar(stmt)


def consumed_amount(
    db: Session, po_id: object, *, exclude_invoice_id: object | None = None
) -> Decimal:
    stmt = select(func.coalesce(func.sum(POAllocation.amount), 0)).where(
        POAllocation.purchase_order_id == po_id, POAllocation.status == "ACTIVE"
    )
    if exclude_invoice_id is not None:
        stmt = stmt.where(POAllocation.invoice_id != exclude_invoice_id)
    return Decimal(db.scalar(stmt) or 0)


def remaining_balance(
    db: Session, po: PurchaseOrder, *, exclude_invoice_id: object | None = None
) -> Decimal:
    return po.total_amount - consumed_amount(db, po.id, exclude_invoice_id=exclude_invoice_id)


def match_purchase_order(
    db: Session, invoice: Invoice, settings: Settings | None = None
) -> list[CheckResult]:
    po = find_purchase_order(db, invoice.po_number_raw)
    invoice.purchase_order_id = po.id if po else None

    if po is None:
        # The PO reference is missing or unknown. Try to infer it from the vendor's open POs.
        inferred, candidates = infer_purchase_order(db, invoice)
        if inferred is not None:
            invoice.purchase_order_id = inferred.id
            return [_inferred_result(invoice, inferred, settings), *_po_checks(db, invoice, inferred)]
        if not invoice.po_number_raw:
            message = "The invoice does not reference a purchase order."
        else:
            message = f"Purchase order {invoice.po_number_raw} was not found."
        if len(candidates) > 1:
            names = ", ".join(c.po_number for c in candidates)
            message += f" Several open POs for this vendor could fit ({names}); a reviewer must choose."
        return _all_skipped_after(
            review(Check.PO_EXISTS, message, actual=invoice.po_number_raw)
        )

    return [
        passed(Check.PO_EXISTS, f"Purchase order {po.po_number} found.", actual=po.po_number),
        *_po_checks(db, invoice, po),
    ]


def _po_checks(db: Session, invoice: Invoice, po: PurchaseOrder) -> list[CheckResult]:
    return [
        _vendor_check(invoice, po),
        _status_check(po),
        _currency_check(invoice, po),
        _balance_check(db, invoice, po),
        _line_items_check(db, invoice, po),
    ]


def infer_purchase_order(
    db: Session, invoice: Invoice
) -> tuple[PurchaseOrder | None, list[PurchaseOrder]]:
    """Implied-PO resolution: the vendor's open PO whose lines cover every invoice line.

    Returns (unique match or None, all plausible candidates). Inference requires a confirmed
    vendor, the same currency, every invoice line matching a PO line (description + price) and
    enough remaining balance — anything weaker is left to a human.
    """
    if invoice.vendor_id is None or not invoice.line_items:
        return None, []
    open_pos = db.scalars(
        select(PurchaseOrder)
        .where(PurchaseOrder.vendor_id == invoice.vendor_id)
        .where(PurchaseOrder.status == POStatus.ACTIVE.value)
        .order_by(PurchaseOrder.po_date)
    ).all()
    candidates = []
    for po in open_pos:
        if invoice.currency and po.currency != invoice.currency:
            continue
        if not all(_line_matches_po(i.description, i.unit_price, po) for i in invoice.line_items):
            continue
        if invoice.total_amount is not None and invoice.total_amount > remaining_balance(
            db, po, exclude_invoice_id=invoice.id
        ):
            continue
        candidates.append(po)
    return (candidates[0] if len(candidates) == 1 else None), candidates


def _inferred_result(invoice: Invoice, po: PurchaseOrder, settings: Settings | None) -> CheckResult:
    lines = len(invoice.line_items)
    why = (
        f"all {lines} invoice line(s) match its items and the remaining balance covers the total"
    )
    if invoice.po_number_raw:
        message = (
            f"PO {invoice.po_number_raw} does not exist; inferred {po.po_number} instead because {why}."
        )
    else:
        message = f"No PO printed on the invoice; inferred {po.po_number} because {why}."
    if settings is not None and settings.auto_approve_inferred_po:
        return passed(Check.PO_EXISTS, message, actual=po.po_number)
    return review(
        Check.PO_EXISTS,
        message + " Confirm the reference before payment.",
        expected=po.po_number,
        actual=invoice.po_number_raw or "not printed",
        status=CheckStatus.WARNING,
    )


def _all_skipped_after(first: CheckResult) -> list[CheckResult]:
    reason = "No purchase order to compare against."
    rest = [
        Check.PO_VENDOR, Check.PO_STATUS, Check.PO_CURRENCY, Check.PO_BALANCE, Check.PO_LINE_ITEMS
    ]  # fmt: skip
    return [first, *[skipped(code, reason) for code in rest]]


def _vendor_check(invoice: Invoice, po: PurchaseOrder) -> CheckResult:
    if invoice.vendor_id is None:
        return review(
            Check.PO_VENDOR,
            f"Vendor is unconfirmed, so PO ownership by {po.vendor.vendor_name} could not be matched.",
            expected=po.vendor.vendor_name,
            status=CheckStatus.WARNING,
        )
    if invoice.vendor_id != po.vendor_id:
        return review(
            Check.PO_VENDOR,
            f"PO {po.po_number} belongs to {po.vendor.vendor_name}, not the invoice vendor.",
            expected=po.vendor.vendor_name,
            actual=invoice.vendor.vendor_name if invoice.vendor else invoice.vendor_name_raw,
        )
    return passed(Check.PO_VENDOR, "PO belongs to the invoice vendor.", actual=po.vendor.vendor_name)


def _status_check(po: PurchaseOrder) -> CheckResult:
    if po.status == POStatus.ACTIVE.value:
        return passed(Check.PO_STATUS, "Purchase order is active.", actual=po.status)
    return review(
        Check.PO_STATUS,
        f"Purchase order is {po.status.lower()}.",
        expected=POStatus.ACTIVE.value,
        actual=po.status,
    )


def _currency_check(invoice: Invoice, po: PurchaseOrder) -> CheckResult:
    if not invoice.currency:
        return skipped(Check.PO_CURRENCY, "Invoice currency is missing.")
    if invoice.currency != po.currency:
        return review(
            Check.PO_CURRENCY,
            f"Invoice currency {invoice.currency} does not match PO currency {po.currency}.",
            expected=po.currency,
            actual=invoice.currency,
        )
    return passed(Check.PO_CURRENCY, "Currency matches the PO.", actual=po.currency)


def _balance_check(db: Session, invoice: Invoice, po: PurchaseOrder) -> CheckResult:
    if invoice.total_amount is None:
        return skipped(Check.PO_BALANCE, "Invoice total is missing.")
    if invoice.currency != po.currency:
        return skipped(Check.PO_BALANCE, "Currencies differ; balance cannot be compared.")
    remaining = remaining_balance(db, po, exclude_invoice_id=invoice.id)
    if invoice.total_amount > remaining:
        excess = invoice.total_amount - remaining
        return review(
            Check.PO_BALANCE,
            f"Invoice total is {money(excess, po.currency)} higher than the remaining PO balance.",
            expected=f"<= {money(remaining, po.currency)}",
            actual=money(invoice.total_amount, po.currency),
        )
    return passed(
        Check.PO_BALANCE,
        f"Invoice total is within the remaining PO balance of {money(remaining, po.currency)}.",
        expected=f"<= {money(remaining, po.currency)}",
        actual=money(invoice.total_amount, po.currency),
    )


def _line_items_check(db: Session, invoice: Invoice, po: PurchaseOrder) -> CheckResult:
    if not po.items:
        return skipped(Check.PO_LINE_ITEMS, "The PO has no line items to compare.")
    if not invoice.line_items:
        return skipped(Check.PO_LINE_ITEMS, "The invoice has no line items to compare.")

    # Ensure invoice line items are flushed so they have IDs before creating reconciliations
    db.flush()

    from app.services.line_item_reconciler import (
        persist_line_reconciliations,
        reconcile_invoice_line_items,
    )

    reconciliations, check_results = reconcile_invoice_line_items(db, invoice, po)
    if reconciliations:
        persist_line_reconciliations(db, reconciliations)

    return check_results[0] if check_results else passed(Check.PO_LINE_ITEMS, "Line items verified.")


def _line_matches_po(description: str | None, unit_price: Decimal | None, po: PurchaseOrder) -> bool:
    if not description:
        return False
    for item in po.items:
        if fuzz.token_set_ratio(description.lower(), item.description.lower()) < LINE_DESCRIPTION_THRESHOLD:
            continue
        if unit_price is None or item.unit_price == 0:
            return True
        if abs(unit_price - item.unit_price) / item.unit_price <= LINE_PRICE_TOLERANCE:
            return True
    return False


def allocate_to_po(
    db: Session, invoice: Invoice, *, allocated_by: str, tolerance: Decimal = Decimal("0")
) -> POAllocation | None:
    """Reserve PO balance for an approved invoice. Must run inside the caller's transaction.

    Locks the PO row (SELECT … FOR UPDATE on PostgreSQL) so two concurrent approvals cannot
    both consume the same remaining balance. Raises ValueError if the balance is insufficient.
    Idempotent: an existing ACTIVE allocation for the invoice is returned unchanged.
    """
    if invoice.purchase_order_id is None or invoice.total_amount is None:
        return None
    existing = db.scalar(select(POAllocation).where(POAllocation.invoice_id == invoice.id))
    if existing and existing.status == "ACTIVE":
        return existing

    po = db.scalar(
        select(PurchaseOrder).where(PurchaseOrder.id == invoice.purchase_order_id).with_for_update()
    )
    if po is None:
        raise ValueError("Purchase order not found.")
    if invoice.currency != po.currency:
        raise ValueError(
            f"Invoice currency {invoice.currency} does not match PO currency {po.currency}."
        )
    remaining = remaining_balance(db, po, exclude_invoice_id=invoice.id)
    if invoice.total_amount > (remaining + tolerance):
        raise ValueError(
            f"Invoice total exceeds the remaining PO balance of {money(remaining, po.currency)}."
        )
    allocation = existing or POAllocation(purchase_order_id=po.id, invoice_id=invoice.id)
    allocation.amount = invoice.total_amount
    allocation.status = "ACTIVE"
    allocation.allocated_by = allocated_by
    db.add(allocation)
    db.flush()

    # Also allocate granular PO line items
    from app.services.line_item_reconciler import allocate_po_line_items

    allocate_po_line_items(db, invoice, allocated_by=allocated_by)

    return allocation

