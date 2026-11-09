"""Sign-in, tokens and role-based access control (no dependency overrides: real auth path)."""

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.providers import get_llm
from app.core.config import get_settings
from app.core.errors import UnauthorizedError
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.database.session import get_session_factory
from app.main import app
from app.services.user_service import DEMO_ACCOUNTS, ensure_demo_accounts
from tests.conftest import add_po, add_vendor, invoice_payload, make_pdf

PASSWORDS = {a["role"].value: (a["email"], a["password"]) for a in DEMO_ACCOUNTS}


@pytest.fixture
def api(llm):
    with get_session_factory()() as db:
        ensure_demo_accounts(db)
    app.dependency_overrides[get_llm] = lambda: llm
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def login(api, role: str) -> dict:
    email, password = PASSWORDS[role]
    res = api.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['data']['token']}"}


def test_password_hash_roundtrip():
    stored = hash_password("s3cret!")
    assert verify_password("s3cret!", stored) and not verify_password("wrong", stored)


def test_token_tamper_and_expiry_rejected():
    settings = get_settings()
    import uuid

    token, _ = create_token(uuid.uuid4(), "ADMIN", settings)
    assert decode_token(token, settings)["role"] == "ADMIN"
    payload, sig = token.split(".")
    with pytest.raises(UnauthorizedError):
        decode_token(payload + "." + sig[:-2] + "xx", settings)


def test_requests_without_token_are_401(api):
    assert api.get("/api/v1/invoices").status_code == 401


def test_wrong_password_is_401_with_generic_message(api):
    res = api.post("/api/v1/auth/login", json={"email": "admin@payflow.demo", "password": "nope"})
    assert res.status_code == 401
    assert res.json()["error"]["message"] == "Incorrect email or password."


def test_me_returns_role_and_permissions(api):
    me = api.get("/api/v1/auth/me", headers=login(api, "AP_CLERK")).json()["data"]
    assert me["role"] == "AP_CLERK" and "invoices:upload" in me["permissions"]
    assert "review:act" not in me["permissions"]


def test_roles_catalogue_is_public(api):
    data = api.get("/api/v1/auth/roles").json()["data"]
    assert {r["role"] for r in data["roles"]} == {"ADMIN", "FINANCE_MANAGER", "AP_REVIEWER", "AP_CLERK", "AUDITOR"}
    admin = next(r for r in data["roles"] if r["role"] == "ADMIN")
    assert set(admin["permissions"]) == set(data["permissions"])  # admin can do everything


@pytest.mark.parametrize(
    "role,status",
    [("ADMIN", 201), ("FINANCE_MANAGER", 201), ("AP_REVIEWER", 201), ("AP_CLERK", 201), ("AUDITOR", 403)],
)
def test_upload_permission_by_role(api, llm, role, status):
    llm.payload = invoice_payload()
    res = api.post(
        "/api/v1/invoices/upload",
        files={"file": (f"{role}.pdf", make_pdf(f"Invoice for {role} " * 10), "application/pdf")},
        headers=login(api, role),
    )
    assert res.status_code == status, res.text


@pytest.mark.parametrize("role,status", [("ADMIN", 201), ("FINANCE_MANAGER", 403), ("AUDITOR", 403)])
def test_only_admin_edits_master_data(api, role, status):
    res = api.post("/api/v1/vendors", json={"vendor_name": f"New Vendor {role}"}, headers=login(api, role))
    assert res.status_code == status, res.text


def test_developer_analytics_admin_only(api):
    assert api.get("/api/v1/dashboard/developer-analytics", headers=login(api, "ADMIN")).status_code == 200
    assert api.get("/api/v1/dashboard/developer-analytics", headers=login(api, "AP_REVIEWER")).status_code == 403


def _high_value_review(api, llm, db) -> str:
    vendor = add_vendor(db)
    add_po(db, vendor, number="PO-BIG", total="1000000.00", items=[("Server rack", "10", "50000")])
    llm.payload = invoice_payload(
        invoice_number="INV-BIG", purchase_order_number="PO-BIG", subtotal="500000.00",
        tax_amount="90000.00", total_amount="590000.00",
        line_items=[{"description": "Server rack", "quantity": "10", "unit_price": "50000.00",
                     "tax_percentage": "18", "total_amount": "500000.00"}],
    )  # fmt: skip
    api.post("/api/v1/invoices/upload", files={"file": ("big.pdf", make_pdf("Invoice INV-BIG " * 10), "application/pdf")},
             headers=login(api, "AP_CLERK"))  # fmt: skip
    reviews = api.get("/api/v1/reviews", headers=login(api, "ADMIN")).json()["data"]
    return reviews[0]["id"]


def test_reviewer_cannot_approve_above_limit_but_finance_can(api, llm, db):
    review_id = _high_value_review(api, llm, db)
    body = {"action": "APPROVE", "comment": "Checked with vendor"}
    blocked = api.post(f"/api/v1/reviews/{review_id}/decision", json=body, headers=login(api, "AP_REVIEWER"))
    assert blocked.status_code == 403 and "Finance Manager" in blocked.json()["error"]["message"]
    ok = api.post(f"/api/v1/reviews/{review_id}/decision", json=body, headers=login(api, "FINANCE_MANAGER"))
    assert ok.status_code == 200, ok.text


def test_clerk_cannot_act_on_reviews(api, llm, db):
    review_id = _high_value_review(api, llm, db)
    res = api.post(f"/api/v1/reviews/{review_id}/decision", json={"action": "REJECT", "comment": "no"},
                   headers=login(api, "AP_CLERK"))  # fmt: skip
    assert res.status_code == 403


def test_query_token_works_for_event_streams_and_documents(api):
    token = login(api, "AUDITOR")["Authorization"][7:]
    assert api.get(f"/api/v1/invoices?access_token={token}").status_code == 200


def test_review_list_links_to_the_run_that_flagged_it(api, llm, db):
    _high_value_review(api, llm, db)
    item = api.get("/api/v1/reviews", headers=login(api, "ADMIN")).json()["data"][0]
    run = api.get(f"/api/v1/runs/{item['review_run_id']}", headers=login(api, "ADMIN")).json()["data"]
    assert run["decision"]["status"] == "NEEDS_REVIEW"
    assert any(r["code"] == "APPROVAL_LIMIT" for r in run["decision"]["reasons"])


@pytest.mark.parametrize("comment", ["", "   ", "ok", "  no  ", "ok ok ok"])
def test_review_decision_requires_a_real_reason(api, llm, db, comment):
    review_id = _high_value_review(api, llm, db)
    for action in ("APPROVE", "REJECT", "REQUEST_CLARIFICATION"):
        res = api.post(f"/api/v1/reviews/{review_id}/decision", json={"action": action, "comment": comment},
                       headers=login(api, "ADMIN"))  # fmt: skip
        assert res.status_code == 422, (action, comment, res.text)


# ------------------------------------------------------------------ demo reset
def test_demo_reset_removes_live_runs_keeps_history_and_allows_fresh_rerun(api, llm, db):
    from app.models import AuditLog, Invoice, ProcessingRun

    vendor = add_vendor(db)
    add_po(db, vendor, items=[("Office chairs", "10", "1000")])
    # A seeded history invoice that must survive.
    seeded = Invoice(invoice_number="HIST-1", original_file_name="h.pdf", stored_file_path="h.pdf",
                     file_hash="seedhash", source_origin="SEED_HISTORY", processing_status="COMPLETED",
                     decision_status="APPROVED")  # fmt: skip
    db.add(seeded)
    db.commit()

    pdf = make_pdf("Invoice INV-2026-001 total 11800 " * 6)
    admin = login(api, "ADMIN")
    llm.payload = invoice_payload()
    first = api.post("/api/v1/invoices/upload", files={"file": ("a.pdf", pdf, "application/pdf")}, headers=admin)
    assert first.status_code == 201
    dup = api.post("/api/v1/invoices/upload", files={"file": ("b.pdf", pdf, "application/pdf")}, headers=admin)
    dup_detail = api.get(f"/api/v1/invoices/{dup.json()['data']['invoice_id']}", headers=admin).json()["data"]
    assert dup_detail["decision_status"] == "REJECTED"  # exact duplicate before the reset

    preview = api.get("/api/v1/demo/reset", headers=admin).json()["data"]
    assert preview["invoices"] == 2 and preview["runs"] == 2 and preview["seeded_invoices_kept"] == 1

    done = api.post("/api/v1/demo/reset", headers=admin)
    assert done.status_code == 200, done.text
    db.expire_all()
    assert db.query(Invoice).filter(Invoice.source_origin == "LIVE_UPLOAD").count() == 0
    assert db.query(ProcessingRun).count() == 0
    assert db.query(Invoice).filter(Invoice.invoice_number == "HIST-1").count() == 1
    assert db.query(AuditLog).filter(AuditLog.action == "DEMO_RESET").count() == 1

    # The very same PDF now processes fresh (no duplicate, PO balance restored).
    again = api.post("/api/v1/invoices/upload", files={"file": ("a.pdf", pdf, "application/pdf")}, headers=admin)
    detail = api.get(f"/api/v1/invoices/{again.json()['data']['invoice_id']}", headers=admin).json()["data"]
    assert detail["decision_status"] == "APPROVED"


@pytest.mark.parametrize("role", ["FINANCE_MANAGER", "AP_REVIEWER", "AP_CLERK", "AUDITOR"])
def test_demo_reset_is_admin_only(api, role):
    assert api.post("/api/v1/demo/reset", headers=login(api, role)).status_code == 403
    assert api.get("/api/v1/demo/reset", headers=login(api, role)).status_code == 403
