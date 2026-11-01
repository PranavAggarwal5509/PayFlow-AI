"""End-to-end API tests (upload → inline workflow → decision → review), Gemini mocked."""

from decimal import Decimal
from uuid import UUID
import pytest

from app.core.errors import TransientError
from app.models import AuditLog, Invoice, POAllocation
from app.services import po_matcher
from tests.conftest import (
    add_po,
    add_vendor,
    invoice_detail,
    invoice_payload,
    upload,
)  # fmt: skip
from tests.test_services_db import new_invoice
from tests.pdf_factory import make_corrupted_pdf, make_image_only_pdf, make_pdf


@pytest.fixture
def world(db):
    vendor = add_vendor(db)
    po = add_po(db, vendor, items=[("Office chairs", "10", "1000")])
    return vendor, po


def reasons(detail):
    return [r["message"] for r in detail["decision"]["reasons"] if r["severity"] != "INFO"]


# ------------------------------------------------------------------- scenarios
def test_demo1_valid_invoice_is_approved(client, llm, world, db):
    result = upload(client, llm, invoice_payload())
    d = invoice_detail(client, result["invoice_id"])
    print("DEMO1 ERROR:", d.get("error_message"), d.get("runs"))
    assert d["processing_status"] == "COMPLETED"
    assert d["decision_status"] == "APPROVED", reasons(d)
    assert d["vendor"]["vendor_name"] == "Acme Supplies Pvt Ltd"
    assert d["purchase_order"]["remaining_balance"] == "88200.00"  # 100000 - 11800 consumed
    assert len(d["line_items"]) == 1 and d["extraction_method"] == "TEXT"
    assert {v["status"] for v in d["validations"]} == {"PASSED"} or any(
        v["status"] == "SKIPPED" for v in d["validations"]
    )
    assert db.query(POAllocation).count() == 1


def test_demo2_exact_duplicate_pdf_rejected(client, llm, world):
    pdf = make_pdf("Invoice INV-2026-001 total 11800 " * 6)
    llm.payload = invoice_payload()
    first = client.post("/api/v1/invoices/upload", files={"file": ("a.pdf", pdf, "application/pdf")})
    second = client.post("/api/v1/invoices/upload", files={"file": ("b.pdf", pdf, "application/pdf")})
    d1 = invoice_detail(client, first.json()["data"]["invoice_id"])
    d2 = invoice_detail(client, second.json()["data"]["invoice_id"])
    assert d1["decision_status"] == "APPROVED"
    assert d2["decision_status"] == "REJECTED"
    assert any("exact file was already uploaded" in m for m in reasons(d2))


def test_business_duplicate_with_different_pdf_rejected(client, llm, world):
    upload(client, llm, invoice_payload(), text="first version of the invoice " * 10)
    r = upload(client, llm, invoice_payload(), text="a re-issued layout of the same invoice " * 10)
    d = invoice_detail(client, r["invoice_id"])
    assert d["decision_status"] == "REJECTED"
    assert any("already submitted by this vendor" in m for m in reasons(d))


def test_demo3_exceeds_po_balance_needs_review(client, llm, db):
    vendor = add_vendor(db)
    add_po(db, vendor, total="9000.00")
    d = invoice_detail(client, upload(client, llm, invoice_payload())["invoice_id"])
    assert d["decision_status"] == "NEEDS_REVIEW"
    assert any("₹2,800.00 higher than the remaining PO balance" in m for m in reasons(d))
    assert db.query(POAllocation).count() == 0  # nothing consumed


def test_demo4_missing_invoice_number_needs_review(client, llm, world):
    d = invoice_detail(client, upload(client, llm, invoice_payload(invoice_number=None))["invoice_id"])
    assert d["decision_status"] == "NEEDS_REVIEW"
    assert any("Invoice number" in m for m in reasons(d))


def test_demo5_inactive_vendor_rejected(client, llm, db):
    vendor = add_vendor(db, status="INACTIVE")
    add_po(db, vendor)
    d = invoice_detail(client, upload(client, llm, invoice_payload())["invoice_id"])
    assert d["decision_status"] == "REJECTED"
    assert any("inactive" in m for m in reasons(d))


def test_arithmetic_mismatch_needs_review(client, llm, world):
    d = invoice_detail(client, upload(client, llm, invoice_payload(total_amount="11900.00"))["invoice_id"])
    assert d["decision_status"] == "NEEDS_REVIEW"
    assert any("differs from subtotal + tax" in m for m in reasons(d))


def test_currency_mismatch_needs_review(client, llm, world):
    d = invoice_detail(client, upload(client, llm, invoice_payload(currency="USD"))["invoice_id"])
    assert d["decision_status"] == "NEEDS_REVIEW"
    assert any("does not match PO currency" in m for m in reasons(d))


def test_missing_po_needs_review(client, llm, world):
    d = invoice_detail(client, upload(client, llm, invoice_payload(purchase_order_number=None))["invoice_id"])
    assert d["decision_status"] == "NEEDS_REVIEW"


# ------------------------------------------------------- technical failures
def test_corrupted_pdf_is_processing_failed_not_rejected(client, llm, world):
    llm.payload = invoice_payload()
    r = client.post("/api/v1/invoices/upload",
                    files={"file": ("bad.pdf", make_corrupted_pdf(), "application/pdf")})  # fmt: skip
    d = invoice_detail(client, r.json()["data"]["invoice_id"])
    assert d["processing_status"] == "FAILED" and d["decision_status"] is None
    assert "corrupted" in d["error_message"]
    run = client.get(f"/api/v1/runs/{r.json()['data']['run_id']}").json()["data"]
    assert run["status"] == "FAILED" and run["can_retry"] is True
    assert any(s["stage"] == "DOCUMENT_EXTRACTION" and s["status"] == "FAILED" for s in run["stages"])


def test_ocr_unavailable_fails_gracefully(client, llm, world):
    llm.payload = invoice_payload()
    r = client.post("/api/v1/invoices/upload",
                    files={"file": ("scan.pdf", make_image_only_pdf(), "application/pdf")})  # fmt: skip
    d = invoice_detail(client, r.json()["data"]["invoice_id"])
    assert d["processing_status"] == "FAILED" and d["decision_status"] is None


def test_llm_invalid_output_fails_extraction_stage(client, llm, world):
    llm.error = ValueError("bad json")
    d = invoice_detail(client, upload_raw(client, llm))
    assert d["processing_status"] == "FAILED"
    assert llm.calls == 2  # retried (GEMINI_MAX_RETRIES=2) before failing


def test_llm_timeout_retries_then_fails_and_retry_creates_new_run(client, llm, world):
    llm.error = TransientError("timeout", category="LLM_TIMEOUT")
    invoice_id = upload_raw(client, llm)
    d = invoice_detail(client, invoice_id)
    assert d["processing_status"] == "FAILED" and d["decision_status"] is None

    llm.error = None
    llm.payload = invoice_payload()
    retry = client.post(f"/api/v1/invoices/{invoice_id}/retry")
    assert retry.status_code == 202
    d = invoice_detail(client, invoice_id)
    assert [r["run_number"] for r in d["runs"]] == [1, 2]  # history preserved
    assert d["runs"][0]["status"] == "FAILED"
    assert d["decision_status"] == "APPROVED"
    # a completed invoice cannot be retried
    assert client.post(f"/api/v1/invoices/{invoice_id}/retry").status_code == 409


def upload_raw(client, llm) -> str:
    pdf = make_pdf("some readable invoice text " * 10)
    r = client.post("/api/v1/invoices/upload", files={"file": ("x.pdf", pdf, "application/pdf")})
    return r.json()["data"]["invoice_id"]


# --------------------------------------------------------------- upload checks
def test_upload_rejects_non_pdf(client):
    r = client.post("/api/v1/invoices/upload", files={"file": ("a.txt", b"hello", "text/plain")})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_file"


def test_upload_rejects_fake_pdf_extension(client):
    r = client.post("/api/v1/invoices/upload", files={"file": ("a.pdf", b"not a pdf", "application/pdf")})
    assert r.status_code == 400


def test_upload_rejects_oversize(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_size_mb", 0)
    r = client.post("/api/v1/invoices/upload",
                    files={"file": ("a.pdf", b"%PDF-1.4 " + b"x" * 100, "application/pdf")})  # fmt: skip
    assert r.status_code == 413


def test_document_served_and_traversal_safe(client, llm, world, db):
    inv_id = upload(client, llm, invoice_payload())["invoice_id"]
    r = client.get(f"/api/v1/invoices/{inv_id}/document")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    from app.models import Invoice

    inv = db.get(Invoice, __import__("uuid").UUID(inv_id))
    inv.stored_file_path = "../../etc/passwd"
    db.commit()
    assert client.get(f"/api/v1/invoices/{inv_id}/document").status_code == 404


# ----------------------------------------------------------- listing + stats
def test_list_filter_sort_paginate(client, llm, world):
    upload(client, llm, invoice_payload(), text="one " * 30)
    upload(client, llm, invoice_payload(invoice_number=None), text="two " * 30)
    body = client.get("/api/v1/invoices", params={"decision_status": "NEEDS_REVIEW"}).json()
    assert body["meta"]["total"] == 1 and body["data"][0]["decision_status"] == "NEEDS_REVIEW"
    body = client.get("/api/v1/invoices", params={"page_size": 1, "sort_by": "total_amount"}).json()
    assert body["meta"]["total_pages"] == 2 and len(body["data"]) == 1
    assert client.get("/api/v1/invoices", params={"q": "Acme"}).json()["meta"]["total"] == 2


def test_invoice_listing_filters_regression(client, llm, world):
    """Regression test for Bug 1: ensure default and all filter variants succeed."""
    # 1. Default request exactly as called by frontend
    res = client.get("/api/v1/invoices?sort_by=uploaded_at&sort_dir=desc&page=1&page_size=15")
    assert res.status_code == 200
    assert "data" in res.json() and "meta" in res.json()

    vendor, po = world
    upload(client, llm, invoice_payload(currency="INR", total_amount="11800.00"), text="first test invoice " * 20)

    # 2. Filter by vendor_id
    res_vendor = client.get("/api/v1/invoices", params={"vendor_id": str(vendor.id)})
    assert res_vendor.status_code == 200
    assert len(res_vendor.json()["data"]) >= 1

    # 3. Filter by currency and amount range
    res_filtered = client.get("/api/v1/invoices", params={
        "currency": "INR",
        "min_amount": "5000",
        "max_amount": "20000",
        "decision_status": "APPROVED",
        "sort_by": "uploaded_at",
        "sort_dir": "desc",
        "page": 1,
        "page_size": 15,
    })
    assert res_filtered.status_code == 200
    assert len(res_filtered.json()["data"]) >= 1

    # 4. Search query
    res_q = client.get("/api/v1/invoices", params={"q": "Acme"})
    assert res_q.status_code == 200


def test_dashboard_stats_come_from_database(client, llm, world):
    upload(client, llm, invoice_payload(), text="a " * 50)
    upload(client, llm, invoice_payload(invoice_number=None), text="b " * 50)
    stats = client.get("/api/v1/dashboard/stats").json()["data"]
    assert stats["kpis"]["total"]["value"] == 2
    assert stats["kpis"]["approved"]["value"] == 1 and stats["kpis"]["needs_review"]["value"] == 1
    assert stats["approval_rate"] == 50.0 and stats["pending_reviews"] == 1
    assert sum(m["count"] for m in stats["monthly_volume"]) == 2
    assert client.get("/api/v1/dashboard/recent-activity").json()["data"]


# ------------------------------------------------------------- manual review
def test_demo6_manual_review_approve_with_audit(client, llm, world, db):
    inv_id = upload(client, llm, invoice_payload(vendor_gstin=None), text="gst missing " * 30)["invoice_id"]
    d = invoice_detail(client, inv_id)
    assert d["decision_status"] == "NEEDS_REVIEW" and d["review"]["review_status"] == "PENDING"
    review_id = d["review"]["id"]

    queue = client.get("/api/v1/reviews", params={"review_status": "OPEN"}).json()
    assert queue["meta"]["total"] == 1 and "GSTIN" in queue["data"][0]["issue"]

    # a comment is mandatory
    bad = client.post(f"/api/v1/reviews/{review_id}/decision", json={"action": "APPROVE", "comment": ""})
    assert bad.status_code == 422

    ok = client.post(f"/api/v1/reviews/{review_id}/decision",
                     json={"action": "APPROVE", "comment": "GSTIN confirmed by phone call"})  # fmt: skip
    assert ok.status_code == 200
    d = invoice_detail(client, inv_id)
    assert d["decision_status"] == "APPROVED" and d["review"]["review_status"] == "APPROVED"
    assert d["purchase_order"]["consumed_amount"] == "11800.00"
    entry = next(a for a in d["audit_trail"] if a["action"] == "REVIEW_APPROVE")
    assert entry["description"] == "GSTIN confirmed by phone call"
    assert entry["old_value"] == "NEEDS_REVIEW" and entry["new_value"] == "APPROVED"
    assert db.query(AuditLog).filter_by(action="REVIEW_APPROVE").count() == 1
    # resolved reviews cannot be decided twice
    again = client.post(f"/api/v1/reviews/{review_id}/decision",
                        json={"action": "REJECT", "comment": "changed my mind"})  # fmt: skip
    assert again.status_code == 409


def test_manual_approval_cannot_overspend_po(client, llm, db):
    vendor = add_vendor(db)
    add_po(db, vendor, total="9000.00")
    inv_id = upload(client, llm, invoice_payload())["invoice_id"]
    review_id = invoice_detail(client, inv_id)["review"]["id"]
    r = client.post(f"/api/v1/reviews/{review_id}/decision",
                    json={"action": "APPROVE", "comment": "approve anyway please"})  # fmt: skip
    assert r.status_code == 409 and "remaining PO balance" in r.json()["error"]["message"]
    d = invoice_detail(client, inv_id)
    assert d["decision_status"] == "NEEDS_REVIEW"
    # Verification that failed approval is recorded in audit log
    entry = next((a for a in d["audit_trail"] if a["action"] == "REVIEW_APPROVE_FAILED"), None)
    assert entry is not None
    assert "Manual approval rejected" in entry["description"]
    assert db.query(POAllocation).count() == 0


def test_two_invoices_competing_for_insufficient_po_balance(client, llm, db):
    vendor = add_vendor(db)
    # PO total is 15000; invoice_payload has total 11800. Two invoices = 23600 (exceeds 15000)
    add_po(db, vendor, total="15000.00")
    inv_1 = UUID(upload(client, llm, invoice_payload(invoice_number="INV-A"), text="invoice a " * 20)["invoice_id"])
    inv_2 = UUID(upload(client, llm, invoice_payload(invoice_number="INV-B"), text="invoice b " * 20)["invoice_id"])
    
    # First is auto-approved because 11800 <= 15000
    d1 = invoice_detail(client, inv_1)
    assert d1["decision_status"] == "APPROVED"
    assert db.query(POAllocation).filter_by(invoice_id=inv_1, status="ACTIVE").count() == 1
    
    # Second needs review because remaining balance is now 15000 - 11800 = 3200 < 11800
    d2 = invoice_detail(client, inv_2)
    assert d2["decision_status"] == "NEEDS_REVIEW"
    review_2 = d2["review"]["id"]
    
    # Reviewer attempts manual approval on second invoice -> must be rejected with 409 Conflict
    r = client.post(f"/api/v1/reviews/{review_2}/decision",
                    json={"action": "APPROVE", "comment": "Force approve second invoice"})
    assert r.status_code == 409
    assert "remaining PO balance" in r.json()["error"]["message"]
    
    # Verify invoice 2 remains in NEEDS_REVIEW, no second allocation, and failure audit logged
    d2_after = invoice_detail(client, inv_2)
    assert d2_after["decision_status"] == "NEEDS_REVIEW"
    assert db.query(POAllocation).filter_by(invoice_id=inv_2).count() == 0
    assert db.query(AuditLog).filter_by(invoice_id=inv_2, action="REVIEW_APPROVE_FAILED").count() == 1


def test_manual_approval_with_balance_changed_and_rollback(client, llm, db):
    vendor = add_vendor(db)
    po = add_po(db, vendor, total="25000.00")
    # Upload an invoice needing review (e.g. missing GSTIN) with total 11800
    inv_id = UUID(upload(client, llm, invoice_payload(invoice_number="INV-REV", vendor_gstin=None), text="missing gstin " * 20)["invoice_id"])
    d = invoice_detail(client, inv_id)
    assert d["decision_status"] == "NEEDS_REVIEW", reasons(d)
    review_id = d["review"]["id"]

    # Now simulate another invoice consuming the balance in the meantime
    other_inv = new_invoice(db, vendor_id=vendor.id, purchase_order_id=po.id, total_amount=Decimal("20000.00"), currency="INR")
    po_matcher.allocate_to_po(db, other_inv, allocated_by="other_reviewer")
    db.commit()
    # Now remaining balance = 25000 - 20000 = 5000 < 11800

    # Attempt manual approval on the first invoice (needs 11800)
    res = client.post(f"/api/v1/reviews/{review_id}/decision", json={"action": "APPROVE", "comment": "Reviewer approves"})
    assert res.status_code == 409
    assert "remaining PO balance" in res.json()["error"]["message"]

    # Verify rollback: status unchanged, no partial allocation created
    d_final = invoice_detail(client, inv_id)
    assert d_final["decision_status"] == "NEEDS_REVIEW"
    assert db.query(POAllocation).filter_by(invoice_id=inv_id).count() == 0
    assert db.query(AuditLog).filter_by(invoice_id=inv_id, action="REVIEW_APPROVE_FAILED").count() == 1


def test_manual_reject_and_clarification(client, llm, world, db):
    a = upload(client, llm, invoice_payload(invoice_number=None), text="aa " * 40)["invoice_id"]
    b = upload(client, llm, invoice_payload(invoice_number=None), text="bb " * 40)["invoice_id"]
    ra, rb = (invoice_detail(client, i)["review"]["id"] for i in (a, b))
    assert client.post(f"/api/v1/reviews/{ra}/decision",
                       json={"action": "REJECT", "comment": "Not our invoice"}).status_code == 200  # fmt: skip
    assert invoice_detail(client, a)["decision_status"] == "REJECTED"
    assert client.post(f"/api/v1/reviews/{rb}/decision",
                       json={"action": "REQUEST_CLARIFICATION",
                             "comment": "Please resend with invoice number"}).status_code == 200  # fmt: skip
    d = invoice_detail(client, b)
    assert d["decision_status"] == "NEEDS_REVIEW"
    assert d["review"]["review_status"] == "CLARIFICATION_REQUESTED"
    from app.models import NotificationDraft

    assert db.query(NotificationDraft).filter_by(kind="CLARIFICATION", status="DRAFT").count() == 1


# ------------------------------------------------------------ master data APIs
def test_vendor_and_po_crud(client, world):
    created = client.post("/api/v1/vendors", json={"vendor_name": "New Vendor Pvt Ltd", "gstin": "27AABCN1234A1Z5"})
    assert created.status_code == 201
    vid = created.json()["data"]["id"]
    dup = client.post("/api/v1/vendors", json={"vendor_name": "Another", "gstin": "27AABCN1234A1Z5"})
    assert dup.status_code == 409
    patched = client.patch(f"/api/v1/vendors/{vid}", json={"status": "INACTIVE"})
    assert patched.json()["data"]["status"] == "INACTIVE"
    assert client.get("/api/v1/vendors", params={"status": "INACTIVE"}).json()["meta"]["total"] == 1

    po = client.post("/api/v1/purchase-orders", json={
        "po_number": "PO-9000", "vendor_id": vid, "po_date": "2026-01-01", "currency": "inr",
        "total_amount": "5000", "items": [{"description": "Widgets", "quantity": "5", "unit_price": "1000"}],
    })  # fmt: skip
    assert po.status_code == 201 and po.json()["data"]["currency"] == "INR"
    detail = client.get(f"/api/v1/purchase-orders/{po.json()['data']['id']}").json()["data"]
    assert detail["items"][0]["total_amount"] == "5000.00" and detail["remaining_balance"] == "5000.00"
    assert client.get("/api/v1/vendors/" + "0" * 32).status_code == 404
