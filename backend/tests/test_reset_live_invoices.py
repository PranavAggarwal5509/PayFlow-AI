"""Automated unit and integration tests for reset_live_invoices utility."""

from decimal import Decimal
from pathlib import Path
from sqlalchemy.orm import Session

from app.models.enums import DecisionStatus, ProcessingStatus, RunStatus, Stage, StageStatus
from app.models.invoice import Invoice, InvoiceLineItem, LineItemReconciliation
from app.models.processing import AuditLog, Decision, ProcessingRun, Review, StageEvent, ValidationResult
from app.models.vendor_po import POAllocation, POLineAllocation, PurchaseOrder, PurchaseOrderItem, Vendor
from scripts.reset_live_invoices import (
    EXPECTED_CONFIRM_STRING,
    execute_deletion,
    find_safe_pdfs_to_remove,
    get_live_invoice_inventory,
)


def test_reset_live_invoices_dry_run_and_execution(db: Session, tmp_path: Path):
    """Test that reset utility deletes only LIVE_UPLOAD records and preserves SEED_HISTORY and master data."""
    # 1. Create a Vendor and PO
    vendor = Vendor(vendor_code="V-TEST-RESET", vendor_name="Reset Test Vendor", normalized_name="reset test vendor", is_demo=True)
    db.add(vendor)
    db.flush()

    from datetime import date
    po = PurchaseOrder(vendor_id=vendor.id, po_number="PO-TEST-RESET", po_date=date(2026, 1, 1), total_amount=Decimal("10000.00"), currency="INR", status="ACTIVE")
    db.add(po)
    db.flush()

    po_item = PurchaseOrderItem(purchase_order_id=po.id, description="Item 1", quantity=Decimal("10"), unit_price=Decimal("1000.00"), total_amount=Decimal("10000.00"))
    db.add(po_item)
    db.flush()

    # 2. Add 1 SEED_HISTORY invoice
    hist_pdf = tmp_path / "hist.pdf"
    hist_pdf.write_bytes(b"%PDF-1.4 historical")
    inv_hist = Invoice(vendor_id=vendor.id, purchase_order_id=po.id, invoice_number="HIST-001", total_amount=Decimal("5000.00"), source_origin="SEED_HISTORY", processing_status="COMPLETED", decision_status="APPROVED", original_file_name="hist.pdf", stored_file_path="hist.pdf", file_hash="hash_h")
    db.add(inv_hist)
    db.flush()

    hist_alloc = POAllocation(purchase_order_id=po.id, invoice_id=inv_hist.id, amount=Decimal("5000.00"), status="COMMITTED", allocated_by="seed")
    db.add(hist_alloc)
    db.flush()

    # 3. Add 2 LIVE_UPLOAD invoices with dependent relational data
    live_pdf_1 = tmp_path / "live1.pdf"
    live_pdf_1.write_bytes(b"%PDF-1.4 live 1")
    inv_live_1 = Invoice(vendor_id=vendor.id, purchase_order_id=po.id, invoice_number="LIVE-001", total_amount=Decimal("2000.00"), source_origin="LIVE_UPLOAD", processing_status="COMPLETED", decision_status="APPROVED", original_file_name="live1.pdf", stored_file_path="live1.pdf", file_hash="hash_l1", visual_evidence={"boxes": []})
    db.add(inv_live_1)
    db.flush()

    live_line_1 = InvoiceLineItem(invoice_id=inv_live_1.id, position=1, description="Live Item 1", quantity=Decimal("2"), unit_price=Decimal("1000.00"), total_amount=Decimal("2000.00"))
    db.add(live_line_1)
    db.flush()

    live_alloc_1 = POAllocation(purchase_order_id=po.id, invoice_id=inv_live_1.id, amount=Decimal("2000.00"), status="COMMITTED", allocated_by="rule_engine")
    db.add(live_alloc_1)
    live_line_alloc_1 = POLineAllocation(purchase_order_id=po.id, purchase_order_item_id=po_item.id, invoice_id=inv_live_1.id, invoice_line_item_id=live_line_1.id, quantity=Decimal("2"), amount=Decimal("2000.00"))
    db.add(live_line_alloc_1)
    recon_1 = LineItemReconciliation(invoice_id=inv_live_1.id, invoice_line_item_id=live_line_1.id, purchase_order_item_id=po_item.id, status="EXACT_MATCH", matching_method="EXACT")
    db.add(recon_1)

    run_1 = ProcessingRun(invoice_id=inv_live_1.id, run_number=1, status=RunStatus.COMPLETED.value)
    db.add(run_1)
    db.flush()

    stage_1 = StageEvent(run_id=run_1.id, stage=Stage.AI_EXTRACTION.value, status=StageStatus.COMPLETED.value)
    db.add(stage_1)
    dec_1 = Decision(invoice_id=inv_live_1.id, processing_run_id=run_1.id, status=DecisionStatus.APPROVED.value, reasons=["All checks passed"])
    db.add(dec_1)
    audit_1 = AuditLog(invoice_id=inv_live_1.id, processing_run_id=run_1.id, action="DECISION", actor_type="SYSTEM", actor_id="rule_engine")
    db.add(audit_1)

    # Live Invoice 2: Needs review
    live_pdf_2 = tmp_path / "live2.pdf"
    live_pdf_2.write_bytes(b"%PDF-1.4 live 2")
    inv_live_2 = Invoice(vendor_id=vendor.id, purchase_order_id=po.id, invoice_number="LIVE-002", total_amount=Decimal("1500.00"), source_origin="LIVE_UPLOAD", processing_status="COMPLETED", decision_status="NEEDS_REVIEW", original_file_name="live2.pdf", stored_file_path="live2.pdf", file_hash="hash_l2")
    db.add(inv_live_2)
    db.flush()

    review_2 = Review(invoice_id=inv_live_2.id, review_status="PENDING", issue_type="SUSPECTED_DUPLICATE")
    db.add(review_2)
    val_2 = ValidationResult(invoice_id=inv_live_2.id, processing_run_id=run_1.id, validation_type="DUPLICATE_CHECK", status="FAILED", impact="REJECT", message="Duplicate check failed")
    db.add(val_2)

    db.commit()

    # 4. Inventory / Dry Run
    inventory = get_live_invoice_inventory(db)
    assert inventory["live_invoices"] == 2
    assert inventory["line_items"] == 1
    assert inventory["processing_runs"] == 1
    assert inventory["stage_events"] == 1
    assert inventory["decisions"] == 1
    assert inventory["reviews"] == 1
    assert inventory["audit_logs"] == 1
    assert inventory["po_allocations"] == 1
    assert inventory["po_line_allocations"] == 1
    assert inventory["visual_evidence"] == 1
    assert set(inventory["stored_pdf_paths"]) == {"live1.pdf", "live2.pdf"}

    safe_pdfs = find_safe_pdfs_to_remove(db, inventory["stored_pdf_paths"], tmp_path)
    assert set(p.name for p in safe_pdfs) == {"live1.pdf", "live2.pdf"}

    # 5. Execute deletion
    execute_deletion(db, inventory, safe_pdfs)

    # 6. Verify post-deletion state
    post_inventory = get_live_invoice_inventory(db)
    assert post_inventory["live_invoices"] == 0

    # Verify SEED_HISTORY is intact
    remaining_invoices = db.query(Invoice).all()
    assert len(remaining_invoices) == 1
    assert remaining_invoices[0].invoice_number == "HIST-001"
    assert remaining_invoices[0].source_origin == "SEED_HISTORY"

    # Verify historical allocation is intact
    remaining_allocs = db.query(POAllocation).all()
    assert len(remaining_allocs) == 1
    assert remaining_allocs[0].invoice_id == inv_hist.id

    # Verify master data is intact
    assert db.query(Vendor).filter(Vendor.id == vendor.id).count() == 1
    assert db.query(PurchaseOrder).filter(PurchaseOrder.id == po.id).count() == 1

    # Verify files
    assert not live_pdf_1.exists()
    assert not live_pdf_2.exists()
    assert hist_pdf.exists()
