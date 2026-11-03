"""Tests verifying complete 90-invoice overview, source isolation, and master data."""

from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.invoice import Invoice
from app.models.vendor_po import Vendor, PurchaseOrder, POAllocation
from app.services.dashboard_service import get_stats
from app.services.analytics_service import get_operational_metrics


def test_portfolio_dataset_reconciliation(client: TestClient, db: Session):
    """Verify that portfolio statistics reconcile and separate LIVE_UPLOAD and SEED_HISTORY."""
    v = Vendor(vendor_code="V-TEST-90", vendor_name="Test Vendor 90", normalized_name="test vendor 90", is_demo=True)
    db.add(v)
    db.flush()

    from datetime import date
    po = PurchaseOrder(vendor_id=v.id, po_number="PO-TEST-90", po_date=date(2026, 1, 1), total_amount=Decimal("50000.00"), currency="INR", status="ACTIVE")
    db.add(po)
    db.flush()

    # Add 15 LIVE_UPLOAD invoices: 3 approved, 7 needs_review, 4 rejected, 1 failed
    for i in range(3):
        db.add(Invoice(vendor_id=v.id, purchase_order_id=po.id, invoice_number=f"LIVE-APP-{i}", total_amount=Decimal("1000.00"), source_origin="LIVE_UPLOAD", decision_status="APPROVED", processing_status="COMPLETED", original_file_name=f"live_app_{i}.pdf", stored_file_path=f"stored_l_a_{i}.pdf", file_hash=f"h_l_a_{i}"))
    for i in range(7):
        db.add(Invoice(vendor_id=v.id, purchase_order_id=po.id, invoice_number=f"LIVE-REV-{i}", total_amount=Decimal("1000.00"), source_origin="LIVE_UPLOAD", decision_status="NEEDS_REVIEW", processing_status="COMPLETED", original_file_name=f"live_rev_{i}.pdf", stored_file_path=f"stored_l_r_{i}.pdf", file_hash=f"h_l_r_{i}"))
    for i in range(4):
        db.add(Invoice(vendor_id=v.id, purchase_order_id=po.id, invoice_number=f"LIVE-REJ-{i}", total_amount=Decimal("1000.00"), source_origin="LIVE_UPLOAD", decision_status="REJECTED", processing_status="COMPLETED", original_file_name=f"live_rej_{i}.pdf", stored_file_path=f"stored_l_j_{i}.pdf", file_hash=f"h_l_j_{i}"))
    # 1 Technical failure
    db.add(Invoice(vendor_id=v.id, purchase_order_id=po.id, invoice_number=None, total_amount=None, source_origin="LIVE_UPLOAD", decision_status=None, processing_status="FAILED", original_file_name="corrupt.pdf", stored_file_path="stored_corrupt.pdf", file_hash="h_corrupt"))

    # Add 75 SEED_HISTORY invoices: 55 approved, 12 needs_review, 8 rejected
    for i in range(55):
        db.add(Invoice(vendor_id=v.id, purchase_order_id=po.id, invoice_number=f"HIST-APP-{i}", total_amount=Decimal("500.00"), source_origin="SEED_HISTORY", decision_status="APPROVED", processing_status="COMPLETED", original_file_name=f"hist_app_{i}.pdf", stored_file_path=f"stored_h_a_{i}.pdf", file_hash=f"h_h_a_{i}"))
    for i in range(12):
        db.add(Invoice(vendor_id=v.id, purchase_order_id=po.id, invoice_number=f"HIST-REV-{i}", total_amount=Decimal("500.00"), source_origin="SEED_HISTORY", decision_status="NEEDS_REVIEW", processing_status="COMPLETED", original_file_name=f"hist_rev_{i}.pdf", stored_file_path=f"stored_h_r_{i}.pdf", file_hash=f"h_h_r_{i}"))
    for i in range(8):
        db.add(Invoice(vendor_id=v.id, purchase_order_id=po.id, invoice_number=f"HIST-REJ-{i}", total_amount=Decimal("500.00"), source_origin="SEED_HISTORY", decision_status="REJECTED", processing_status="COMPLETED", original_file_name=f"hist_rej_{i}.pdf", stored_file_path=f"stored_h_j_{i}.pdf", file_hash=f"h_h_j_{i}"))

    db.commit()

    stats = get_stats(db)
    portfolio = stats["portfolio"]

    # Verify counts
    assert portfolio["all"]["total"] == 90
    assert portfolio["historical"]["total"] == 75
    assert portfolio["live"]["total"] == 15

    # Historical outcomes
    assert portfolio["historical"]["approved"] == 55
    assert portfolio["historical"]["needs_review"] == 12
    assert portfolio["historical"]["rejected"] == 8

    # Live outcomes
    assert portfolio["live"]["approved"] == 3
    assert portfolio["live"]["needs_review"] == 7
    assert portfolio["live"]["rejected"] == 4
    assert portfolio["live"]["failed"] == 1

    # Combined reconciles to 90
    assert portfolio["all"]["approved"] == 58
    assert portfolio["all"]["needs_review"] == 19
    assert portfolio["all"]["rejected"] == 12
    assert portfolio["all"]["failed"] == 1


def test_invoices_source_filtering(client: TestClient, db: Session):
    """Verify GET /api/v1/invoices supports source_origin filtering."""
    v = Vendor(vendor_code="V-TEST-SRC", vendor_name="Source Test Vendor", normalized_name="source test vendor", is_demo=True)
    db.add(v)
    db.flush()

    for i in range(15):
        db.add(Invoice(vendor_id=v.id, invoice_number=f"LIVE-{i}", total_amount=Decimal("100"), source_origin="LIVE_UPLOAD", original_file_name=f"f_{i}.pdf", stored_file_path=f"stored_f_{i}.pdf", file_hash=f"hl_{i}"))
    for i in range(75):
        db.add(Invoice(vendor_id=v.id, invoice_number=f"HIST-{i}", total_amount=Decimal("100"), source_origin="SEED_HISTORY", original_file_name=f"h_{i}.pdf", stored_file_path=f"stored_h_{i}.pdf", file_hash=f"hh_{i}"))
    db.commit()

    # Default should return live uploads
    res_def = client.get("/api/v1/invoices?page_size=100")
    assert res_def.status_code == 200
    assert res_def.json()["meta"]["total"] == 15

    # Explicit live
    res_live = client.get("/api/v1/invoices?source_origin=LIVE_UPLOAD&page_size=100")
    assert res_live.status_code == 200
    assert res_live.json()["meta"]["total"] == 15

    # Historical
    res_hist = client.get("/api/v1/invoices?source_origin=SEED_HISTORY&page_size=100")
    assert res_hist.status_code == 200
    assert res_hist.json()["meta"]["total"] == 75

    # All
    res_all = client.get("/api/v1/invoices?source_origin=ALL&page_size=100")
    assert res_all.status_code == 200
    assert res_all.json()["meta"]["total"] == 90


def test_developer_analytics_endpoint(client: TestClient, db: Session):
    """Verify GET /api/v1/dashboard/developer-analytics returns telemetry and formulas."""
    res = client.get("/api/v1/dashboard/developer-analytics?days=30")
    assert res.status_code == 200
    data = res.json()["data"]
    assert "reliability" in data
    assert "speed" in data
    assert "ai_usage" in data
    assert "technical_success_formula" in data["reliability"]
    assert "failed_before_extraction" in data["reliability"]
    assert "tokens_available" in data["ai_usage"]
