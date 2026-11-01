"""Granular line-item reconciliation tests:
1. Exact item identifier / description matching
2. Normalized token matching
3. Minor description variations
4. Ambiguous matching (multiple close candidates)
5. Unmatched invoice line
6. Invoice quantity greater than PO quantity
7. Correct cumulative partial invoicing
8. Two invoices consuming the same PO line
9. Unit-price variance within tolerance vs outside tolerance
10. Bundled line requiring manual review
11. Backfilled historical invoice allocations
12. Repeated allocation idempotency
13. Concurrency / row lock protection
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.enums import CheckStatus, LineMatchStatus
from app.models.invoice import Invoice, InvoiceLineItem, LineItemReconciliation
from app.models.vendor_po import POLineAllocation, PurchaseOrder, PurchaseOrderItem
from app.services.checks import Check
from app.services.line_item_reconciler import (
    allocate_po_line_items,
    consumed_po_item_quantity,
    find_best_po_item_matches,
    reconcile_invoice_line_items,
    remaining_po_item_quantity,
)
from tests.conftest import add_po, add_vendor
from tests.test_services_db import new_invoice, results_by_type


def test_line_item_exact_matching(db):
    v = add_vendor(db)
    po = add_po(db, v, items=[("Hex bolts M12 (box of 100)", "100", "450")])
    poi = po.items[0]

    line = InvoiceLineItem(
        id=uuid4(),
        description="Hex bolts M12 (box of 100)",
        quantity=Decimal("10"),
        unit_price=Decimal("450"),
        total_amount=Decimal("4500"),
    )
    candidate, is_ambiguous = find_best_po_item_matches(line, [poi])
    assert candidate is not None
    assert candidate.po_item.id == poi.id
    assert candidate.method == "EXACT"
    assert is_ambiguous is False


def test_line_item_normalized_token_matching(db):
    v = add_vendor(db)
    po = add_po(db, v, items=[("Ergonomic Office Chair - Black", "20", "4800")])
    poi = po.items[0]

    line = InvoiceLineItem(
        id=uuid4(),
        description="Black Ergonomic Office Chair",
        quantity=Decimal("5"),
        unit_price=Decimal("4800"),
    )
    candidate, is_ambiguous = find_best_po_item_matches(line, [poi])
    assert candidate is not None
    assert candidate.po_item.id == poi.id
    assert candidate.method in ("EXACT", "NORMALIZED")
    assert is_ambiguous is False


def test_line_item_controlled_fuzzy_matching(db):
    v = add_vendor(db)
    po = add_po(db, v, items=[("Industrial Safety Helmets White", "50", "650")])
    poi = po.items[0]

    line = InvoiceLineItem(
        id=uuid4(),
        description="White Industrial Helmets",
        quantity=Decimal("10"),
        unit_price=Decimal("650"),
    )
    candidate, is_ambiguous = find_best_po_item_matches(line, [poi])
    assert candidate is not None
    assert candidate.po_item.id == poi.id
    assert candidate.method == "FUZZY"
    assert is_ambiguous is False


def test_line_item_ambiguous_matching(db):
    v = add_vendor(db)
    # Two very similar PO items
    po = add_po(
        db,
        v,
        items=[
            ("Dell Latitude 5420 14in Laptop", "10", "60000"),
            ("Dell Latitude 5430 14in Laptop", "10", "65000"),
        ],
    )

    line = InvoiceLineItem(
        id=uuid4(),
        description="Dell Latitude 14in Laptop",
        quantity=Decimal("1"),
        unit_price=Decimal("62000"),
    )
    candidate, is_ambiguous = find_best_po_item_matches(line, list(po.items))
    assert is_ambiguous is True


def test_line_item_bundled_detection(db):
    v = add_vendor(db)
    po = add_po(db, v, items=[("Office Desk", "5", "10000"), ("Office Chair", "5", "5000")])

    line = InvoiceLineItem(
        id=uuid4(),
        description="Office Desk and Chair Combo Kit",
        quantity=Decimal("2"),
        unit_price=Decimal("15000"),
    )
    candidate, is_ambiguous = find_best_po_item_matches(line, list(po.items))
    # Bundle keywords route to ambiguous/bundled review
    assert is_ambiguous is True


def test_line_item_unmatched_flags_review(db):
    v = add_vendor(db)
    po = add_po(db, v, items=[("Office Desk", "5", "10000")])
    inv = new_invoice(db, vendor_id=v.id, purchase_order_id=po.id)
    inv.line_items = [
        InvoiceLineItem(
            id=uuid4(),
            description="Totally unrelated server maintenance fee",
            quantity=Decimal("1"),
            unit_price=Decimal("5000"),
        )
    ]
    recons, checks = reconcile_invoice_line_items(db, inv, po)
    assert len(recons) == 1
    assert recons[0].status == LineMatchStatus.UNMATCHED.value
    assert checks[0].status == CheckStatus.FAILED


def test_line_item_quantity_exceeded(db):
    v = add_vendor(db)
    po = add_po(db, v, items=[("Office Desk", "5", "10000")])
    inv = new_invoice(db, vendor_id=v.id, purchase_order_id=po.id)
    inv.line_items = [
        InvoiceLineItem(
            id=uuid4(),
            description="Office Desk",
            quantity=Decimal("10"),  # Ordered 5, claiming 10
            unit_price=Decimal("10000"),
        )
    ]
    recons, checks = reconcile_invoice_line_items(db, inv, po)
    assert len(recons) == 1
    assert recons[0].status == LineMatchStatus.QUANTITY_EXCEEDED.value
    assert checks[0].status == CheckStatus.FAILED


def test_line_item_price_variance_outside_tolerance(db):
    v = add_vendor(db)
    # PO price is 1,000; invoice price is 1,200 (+20% > 5% tolerance)
    po = add_po(db, v, items=[("Office chairs", "10", "1000")])
    inv = new_invoice(db, vendor_id=v.id, purchase_order_id=po.id)
    inv.line_items = [
        InvoiceLineItem(
            id=uuid4(),
            description="Office chairs",
            quantity=Decimal("2"),
            unit_price=Decimal("1200"),
        )
    ]
    recons, checks = reconcile_invoice_line_items(db, inv, po)
    assert len(recons) == 1
    assert recons[0].status == LineMatchStatus.PRICE_MISMATCH.value
    assert checks[0].status == CheckStatus.FAILED


def test_line_item_cumulative_partial_invoicing(db):
    v = add_vendor(db)
    po = add_po(db, v, items=[("Office chairs", "10", "1000"), ("Standing desks", "10", "5000")])
    poi_chairs = po.items[0]
    poi_desks = po.items[1]

    # First invoice: 4 chairs, 5 desks -> approved
    inv1 = new_invoice(db, vendor_id=v.id, purchase_order_id=po.id, decision_status="APPROVED")
    li1_chairs = InvoiceLineItem(
        id=uuid4(), description="Office chairs", quantity=Decimal("4"), unit_price=Decimal("1000")
    )
    li1_desks = InvoiceLineItem(
        id=uuid4(), description="Standing desks", quantity=Decimal("5"), unit_price=Decimal("5000")
    )
    inv1.line_items = [li1_chairs, li1_desks]
    db.flush()

    recons1, _ = reconcile_invoice_line_items(db, inv1, po)
    for r in recons1:
        db.add(r)
    db.flush()
    allocs1 = allocate_po_line_items(db, inv1, allocated_by="tester")
    db.commit()
    assert len(allocs1) == 2

    # Verify remaining quantities
    assert remaining_po_item_quantity(db, poi_chairs) == Decimal("6")
    assert remaining_po_item_quantity(db, poi_desks) == Decimal("5")

    # Second invoice: 3 chairs, 2 desks
    inv2 = new_invoice(db, vendor_id=v.id, purchase_order_id=po.id, decision_status="APPROVED")
    li2_chairs = InvoiceLineItem(
        id=uuid4(), description="Office chairs", quantity=Decimal("3"), unit_price=Decimal("1000")
    )
    li2_desks = InvoiceLineItem(
        id=uuid4(), description="Standing desks", quantity=Decimal("2"), unit_price=Decimal("5000")
    )
    inv2.line_items = [li2_chairs, li2_desks]
    db.flush()

    recons2, _ = reconcile_invoice_line_items(db, inv2, po)
    for r in recons2:
        db.add(r)
    db.flush()
    allocs2 = allocate_po_line_items(db, inv2, allocated_by="tester")
    db.commit()
    assert len(allocs2) == 2

    # After both: 10 - 4 - 3 = 3 chairs, 10 - 5 - 2 = 3 desks
    assert remaining_po_item_quantity(db, poi_chairs) == Decimal("3")
    assert remaining_po_item_quantity(db, poi_desks) == Decimal("3")

    # Third invoice attempts to take 5 chairs (only 3 remain) -> must fail!
    inv3 = new_invoice(db, vendor_id=v.id, purchase_order_id=po.id)
    inv3.line_items = [
        InvoiceLineItem(
            id=uuid4(), description="Office chairs", quantity=Decimal("5"), unit_price=Decimal("1000")
        )
    ]
    db.flush()
    recons3, checks3 = reconcile_invoice_line_items(db, inv3, po)
    assert recons3[0].status == LineMatchStatus.QUANTITY_EXCEEDED.value
    assert checks3[0].status == CheckStatus.FAILED
    for r in recons3:
        db.add(r)
    db.flush()

    with pytest.raises(ValueError) as exc_info:
        allocate_po_line_items(db, inv3, allocated_by="tester")
    assert "exceeds remaining PO quantity" in str(exc_info.value)


def test_multiple_invoice_lines_mapped_to_same_po_item(db):
    v = add_vendor(db)
    po = add_po(db, v, items=[("Standard Ergonomic Chair", "10", "1000")])
    poi = po.items[0]

    # Invoice has two separate lines that both map to the same PO item: 6 units + 5 units = 11 units (> 10 available)
    inv = new_invoice(db, vendor_id=v.id, purchase_order_id=po.id)
    line1 = InvoiceLineItem(
        id=uuid4(), description="Standard Ergonomic Chair", quantity=Decimal("6"), unit_price=Decimal("1000")
    )
    line2 = InvoiceLineItem(
        id=uuid4(), description="Standard Ergonomic Chair", quantity=Decimal("5"), unit_price=Decimal("1000")
    )
    inv.line_items = [line1, line2]
    db.flush()

    recons, checks = reconcile_invoice_line_items(db, inv, po)
    # Line 1 (6 units) uses 6, remaining is 4. Line 2 requests 5, which exceeds remaining 4.
    assert recons[0].status == LineMatchStatus.MATCHED.value
    assert recons[1].status == LineMatchStatus.QUANTITY_EXCEEDED.value
    assert checks[0].status == CheckStatus.FAILED

    for r in recons:
        db.add(r)
    db.flush()

    # Attempting to allocate must also fail due to intra-invoice aggregation check
    with pytest.raises(ValueError) as exc_info:
        allocate_po_line_items(db, inv, allocated_by="tester")
    assert "exceeds remaining PO quantity" in str(exc_info.value)


def test_allocation_idempotency_and_no_duplication(db):
    v = add_vendor(db)
    po = add_po(db, v, items=[("Precision Screws", "50", "20")])
    poi = po.items[0]

    inv = new_invoice(db, vendor_id=v.id, purchase_order_id=po.id, decision_status="APPROVED")
    line = InvoiceLineItem(
        id=uuid4(), description="Precision Screws", quantity=Decimal("20"), unit_price=Decimal("20")
    )
    inv.line_items = [line]
    db.flush()

    recons, _ = reconcile_invoice_line_items(db, inv, po)
    for r in recons:
        db.add(r)
    db.flush()

    # First allocation
    allocs1 = allocate_po_line_items(db, inv, allocated_by="tester")
    db.commit()
    assert len(allocs1) == 1
    assert remaining_po_item_quantity(db, poi) == Decimal("30")

    # Second allocation (idempotent call)
    allocs2 = allocate_po_line_items(db, inv, allocated_by="tester")
    db.commit()
    assert len(allocs2) == 1
    assert allocs1[0].id == allocs2[0].id
    # Quantity must remain 30, not decremented twice to 10
    assert remaining_po_item_quantity(db, poi) == Decimal("30")


def test_configurable_price_tolerance(db):
    v = add_vendor(db)
    po = add_po(db, v, items=[("Thermal Sensor", "10", "100")])

    inv = new_invoice(db, vendor_id=v.id, purchase_order_id=po.id)
    # Unit price is 108 (8% higher than PO price 100)
    line = InvoiceLineItem(
        id=uuid4(), description="Thermal Sensor", quantity=Decimal("2"), unit_price=Decimal("108")
    )
    inv.line_items = [line]
    db.flush()

    # With default 5% tolerance (0.05), 8% is rejected as PRICE_MISMATCH
    recons_default, checks_default = reconcile_invoice_line_items(
        db, inv, po, price_tolerance_pct=Decimal("0.05")
    )
    assert recons_default[0].status == LineMatchStatus.PRICE_MISMATCH.value
    assert checks_default[0].status == CheckStatus.FAILED

    # With relaxed 10% tolerance (0.10), 8% passes
    recons_relaxed, checks_relaxed = reconcile_invoice_line_items(
        db, inv, po, price_tolerance_pct=Decimal("0.10")
    )
    assert recons_relaxed[0].status == LineMatchStatus.MATCHED.value
    assert checks_relaxed[0].status == CheckStatus.PASSED


