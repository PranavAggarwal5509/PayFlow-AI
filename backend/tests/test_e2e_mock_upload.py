import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.database.session import get_engine, get_session_factory
from app.database.base import Base
from app.main import app
from app.api.dependencies.providers import get_llm
from app.services.llm_extractor import MockLLMProvider
from app.core.security import get_current_user
from tests.conftest import TEST_ADMIN, add_vendor
from app.models import PurchaseOrder, PurchaseOrderItem
from decimal import Decimal
from datetime import date


def test_end_to_end_upload_with_mock_provider(tmp_path):
    # Setup test DB tables
    Base.metadata.drop_all(get_engine())
    Base.metadata.create_all(get_engine())

    with get_session_factory()() as db:
        vendor = add_vendor(db, name="Acme Industrial Supplies Pvt Ltd", gstin="27AABCA1001A1ZU", code="V-1001")
        # Verified remittance details on file (the sample PDF prints the same account).
        vendor.bank_account_number, vendor.bank_ifsc = "50200010017037", "YESB0001001"
        po = PurchaseOrder(
            po_number="PO-2026-0001",
            vendor_id=vendor.id,
            po_date=date(2026, 4, 2),
            currency="INR",
            total_amount=Decimal("300000.00"),
            status="ACTIVE",
            description="Industrial fasteners",
        )
        po.items.append(
            PurchaseOrderItem(description="Hex bolts M12 (box of 100)", quantity=Decimal("400"), unit_price=Decimal("450"), total_amount=Decimal("180000"))
        )
        po.items.append(
            PurchaseOrderItem(description="Safety helmets", quantity=Decimal("300"), unit_price=Decimal("650"), total_amount=Decimal("195000"))
        )
        db.add(po)
        db.commit()

    # Configure app to use MockLLMProvider
    mock_llm = MockLLMProvider()
    app.dependency_overrides[get_llm] = lambda: mock_llm
    app.dependency_overrides[get_current_user] = lambda: TEST_ADMIN

    pdf_path = Path(__file__).resolve().parent.parent.parent / "sample_data" / "invoices" / "01_valid_invoice.pdf"
    assert pdf_path.exists(), "01_valid_invoice.pdf must exist"

    with TestClient(app) as client:
        with open(pdf_path, "rb") as f:
            resp = client.post(
                "/api/v1/invoices/upload",
                files={"file": ("01_valid_invoice.pdf", f, "application/pdf")},
            )
        assert resp.status_code == 201
        data = resp.json()["data"]
        invoice_id = data["invoice_id"]
        run_id = data["run_id"]

        # Run pipeline stages inline as executed in WORKFLOW_MODE=inline
        run_resp = client.get(f"/api/v1/runs/{run_id}")
        assert run_resp.status_code == 200

        # Query the invoice detail to verify real DB persistence and deterministic decision
        inv_resp = client.get(f"/api/v1/invoices/{invoice_id}")
        assert inv_resp.status_code == 200
        inv_data = inv_resp.json()["data"]

        assert inv_data["invoice_number"] == "ACM/2026/1042"
        assert inv_data["decision_status"] == "APPROVED"
        assert inv_data["total_amount"] == "114460.00"
        assert len(inv_data["line_items"]) == 2
        assert inv_data["purchase_order"]["po_number"] == "PO-2026-0001"
        assert inv_data["purchase_order"]["remaining_balance"] is not None

    app.dependency_overrides.clear()

