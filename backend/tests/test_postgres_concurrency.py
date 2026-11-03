"""PostgreSQL concurrency integration test for PO line allocations under row locks.

Verifies that two genuinely concurrent transactions on PostgreSQL:
- PO line quantity: 10
- Invoice A requests: 7
- Invoice B requests: 6
- Both attempt approval concurrently.
Result:
- Exactly one succeeds.
- The other raises ValueError / ConflictError due to insufficient PO item quantity.
- Total allocated quantity in PostgreSQL never exceeds 10.
- All database records remain consistent.
"""

import os
import threading
import time
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models.enums import DecisionStatus, LineMatchStatus
from app.models.invoice import Invoice, InvoiceLineItem, LineItemReconciliation
from app.models.vendor_po import POLineAllocation, PurchaseOrder, PurchaseOrderItem, Vendor
from app.services.line_item_reconciler import allocate_po_line_items, consumed_po_item_quantity, reconcile_invoice_line_items

PG_URL = os.environ.get("REAL_PG_URL") or "postgresql+psycopg://payflow:payflow@postgres:5432/payflow"


def test_postgres_concurrent_line_allocations_protected():
    engine = create_engine(PG_URL)
    SessionLocal = sessionmaker(bind=engine)

    # Setup isolated test data using Session 1
    with SessionLocal() as db_setup:
        test_uid = uuid4().hex[:6]
        vendor = Vendor(
            vendor_code=f"V{test_uid}",
            vendor_name=f"Concurrent Test Vendor {test_uid}",
            normalized_name=f"concurrent test vendor {test_uid}",
            gstin=f"27C{test_uid.upper()}1Z",
            status="ACTIVE",
            email="conc@example.com",
        )
        db_setup.add(vendor)
        db_setup.flush()

        po = PurchaseOrder(
            vendor_id=vendor.id,
            po_number=f"PO-CONC-{test_uid}",
            po_date=date(2026, 1, 1),
            total_amount=Decimal("10000.00"),
            currency="INR",
            status="ACTIVE",
        )
        db_setup.add(po)
        db_setup.flush()

        poi = PurchaseOrderItem(
            purchase_order_id=po.id,
            description="Concurrent High-End Server Rack",
            quantity=Decimal("10"),
            unit_price=Decimal("1000.00"),
            total_amount=Decimal("10000.00"),
        )
        db_setup.add(poi)
        db_setup.flush()

        # Create Invoice A (qty 7)
        inv_a = Invoice(
            vendor_id=vendor.id,
            purchase_order_id=po.id,
            invoice_number=f"INV-A-{test_uid}",
            currency="INR",
            total_amount=Decimal("7000.00"),
            subtotal=Decimal("7000.00"),
            tax_amount=Decimal("0.00"),
            decision_status=DecisionStatus.APPROVED.value,
            original_file_name="inv_a.pdf",
            stored_file_path="dummy_a.pdf",
            file_hash=f"hash_a_{test_uid}",
        )
        db_setup.add(inv_a)
        db_setup.flush()

        line_a = InvoiceLineItem(
            invoice_id=inv_a.id,
            description="Concurrent High-End Server Rack",
            quantity=Decimal("7"),
            unit_price=Decimal("1000.00"),
            total_amount=Decimal("7000.00"),
        )
        db_setup.add(line_a)
        db_setup.flush()
        inv_a.line_items = [line_a]

        recons_a, _ = reconcile_invoice_line_items(db_setup, inv_a, po)
        for r in recons_a:
            db_setup.add(r)

        # Create Invoice B (qty 6)
        inv_b = Invoice(
            vendor_id=vendor.id,
            purchase_order_id=po.id,
            invoice_number=f"INV-B-{test_uid}",
            currency="INR",
            total_amount=Decimal("6000.00"),
            subtotal=Decimal("6000.00"),
            tax_amount=Decimal("0.00"),
            decision_status=DecisionStatus.APPROVED.value,
            original_file_name="inv_b.pdf",
            stored_file_path="dummy_b.pdf",
            file_hash=f"hash_b_{test_uid}",
        )
        db_setup.add(inv_b)
        db_setup.flush()

        line_b = InvoiceLineItem(
            invoice_id=inv_b.id,
            description="Concurrent High-End Server Rack",
            quantity=Decimal("6"),
            unit_price=Decimal("1000.00"),
            total_amount=Decimal("6000.00"),
        )
        db_setup.add(line_b)
        db_setup.flush()
        inv_b.line_items = [line_b]

        recons_b, _ = reconcile_invoice_line_items(db_setup, inv_b, po)
        for r in recons_b:
            db_setup.add(r)

        db_setup.commit()

        vendor_id = vendor.id
        po_id = po.id
        poi_id = poi.id
        inv_a_id = inv_a.id
        inv_b_id = inv_b.id

    barrier = threading.Barrier(2)
    results = {}

    def attempt_allocate(inv_id, label):
        with SessionLocal() as session:
            try:
                inv = session.get(Invoice, inv_id)
                # Wait for both threads to hit this point together
                barrier.wait(timeout=5)
                # Now both call allocate_po_line_items concurrently
                allocs = allocate_po_line_items(session, inv, allocated_by=label)
                # Introduce a slight sleep before commit while holding the row lock
                time.sleep(0.1)
                session.commit()
                results[label] = ("SUCCESS", len(allocs))
            except Exception as e:
                session.rollback()
                results[label] = ("FAILED", str(e))

    thread_a = threading.Thread(target=attempt_allocate, args=(inv_a_id, "Thread-A-Qty7"))
    thread_b = threading.Thread(target=attempt_allocate, args=(inv_b_id, "Thread-B-Qty6"))

    thread_a.start()
    thread_b.start()
    thread_a.join()
    thread_b.join()

    # Exactly one must succeed and one must fail
    successes = [k for k, v in results.items() if v[0] == "SUCCESS"]
    failures = [k for k, v in results.items() if v[0] == "FAILED"]

    assert len(successes) == 1, f"Expected exactly 1 success, got {results}"
    assert len(failures) == 1, f"Expected exactly 1 failure, got {results}"
    assert "exceeds remaining PO quantity" in failures[0] or "exceeds remaining PO quantity" in results[failures[0]][1]

    # Verify final database state in fresh session
    with SessionLocal() as db_verify:
        try:
            consumed = consumed_po_item_quantity(db_verify, poi_id)
            # Consumed must be either 7 or 6, NEVER 13
            assert consumed in (Decimal("7"), Decimal("6")), f"Consumed quantity violated PO: {consumed}"
            allocs = list(
                db_verify.scalars(
                    select(POLineAllocation).where(POLineAllocation.purchase_order_item_id == poi_id)
                ).all()
            )
            assert len(allocs) == 1
            assert allocs[0].status == "ACTIVE"
        finally:
            # Clean up the test fixtures so they do not pollute PostgreSQL master data
            db_verify.rollback()
            from app.models.processing import AuditLog
            db_verify.query(POLineAllocation).filter(POLineAllocation.purchase_order_item_id == poi_id).delete(synchronize_session=False)
            db_verify.query(LineItemReconciliation).filter(LineItemReconciliation.invoice_id.in_([inv_a_id, inv_b_id])).delete(synchronize_session=False)
            db_verify.query(InvoiceLineItem).filter(InvoiceLineItem.invoice_id.in_([inv_a_id, inv_b_id])).delete(synchronize_session=False)
            db_verify.query(AuditLog).filter(AuditLog.invoice_id.in_([inv_a_id, inv_b_id])).delete(synchronize_session=False)
            db_verify.query(Invoice).filter(Invoice.id.in_([inv_a_id, inv_b_id])).delete(synchronize_session=False)
            db_verify.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == poi_id).delete(synchronize_session=False)
            db_verify.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).delete(synchronize_session=False)
            db_verify.query(Vendor).filter(Vendor.id == vendor_id).delete(synchronize_session=False)
            db_verify.commit()
