"""Unit tests: validation engine, decision engine, normalisation."""

from datetime import date
from decimal import Decimal

from app.models.enums import CheckStatus, DecisionStatus, Impact
from app.models.invoice import Invoice, InvoiceLineItem
from app.services import validation_engine as ve
from app.services.checks import Check, CheckResult, passed, reject, review
from app.services.decision_engine import REQUIRED_FOR_APPROVAL, decide
from app.utils.normalize import normalize_vendor_name


def make_invoice(**kw) -> Invoice:
    values = dict(
        invoice_number="INV-1", vendor_name_raw="Acme", invoice_date=date(2026, 1, 1),
        currency="INR", subtotal=Decimal("1000"), tax_amount=Decimal("180"),
        total_amount=Decimal("1180"), extracted_data={},
    )  # fmt: skip
    values.update(kw)
    invoice = Invoice(**values)
    invoice.line_items = [
        InvoiceLineItem(description="x", quantity=Decimal(1), unit_price=Decimal("1000"),
                        total_amount=Decimal("1000"))  # fmt: skip
    ]
    return invoice


def by_type(results):
    return {r.validation_type: r for r in results}


def test_total_arithmetic_passes_when_consistent(settings):
    r = by_type(ve.validate_financials(make_invoice(), settings))
    assert r[Check.TOTAL_ARITHMETIC].status == CheckStatus.PASSED


def test_total_arithmetic_mismatch_flags_review_and_never_alters_amount(settings):
    inv = make_invoice(total_amount=Decimal("1250"))
    r = by_type(ve.validate_financials(inv, settings))[Check.TOTAL_ARITHMETIC]
    assert r.status == CheckStatus.FAILED and r.impact == Impact.REVIEW
    assert inv.total_amount == Decimal("1250")  # not silently corrected


def test_inr_rounding_tolerance_is_one_rupee(settings):
    within = by_type(ve.validate_financials(make_invoice(total_amount=Decimal("1180.90")), settings))
    outside = by_type(ve.validate_financials(make_invoice(total_amount=Decimal("1181.10")), settings))
    assert within[Check.TOTAL_ARITHMETIC].status == CheckStatus.PASSED
    assert outside[Check.TOTAL_ARITHMETIC].status == CheckStatus.FAILED


def test_non_inr_uses_tighter_tolerance(settings):
    inv = make_invoice(currency="USD", total_amount=Decimal("1180.50"))
    r = by_type(ve.validate_financials(inv, settings))[Check.TOTAL_ARITHMETIC]
    assert r.status == CheckStatus.FAILED


def test_missing_required_fields(settings):
    inv = make_invoice(invoice_number=None)
    r = by_type(ve.validate_data(inv, settings))[Check.REQUIRED_FIELDS]
    assert r.status == CheckStatus.FAILED and "Invoice number" in r.message


def test_unsupported_currency(settings):
    r = by_type(ve.validate_data(make_invoice(currency="XYZ"), settings))[Check.CURRENCY_SUPPORTED]
    assert r.status == CheckStatus.FAILED


def test_negative_amount_invalid(settings):
    r = by_type(ve.validate_data(make_invoice(tax_amount=Decimal("-5")), settings))[Check.AMOUNTS_VALID]
    assert r.status == CheckStatus.FAILED


def test_invalid_line_item_quantity(settings):
    inv = make_invoice()
    inv.line_items[0].quantity = Decimal("0")
    r = by_type(ve.validate_data(inv, settings))[Check.LINE_ITEMS_VALID]
    assert r.status == CheckStatus.FAILED


def test_line_items_must_sum_to_subtotal(settings):
    inv = make_invoice()
    inv.line_items[0].total_amount = Decimal("900")
    inv.line_items[0].unit_price = Decimal("900")
    r = by_type(ve.validate_financials(inv, settings))[Check.LINE_ITEMS_SUM]
    assert r.status == CheckStatus.WARNING


def test_uncertain_fields_need_review(settings):
    inv = make_invoice(extracted_data={"uncertain_fields": ["invoice_date"]})
    r = by_type(ve.validate_data(inv, settings))[Check.EXTRACTION_QUALITY]
    assert r.impact == Impact.REVIEW


# -------------------------------------------------------------- decision engine
def all_passed(settings) -> list[CheckResult]:
    codes = set(REQUIRED_FOR_APPROVAL)
    codes.add(Check.VENDOR_GSTIN)
    return [passed(c, f"{c} ok") for c in codes]


def test_decision_approved_when_everything_passes(settings):
    assert decide(all_passed(settings), settings).status == DecisionStatus.APPROVED


def test_decision_inactive_vendor_rejected(settings):
    results = [r for r in all_passed(settings) if r.validation_type != Check.VENDOR_STATUS]
    results.append(reject(Check.VENDOR_STATUS, "inactive"))
    outcome = decide(results, settings)
    assert outcome.status == DecisionStatus.REJECTED
    assert outcome.reasons[0].message == "inactive"


def test_decision_missing_po_is_review_not_reject(settings):
    results = [r for r in all_passed(settings) if r.validation_type != Check.PO_EXISTS]
    results.append(review(Check.PO_EXISTS, "no PO"))
    assert decide(results, settings).status == DecisionStatus.NEEDS_REVIEW


def test_decision_incomplete_checks_never_approve(settings):
    results = all_passed(settings)[:-3]
    outcome = decide(results, settings)
    assert outcome.status == DecisionStatus.NEEDS_REVIEW
    assert any("could not be completed" in r.message for r in outcome.reasons)


def test_decision_warning_only_still_needs_review(settings):
    results = all_passed(settings) + [review(Check.LINE_ITEMS_SUM, "mismatch", status=CheckStatus.WARNING)]
    assert decide(results, settings).status == DecisionStatus.NEEDS_REVIEW


def test_reject_takes_priority_over_review(settings):
    results = [reject(Check.DUP_FILE, "dup"), review(Check.PO_EXISTS, "no po")]
    outcome = decide(results, settings)
    assert outcome.status == DecisionStatus.REJECTED
    assert {r.code for r in outcome.reasons if r.severity == "BLOCKING"} == {Check.DUP_FILE, Check.PO_EXISTS}


def test_decision_reasons_come_from_check_messages(settings):
    outcome = decide([review(Check.PO_BALANCE, "Invoice total is ₹2,500.00 higher than the balance.")], settings)
    assert outcome.reasons[0].message.startswith("Invoice total is ₹2,500.00")


def test_vendor_name_normalisation():
    assert normalize_vendor_name("Acme Supplies Pvt. Ltd.") == "acme supplies"
    assert normalize_vendor_name("ACME  SUPPLIES PRIVATE LIMITED") == "acme supplies"

