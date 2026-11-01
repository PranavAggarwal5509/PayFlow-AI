"""Granular invoice line-item reconciliation against purchase order line items.

Layered matching strategy:
1. Exact match (Description / SKU / Identifiers)
2. Normalized descriptions and tokens
3. Controlled fuzzy matching (rapidfuzz) with ambiguity detection
4. Bundled detection

Evaluates quantities, cumulative allocations, unit price variances, and units of measure.
"""

import re
from decimal import Decimal
from typing import NamedTuple
from uuid import UUID

from rapidfuzz import fuzz
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.enums import LineMatchStatus
from app.models.invoice import Invoice, InvoiceLineItem, LineItemReconciliation
from app.models.vendor_po import POLineAllocation, PurchaseOrder, PurchaseOrderItem
from app.services.checks import Check, CheckResult, passed, review, skipped

LINE_EXACT_THRESHOLD = 95
LINE_FUZZY_THRESHOLD = 65


class LineMatchCandidate(NamedTuple):
    po_item: PurchaseOrderItem
    method: str
    score: float


def normalize_line_desc(desc: str | None) -> str:
    if not desc:
        return ""
    # Lowercase, strip punctuation and extra spaces
    cleaned = re.sub(r"[^\w\s]", " ", desc.lower())
    return " ".join(cleaned.split())


def consumed_po_item_quantity(
    db: Session, po_item_id: UUID, *, exclude_invoice_id: UUID | None = None
) -> Decimal:
    """Calculate cumulative allocated quantity for a PO item across all active allocations."""
    stmt = select(func.coalesce(func.sum(POLineAllocation.quantity), 0)).where(
        POLineAllocation.purchase_order_item_id == po_item_id,
        POLineAllocation.status == "ACTIVE",
    )
    if exclude_invoice_id is not None:
        stmt = stmt.where(POLineAllocation.invoice_id != exclude_invoice_id)
    return Decimal(str(db.scalar(stmt) or 0))


def remaining_po_item_quantity(
    db: Session, po_item: PurchaseOrderItem, *, exclude_invoice_id: UUID | None = None
) -> Decimal:
    consumed = consumed_po_item_quantity(db, po_item.id, exclude_invoice_id=exclude_invoice_id)
    return po_item.quantity - consumed


def find_best_po_item_matches(
    invoice_line: InvoiceLineItem, po_items: list[PurchaseOrderItem]
) -> tuple[LineMatchCandidate | None, bool]:
    """Find the best PO item for an invoice line. Returns (best_candidate, is_ambiguous)."""
    desc = invoice_line.description or ""
    norm_inv = normalize_line_desc(desc)
    if not norm_inv or not po_items:
        return None, False

    # Check for bundle keywords or multiple item indicators in invoice description
    bundle_indicators = ["bundle", "combo", "kit", "package deal", "assorted items", "lot of"]
    is_bundle = any(b in norm_inv for b in bundle_indicators)
    if is_bundle:
        # Bundled item requires human decomposition
        return None, True

    # 1. Level 1 - Exact description or code match
    for poi in po_items:
        norm_po = normalize_line_desc(poi.description)
        if norm_inv == norm_po:
            return LineMatchCandidate(poi, "EXACT", 100.0), False

    # 2. Level 2 - Token set ratio exact match (100)
    exact_token_matches: list[LineMatchCandidate] = []
    for poi in po_items:
        norm_po = normalize_line_desc(poi.description)
        score = fuzz.token_sort_ratio(norm_inv, norm_po)
        if score >= LINE_EXACT_THRESHOLD:
            exact_token_matches.append(LineMatchCandidate(poi, "NORMALIZED", float(score)))

    if len(exact_token_matches) == 1:
        return exact_token_matches[0], False
    elif len(exact_token_matches) > 1:
        return exact_token_matches[0], True  # Ambiguous

    # 3. Level 3 - Controlled fuzzy matching
    fuzzy_candidates: list[LineMatchCandidate] = []
    for poi in po_items:
        norm_po = normalize_line_desc(poi.description)
        score = fuzz.token_set_ratio(norm_inv, norm_po)
        if score >= LINE_FUZZY_THRESHOLD:
            fuzzy_candidates.append(LineMatchCandidate(poi, "FUZZY", float(score)))

    if not fuzzy_candidates:
        return None, False

    # Sort descending by score
    fuzzy_candidates.sort(key=lambda c: c.score, reverse=True)
    best = fuzzy_candidates[0]

    # Ambiguity check: if top 2 candidates have very close scores (within 5 points)
    if len(fuzzy_candidates) > 1 and (best.score - fuzzy_candidates[1].score) < 5:
        return best, True

    return best, False


def reconcile_invoice_line_items(
    db: Session, invoice: Invoice, po: PurchaseOrder, *, price_tolerance_pct: Decimal | None = None
) -> tuple[list[LineItemReconciliation], list[CheckResult]]:
    """Perform granular line-item matching, quantity verification, and price checking.

    Returns:
        reconciliations: List of LineItemReconciliation records.
        check_results: List of CheckResults for PO_LINE_ITEMS check.
    """
    if not po.items or not invoice.line_items:
        return [], [skipped(Check.PO_LINE_ITEMS, "No line items to compare between invoice and PO.")]

    tolerance_pct = price_tolerance_pct if price_tolerance_pct is not None else get_settings().po_line_price_tolerance_pct

    # Keep track of requested quantities per PO item in THIS invoice
    current_invoice_item_quantities: dict[UUID, Decimal] = {}
    reconciliations: list[LineItemReconciliation] = []
    issues: list[str] = []
    has_blocking_variance = False

    for line in invoice.line_items:
        inv_qty = line.quantity if line.quantity is not None else Decimal("0")
        inv_price = line.unit_price if line.unit_price is not None else Decimal("0")
        inv_total = line.total_amount if line.total_amount is not None else (inv_qty * inv_price)

        best_match, is_ambiguous = find_best_po_item_matches(line, list(po.items))

        if is_ambiguous:
            recon = LineItemReconciliation(
                invoice_id=invoice.id,
                invoice_line_item_id=line.id,
                purchase_order_item_id=best_match.po_item.id if best_match else None,
                status=LineMatchStatus.AMBIGUOUS.value,
                matching_method="AMBIGUOUS",
                matched_description=best_match.po_item.description if best_match else None,
                invoice_quantity=inv_qty,
                actual_line_amount=inv_total,
                explanation=f"Line item '{line.description}' matches multiple PO items ambiguously or appears bundled.",
            )
            reconciliations.append(recon)
            issues.append(f"Ambiguous match for line '{line.description}'")
            has_blocking_variance = True
            continue

        if not best_match:
            recon = LineItemReconciliation(
                invoice_id=invoice.id,
                invoice_line_item_id=line.id,
                purchase_order_item_id=None,
                status=LineMatchStatus.UNMATCHED.value,
                matching_method="NONE",
                matched_description=None,
                invoice_quantity=inv_qty,
                actual_line_amount=inv_total,
                explanation=f"Line item '{line.description}' does not correspond to any item on PO {po.po_number}.",
            )
            reconciliations.append(recon)
            issues.append(f"Unmatched item: '{line.description}'")
            has_blocking_variance = True
            continue

        matched_poi = best_match.po_item
        ordered_qty = matched_poi.quantity
        po_price = matched_poi.unit_price
        expected_total = inv_qty * po_price

        # Quantity accounting: historical allocated + previously counted lines in this invoice
        allocated_qty = consumed_po_item_quantity(db, matched_poi.id, exclude_invoice_id=invoice.id)
        already_in_this_invoice = current_invoice_item_quantities.get(matched_poi.id, Decimal("0"))
        remaining_qty = ordered_qty - allocated_qty - already_in_this_invoice

        current_invoice_item_quantities[matched_poi.id] = already_in_this_invoice + inv_qty

        # Price variance check
        price_var = abs(inv_price - po_price)
        price_mismatch = False
        if po_price > 0:
            variance_pct = price_var / po_price
            if variance_pct > tolerance_pct:
                price_mismatch = True

        # Status determination
        if inv_qty > remaining_qty:
            status = LineMatchStatus.QUANTITY_EXCEEDED.value
            explanation = (
                f"Invoice quantity ({inv_qty}) exceeds remaining PO quantity ({remaining_qty}) "
                f"for '{matched_poi.description}'."
            )
            issues.append(explanation)
            has_blocking_variance = True
        elif price_mismatch:
            status = LineMatchStatus.PRICE_MISMATCH.value
            explanation = (
                f"Unit price {inv_price} differs from PO price {po_price} by more than "
                f"{int(tolerance_pct * 100)}% for '{matched_poi.description}'."
            )
            issues.append(explanation)
            has_blocking_variance = True
        elif best_match.method == "FUZZY":
            status = LineMatchStatus.MATCHED_WITH_VARIANCE.value
            explanation = f"Fuzzy matched to '{matched_poi.description}' (confidence {best_match.score:.0f}%)."
        else:
            status = LineMatchStatus.MATCHED.value
            explanation = f"Matched to PO line '{matched_poi.description}'."

        recon = LineItemReconciliation(
            invoice_id=invoice.id,
            invoice_line_item_id=line.id,
            purchase_order_item_id=matched_poi.id,
            status=status,
            matching_method=best_match.method,
            matched_description=matched_poi.description,
            invoice_quantity=inv_qty,
            ordered_quantity=ordered_qty,
            allocated_quantity=allocated_qty,
            remaining_quantity=remaining_qty,
            invoice_unit_price=inv_price,
            po_unit_price=po_price,
            price_variance=price_var,
            expected_line_amount=expected_total,
            actual_line_amount=inv_total,
            explanation=explanation,
        )
        reconciliations.append(recon)

    if has_blocking_variance:
        msg = "Line-item reconciliation flagged issues: " + "; ".join(issues[:3])
        if len(issues) > 3:
            msg += f" and {len(issues) - 3} more."
        return reconciliations, [review(Check.PO_LINE_ITEMS, msg)]

    return reconciliations, [passed(Check.PO_LINE_ITEMS, "All invoice line items matched to PO items within permitted tolerances.")]


def persist_line_reconciliations(db: Session, reconciliations: list[LineItemReconciliation]) -> None:
    """Save line-item reconciliations atomically."""
    # Ensure line items have primary keys before saving reconciliations
    db.flush()
    for r in reconciliations:
        if not r.invoice_line_item_id:
            continue
        existing = db.scalar(
            select(LineItemReconciliation).where(
                LineItemReconciliation.invoice_line_item_id == r.invoice_line_item_id
            )
        )
        if existing:
            existing.purchase_order_item_id = r.purchase_order_item_id
            existing.status = r.status
            existing.matching_method = r.matching_method
            existing.matched_description = r.matched_description
            existing.invoice_quantity = r.invoice_quantity
            existing.ordered_quantity = r.ordered_quantity
            existing.allocated_quantity = r.allocated_quantity
            existing.remaining_quantity = r.remaining_quantity
            existing.unit_of_measure = r.unit_of_measure
            existing.invoice_unit_price = r.invoice_unit_price
            existing.po_unit_price = r.po_unit_price
            existing.price_variance = r.price_variance
            existing.expected_line_amount = r.expected_line_amount
            existing.actual_line_amount = r.actual_line_amount
            existing.explanation = r.explanation
        else:
            db.add(r)
    db.flush()


def allocate_po_line_items(
    db: Session, invoice: Invoice, *, allocated_by: str = "system"
) -> list[POLineAllocation]:
    """Reserve granular PO line quantities for an approved invoice under row locks.

    Orders lock acquisitions consistently:
    1. PurchaseOrder row lock (SELECT ... FOR UPDATE)
    2. PurchaseOrderItem rows locks in deterministic order (by item.id ASC)
    This prevents any possible deadlock when multiple concurrent invoices touch the same PO.
    Also aggregates multiple invoice lines that map to the same PO item to prevent intra-invoice oversubscription.
    """
    if not invoice.purchase_order_id or not invoice.line_items:
        return []

    po = db.scalar(
        select(PurchaseOrder).where(PurchaseOrder.id == invoice.purchase_order_id).with_for_update()
    )
    if not po or not po.items:
        return []

    # Deterministic lock ordering on PO items to prevent deadlocks
    po_item_ids = sorted([p.id for p in po.items])
    locked_po_items = list(
        db.scalars(
            select(PurchaseOrderItem)
            .where(PurchaseOrderItem.id.in_(po_item_ids))
            .order_by(PurchaseOrderItem.id.asc())
            .with_for_update()
        ).all()
    )
    po_items_by_id = {poi.id: poi for poi in locked_po_items}

    # Aggregate requested quantities per PO item in this invoice across all invoice lines
    line_recon_map: list[tuple[InvoiceLineItem, LineItemReconciliation, PurchaseOrderItem]] = []
    total_requested_per_po_item: dict[UUID, Decimal] = {}

    for line in invoice.line_items:
        recon = db.scalar(
            select(LineItemReconciliation).where(
                LineItemReconciliation.invoice_line_item_id == line.id
            )
        )
        if not recon or not recon.purchase_order_item_id:
            continue

        poi = po_items_by_id.get(recon.purchase_order_item_id)
        if not poi:
            continue

        qty = line.quantity if line.quantity is not None else Decimal("0")
        total_requested_per_po_item[poi.id] = total_requested_per_po_item.get(poi.id, Decimal("0")) + qty
        line_recon_map.append((line, recon, poi))

    # Verify each requested PO item has sufficient remaining balance across all lines of this invoice
    for poi_id, total_needed in total_requested_per_po_item.items():
        poi = po_items_by_id[poi_id]
        remaining = remaining_po_item_quantity(db, poi, exclude_invoice_id=invoice.id)
        if total_needed > remaining:
            raise ValueError(
                f"Invoice total requested quantity of {total_needed} exceeds remaining PO quantity of {remaining} for '{poi.description}'."
            )

    allocations: list[POLineAllocation] = []
    for line, recon, poi in line_recon_map:
        existing_alloc = db.scalar(
            select(POLineAllocation).where(
                POLineAllocation.invoice_line_item_id == line.id
            )
        )
        if existing_alloc and existing_alloc.status == "ACTIVE":
            allocations.append(existing_alloc)
            continue

        qty = line.quantity if line.quantity is not None else Decimal("0")
        amt = line.total_amount if line.total_amount is not None else (qty * (line.unit_price or Decimal("0")))

        alloc = existing_alloc or POLineAllocation(
            purchase_order_id=po.id,
            purchase_order_item_id=poi.id,
            invoice_id=invoice.id,
            invoice_line_item_id=line.id,
        )
        alloc.quantity = qty
        alloc.amount = amt
        alloc.status = "ACTIVE"
        alloc.allocated_by = allocated_by
        db.add(alloc)
        allocations.append(alloc)

    db.flush()
    return allocations


def backfill_historical_approved_allocations(db: Session) -> int:
    """Backfill granular line allocations and reconciliations for existing historical approved invoices."""
    approved_invoices = list(
        db.scalars(
            select(Invoice)
            .where(
                Invoice.decision_status == "APPROVED",
                Invoice.purchase_order_id.is_not(None),
            )
            .order_by(Invoice.uploaded_at.asc())
        ).all()
    )

    created_count = 0
    for inv in approved_invoices:
        po = inv.purchase_order
        if not po or not po.items or not inv.line_items:
            continue

        recons, _ = reconcile_invoice_line_items(db, inv, po)
        persist_line_reconciliations(db, recons)

        for line in inv.line_items:
            recon = next((r for r in recons if r.invoice_line_item_id == line.id), None)
            if not recon or not recon.purchase_order_item_id:
                continue

            existing = db.scalar(
                select(POLineAllocation).where(POLineAllocation.invoice_line_item_id == line.id)
            )
            if existing and existing.status == "ACTIVE":
                continue

            qty = line.quantity if line.quantity is not None else Decimal("0")
            amt = line.total_amount if line.total_amount is not None else (qty * (line.unit_price or Decimal("0")))

            alloc = existing or POLineAllocation(
                purchase_order_id=po.id,
                purchase_order_item_id=recon.purchase_order_item_id,
                invoice_id=inv.id,
                invoice_line_item_id=line.id,
            )
            alloc.quantity = qty
            alloc.amount = amt
            alloc.status = "ACTIVE"
            alloc.allocated_by = "history_backfill"
            db.add(alloc)
            created_count += 1

    db.commit()
    return created_count
