"""Vendor matching, PO matching, balance accounting, duplicate detection (DB-backed)."""

from datetime import timedelta
from decimal import Decimal

import pytest

from app.database.base import utcnow
from app.models import Invoice, InvoiceLineItem, POAllocation
from app.models.enums import CheckStatus, Impact
from app.services import duplicate_detector, po_matcher, vendor_service
from app.services.checks import Check
from tests.conftest import GSTIN_ACME, add_po, add_vendor


def results_by_type(results):
    return {r.validation_type: r for r in results}


def new_invoice(db, **kw) -> Invoice:
    values = dict(
        original_file_name="a.pdf", stored_file_path="a", file_hash="h" + str(utcnow().timestamp()),
        invoice_number="INV-1", vendor_name_raw="Acme Supplies Pvt Ltd", vendor_gstin_raw=GSTIN_ACME,
        currency="INR", total_amount=Decimal("1000"), uploaded_at=utcnow(),
    )  # fmt: skip
    values.update(kw)
    inv = Invoice(**values)
    db.add(inv)
    db.commit()
    return inv


# ---------------------------------------------------------------------- vendors
def test_vendor_matched_by_gstin_even_if_name_differs_slightly(db, settings):
    vendor = add_vendor(db)
    inv = new_invoice(db, vendor_name_raw="Acme Supplies Private Limited")
    r = results_by_type(vendor_service.verify_vendor(db, inv, settings))
    assert inv.vendor_id == vendor.id
    assert r[Check.VENDOR_MATCH].status == CheckStatus.PASSED
    assert r[Check.VENDOR_GSTIN].status == CheckStatus.PASSED


def test_inactive_vendor_is_hard_reject(db, settings):
    add_vendor(db, status="INACTIVE")
    inv = new_invoice(db)
    r = results_by_type(vendor_service.verify_vendor(db, inv, settings))
    assert r[Check.VENDOR_STATUS].impact == Impact.REJECT
    assert r[Check.VENDOR_STATUS].status == CheckStatus.FAILED


def test_fuzzy_match_never_authorises_vendor(db, settings):
    add_vendor(db, name="Acme Supplies Pvt Ltd", gstin=None)
    inv = new_invoice(db, vendor_name_raw="Acme Suppliez", vendor_gstin_raw=None)
    r = results_by_type(vendor_service.verify_vendor(db, inv, settings))
    assert inv.vendor_id is None  # not linked
    assert r[Check.VENDOR_MATCH].status == CheckStatus.WARNING
    assert r[Check.VENDOR_MATCH].impact == Impact.REVIEW
    assert "Acme Supplies" in r[Check.VENDOR_MATCH].message


def test_unknown_vendor_needs_review(db, settings):
    add_vendor(db)
    inv = new_invoice(db, vendor_name_raw="Totally Different Co", vendor_gstin_raw=None)
    r = results_by_type(vendor_service.verify_vendor(db, inv, settings))
    assert r[Check.VENDOR_MATCH].impact == Impact.REVIEW and inv.vendor_id is None


def test_ambiguous_vendor_needs_review(db, settings):
    add_vendor(db, name="Delta Traders", gstin="27AABCD1111A1ZO", code="V-A")
    add_vendor(db, name="Delta Trader", gstin="27AABCD2222A1ZI", code="V-B")
    inv = new_invoice(db, vendor_name_raw="Delta Tradersz", vendor_gstin_raw=None)
    r = results_by_type(vendor_service.verify_vendor(db, inv, settings))
    assert "Multiple vendors" in r[Check.VENDOR_MATCH].message


def test_gstin_mismatch_flagged(db, settings):
    add_vendor(db)
    inv = new_invoice(db, vendor_gstin_raw=None, vendor_name_raw="Acme Supplies Pvt Ltd")
    inv.vendor_gstin_raw = "29AABCA9999A1ZB"
    r = results_by_type(vendor_service.verify_vendor(db, inv, settings))
    assert r[Check.VENDOR_MATCH].status == CheckStatus.PASSED  # matched by name
    assert r[Check.VENDOR_GSTIN].status == CheckStatus.FAILED


def test_missing_invoice_gstin_cannot_be_verified(db, settings):
    add_vendor(db)
    inv = new_invoice(db, vendor_gstin_raw=None)
    r = results_by_type(vendor_service.verify_vendor(db, inv, settings))
    assert r[Check.VENDOR_GSTIN].status == CheckStatus.WARNING
    assert "could not be verified" in r[Check.VENDOR_GSTIN].message


# ------------------------------------------------------------------------- POs
def test_po_match_all_pass(db):
    vendor = add_vendor(db)
    add_po(db, vendor, items=[("Office chairs", "10", "1000")])
    inv = new_invoice(db, vendor_id=vendor.id, po_number_raw="po-1001")  # case-insensitive
    inv.line_items = [InvoiceLineItem(description="Office chair", unit_price=Decimal("1000"))]
    r = results_by_type(po_matcher.match_purchase_order(db, inv))
    assert all(x.status == CheckStatus.PASSED for x in r.values()), {k: v.message for k, v in r.items()}


def test_missing_po_number_needs_review(db):
    inv = new_invoice(db, po_number_raw=None)
    r = results_by_type(po_matcher.match_purchase_order(db, inv))
    assert r[Check.PO_EXISTS].impact == Impact.REVIEW
    assert r[Check.PO_BALANCE].status == CheckStatus.SKIPPED


def test_po_belongs_to_other_vendor(db):
    acme = add_vendor(db)
    other = add_vendor(db, name="Other Corp", gstin="27AABCO1111A1ZD", code="V-O")
    add_po(db, other)
    inv = new_invoice(db, vendor_id=acme.id, po_number_raw="PO-1001")
    r = results_by_type(po_matcher.match_purchase_order(db, inv))
    assert r[Check.PO_VENDOR].status == CheckStatus.FAILED
    assert "Other Corp" in r[Check.PO_VENDOR].message


def test_po_currency_mismatch(db):
    v = add_vendor(db)
    add_po(db, v, currency="USD")
    inv = new_invoice(db, vendor_id=v.id, po_number_raw="PO-1001")
    r = results_by_type(po_matcher.match_purchase_order(db, inv))
    assert r[Check.PO_CURRENCY].status == CheckStatus.FAILED


def test_closed_po_needs_review(db):
    v = add_vendor(db)
    add_po(db, v, status="CLOSED")
    inv = new_invoice(db, vendor_id=v.id, po_number_raw="PO-1001")
    assert results_by_type(po_matcher.match_purchase_order(db, inv))[Check.PO_STATUS].impact == Impact.REVIEW


def test_remaining_balance_counts_only_approved_allocations(db):
    v = add_vendor(db)
    po = add_po(db, v, total="10000")
    approved = new_invoice(db, vendor_id=v.id, purchase_order_id=po.id, total_amount=Decimal("4000"))
    pending = new_invoice(db, vendor_id=v.id, purchase_order_id=po.id, total_amount=Decimal("3000"),
                          file_hash="other")  # fmt: skip
    po_matcher.allocate_to_po(db, approved, allocated_by="t")
    db.commit()
    assert po_matcher.remaining_balance(db, po) == Decimal("6000")  # pending invoice consumes nothing
    assert pending.id != approved.id


def test_invoice_exceeding_balance_flagged_with_amount(db):
    v = add_vendor(db)
    po = add_po(db, v, total="10000")
    inv = new_invoice(db, vendor_id=v.id, po_number_raw="PO-1001", total_amount=Decimal("12500"))
    r = results_by_type(po_matcher.match_purchase_order(db, inv))
    assert r[Check.PO_BALANCE].status == CheckStatus.FAILED
    assert "₹2,500.00 higher than the remaining PO balance" in r[Check.PO_BALANCE].message
    assert po.total_amount == Decimal("10000")


def test_allocation_cannot_overspend_and_is_idempotent(db):
    v = add_vendor(db)
    po = add_po(db, v, total="10000")
    a = new_invoice(db, vendor_id=v.id, purchase_order_id=po.id, total_amount=Decimal("7000"), file_hash="a")
    b = new_invoice(db, vendor_id=v.id, purchase_order_id=po.id, total_amount=Decimal("5000"), file_hash="b")
    po_matcher.allocate_to_po(db, a, allocated_by="t")
    po_matcher.allocate_to_po(db, a, allocated_by="t")  # idempotent
    with pytest.raises(ValueError):
        po_matcher.allocate_to_po(db, b, allocated_by="t")
    db.commit()
    assert db.query(POAllocation).count() == 1


# ------------------------------------------------------------------- duplicates
def test_exact_file_duplicate_rejected(db, settings):
    first = new_invoice(db, file_hash="same", uploaded_at=utcnow() - timedelta(hours=1))
    second = new_invoice(db, file_hash="same")
    r = results_by_type(duplicate_detector.detect_duplicates(db, second, settings))
    assert r[Check.DUP_FILE].impact == Impact.REJECT
    original = results_by_type(duplicate_detector.detect_duplicates(db, first, settings))
    assert original[Check.DUP_FILE].status == CheckStatus.PASSED  # earliest upload is the original


def test_business_duplicate_same_vendor_and_number(db, settings):
    v = add_vendor(db)
    new_invoice(db, vendor_id=v.id, file_hash="1", uploaded_at=utcnow() - timedelta(days=1),
                decision_status="APPROVED")  # fmt: skip
    dup = new_invoice(db, vendor_id=v.id, file_hash="2", invoice_number="inv 1")
    r = results_by_type(duplicate_detector.detect_duplicates(db, dup, settings))
    assert r[Check.DUP_BUSINESS].impact == Impact.REJECT


def test_same_number_other_vendor_is_not_duplicate(db, settings):
    a = add_vendor(db)
    b = add_vendor(db, name="Other Corp", gstin="27AABCO1111A1ZD", code="V-O")
    new_invoice(db, vendor_id=a.id, file_hash="1", uploaded_at=utcnow() - timedelta(days=1), decision_status="APPROVED")
    inv = new_invoice(db, vendor_id=b.id, file_hash="2")
    r = results_by_type(duplicate_detector.detect_duplicates(db, inv, settings))
    assert r[Check.DUP_BUSINESS].status == CheckStatus.PASSED


def test_potential_duplicate_similar_number_same_amount(db, settings):
    v = add_vendor(db)
    new_invoice(db, vendor_id=v.id, invoice_number="INV-2026-0042", file_hash="1",
                uploaded_at=utcnow() - timedelta(days=1), decision_status="APPROVED")  # fmt: skip
    inv = new_invoice(db, vendor_id=v.id, invoice_number="INV-2026-0042A", file_hash="2")
    r = results_by_type(duplicate_detector.detect_duplicates(db, inv, settings))
    assert r[Check.DUP_BUSINESS].status == CheckStatus.PASSED
    assert r[Check.DUP_POTENTIAL].status == CheckStatus.WARNING
    assert r[Check.DUP_POTENTIAL].impact == Impact.REVIEW


def test_failed_processing_invoices_are_not_originals(db, settings):
    v = add_vendor(db)
    new_invoice(db, vendor_id=v.id, file_hash="same", uploaded_at=utcnow() - timedelta(days=1),
                processing_status="FAILED")  # fmt: skip
    inv = new_invoice(db, vendor_id=v.id, file_hash="same")
    r = results_by_type(duplicate_detector.detect_duplicates(db, inv, settings))
    assert r[Check.DUP_FILE].status == CheckStatus.PASSED
