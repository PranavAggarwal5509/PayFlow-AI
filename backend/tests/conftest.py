"""Test harness: SQLite database, inline execution, fake LLM, generated PDFs."""

import os
import tempfile
import warnings
from datetime import date
from decimal import Decimal
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="payflow-tests-"))
os.environ.update(
    ENVIRONMENT="test",
    DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}",
    UPLOAD_DIR=str(_TMP / "uploads"),
    GEMINI_API_KEY="",
    GEMINI_MAX_RETRIES="2",
)
warnings.filterwarnings("ignore", message="Dialect sqlite\\+pysqlite does \\*not\\* support Decimal")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.dependencies.providers import get_llm  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.database.base import Base  # noqa: E402
from app.database.session import get_engine, get_session_factory  # noqa: E402
from app.main import app  # noqa: E402
from app.models import PurchaseOrder, PurchaseOrderItem, Vendor  # noqa: E402
from app.utils.normalize import normalize_vendor_name  # noqa: E402
from tests.pdf_factory import make_pdf  # noqa: E402


class FakeLLM:
    """Stand-in for Gemini. Tests set `payload` (or `error`) before uploading."""

    def __init__(self) -> None:
        self.payload: dict | None = None
        self.error: Exception | None = None
        self.calls = 0

    def extract_invoice(self, document_text: str) -> dict:
        self.calls += 1
        if self.error:
            raise self.error
        assert self.payload is not None, "test did not set FakeLLM.payload"
        return self.payload


@pytest.fixture(autouse=True)
def _reset_database():
    Base.metadata.drop_all(get_engine())
    Base.metadata.create_all(get_engine())
    yield


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
def db() -> Session:
    with get_session_factory()() as session:
        yield session


@pytest.fixture
def llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def client(llm: FakeLLM) -> TestClient:
    app.dependency_overrides[get_llm] = lambda: llm
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


GSTIN_ACME = "27AABCA1234A1Z5"


def add_vendor(db: Session, name="Acme Supplies Pvt Ltd", gstin=GSTIN_ACME, status="ACTIVE", code=None):
    vendor = Vendor(
        vendor_code=code or f"V-{abs(hash(name)) % 10000:04d}",
        vendor_name=name,
        normalized_name=normalize_vendor_name(name),
        gstin=gstin,
        status=status,
        email="ap@example.com",
    )
    db.add(vendor)
    db.commit()
    return vendor


def add_po(db: Session, vendor: Vendor, number="PO-1001", total="100000.00", currency="INR",
           status="ACTIVE", items=None):  # fmt: skip
    po = PurchaseOrder(
        po_number=number, vendor_id=vendor.id, po_date=date(2026, 1, 5), currency=currency,
        total_amount=Decimal(total), status=status, description="Test PO",
    )  # fmt: skip
    for desc, qty, price in items or []:
        po.items.append(
            PurchaseOrderItem(
                description=desc, quantity=Decimal(qty), unit_price=Decimal(price),
                total_amount=Decimal(qty) * Decimal(price),
            )
        )
    db.add(po)
    db.commit()
    return po


def invoice_payload(**overrides) -> dict:
    """A fully consistent invoice that should be APPROVED against `add_vendor` + `add_po`."""
    payload = {
        "vendor_name": "Acme Supplies Pvt Ltd",
        "vendor_gstin": GSTIN_ACME,
        "invoice_number": "INV-2026-001",
        "invoice_date": "2026-02-10",
        "due_date": "2026-03-10",
        "purchase_order_number": "PO-1001",
        "currency": "INR",
        "subtotal": "10000.00",
        "tax_amount": "1800.00",
        "total_amount": "11800.00",
        "line_items": [
            {"description": "Office chairs", "quantity": "10", "unit_price": "1000.00",
             "tax_percentage": "18", "total_amount": "10000.00"},
        ],  # fmt: skip
    }
    payload.update(overrides)
    return payload


def upload(client: TestClient, llm: FakeLLM, payload: dict, *, text: str | None = None,
           filename="invoice.pdf") -> dict:  # fmt: skip
    llm.payload = payload
    pdf = make_pdf(text or f"Invoice {payload.get('invoice_number')} {payload.get('total_amount')} " * 8)
    response = client.post(
        "/api/v1/invoices/upload", files={"file": (filename, pdf, "application/pdf")}
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def invoice_detail(client: TestClient, invoice_id: str) -> dict:
    response = client.get(f"/api/v1/invoices/{invoice_id}")
    assert response.status_code == 200, response.text
    return response.json()["data"]
