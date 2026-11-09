"""Enterprise AP controls: GSTIN checksum, bank-account fraud, GST rates, approval limit,
implied-PO inference and the potential-duplicate look-back window."""

from decimal import Decimal

import pytest

from app.utils.normalize import gstin_checksum_valid, parse_bank_details
from tests.conftest import add_po, add_vendor, invoice_detail, invoice_payload, upload


@pytest.fixture
def world(db):
    vendor = add_vendor(db)
    vendor.bank_account_number, vendor.bank_ifsc = "50200010017037", "YESB0001001"
    db.commit()
    po = add_po(db, vendor, items=[("Office chairs", "10", "1000")])
    return vendor, po


def codes(detail, severity=("BLOCKING", "WARNING")):
    return {r["code"] for r in detail["decision"]["reasons"] if r["severity"] in severity}


# ------------------------------------------------------------------- pure helpers
def test_gstin_checksum_accepts_real_and_rejects_typo():
    assert gstin_checksum_valid("27AAPFU0939F1ZV")
    assert not gstin_checksum_valid("27AAPFU0939F1ZX")
    assert not gstin_checksum_valid("O9AABCI1009I1ZV")  # OCR read 0 as O


def test_bank_details_parsed_from_free_text():
    assert parse_bank_details("Remit to: Yes Bank, A/C 5020 0010 0170 37, IFSC YESB0001001") == (
        "50200010017037",
        "YESB0001001",
    )
    assert parse_bank_details(None) == (None, None)


# ------------------------------------------------------------------- pipeline scenarios
def test_matching_bank_details_are_approved(client, llm, world):
    payload = invoice_payload(bank_account_details="Yes Bank A/C 50200010017037 IFSC YESB0001001")
    d = invoice_detail(client, upload(client, llm, payload)["invoice_id"])
    assert d["decision_status"] == "APPROVED"


def test_changed_bank_account_holds_payment(client, llm, world):
    payload = invoice_payload(bank_account_details="PNB A/C 36110098765432 IFSC PUNB0361100")
    d = invoice_detail(client, upload(client, llm, payload)["invoice_id"])
    assert d["decision_status"] == "NEEDS_REVIEW"
    assert "VENDOR_BANK" in codes(d, ("BLOCKING",))


def test_invalid_gstin_checksum_needs_review(client, llm, db, world):
    vendor, _ = world
    vendor.gstin = None  # force the invoice GSTIN to be evaluated on its own
    db.commit()
    d = invoice_detail(
        client, upload(client, llm, invoice_payload(vendor_gstin="27AABCA1234A1ZX"))["invoice_id"]
    )
    assert d["decision_status"] == "NEEDS_REVIEW"
    assert "VENDOR_GSTIN" in codes(d)


def test_non_gst_slab_rate_flagged(client, llm, world):
    payload = invoice_payload(
        tax_amount="1700.00",
        total_amount="11700.00",
        line_items=[{"description": "Office chairs", "quantity": "10", "unit_price": "1000.00",
                     "tax_percentage": "17", "total_amount": "10000.00"}],
    )  # fmt: skip
    d = invoice_detail(client, upload(client, llm, payload)["invoice_id"])
    assert d["decision_status"] == "NEEDS_REVIEW"
    assert "TAX_RATES" in codes(d)


def test_invoice_above_approval_limit_needs_human(client, llm, db, world):
    vendor, _ = world
    add_po(db, vendor, number="PO-BIG", total="1000000.00", items=[("Server rack", "10", "50000")])
    payload = invoice_payload(
        invoice_number="INV-BIG-1", purchase_order_number="PO-BIG", subtotal="500000.00",
        tax_amount="90000.00", total_amount="590000.00",
        line_items=[{"description": "Server rack", "quantity": "10", "unit_price": "50000.00",
                     "tax_percentage": "18", "total_amount": "500000.00"}],
    )  # fmt: skip
    d = invoice_detail(client, upload(client, llm, payload)["invoice_id"])
    assert d["decision_status"] == "NEEDS_REVIEW"
    assert codes(d) == {"APPROVAL_LIMIT"}


def test_usd_invoice_converted_for_approval_limit(client, llm, db, world):
    vendor, _ = world
    add_po(db, vendor, number="PO-USD", total="10000.00", currency="USD",
           items=[("Cloud credits", "100", "80")])  # fmt: skip
    payload = invoice_payload(
        invoice_number="INV-USD-1", purchase_order_number="PO-USD", currency="USD",
        subtotal="8000.00", tax_amount="0.00", total_amount="8000.00",
        line_items=[{"description": "Cloud credits", "quantity": "100", "unit_price": "80.00",
                     "tax_percentage": "0", "total_amount": "8000.00"}],
    )  # fmt: skip
    d = invoice_detail(client, upload(client, llm, payload)["invoice_id"])
    # 8,000 USD x 83.50 = 6,68,000 INR > 4,00,000 limit
    assert codes(d) == {"APPROVAL_LIMIT"}


def test_missing_po_is_inferred_from_vendor_and_lines(client, llm, world):
    _, po = world
    d = invoice_detail(
        client, upload(client, llm, invoice_payload(purchase_order_number=None))["invoice_id"]
    )
    assert d["decision_status"] == "NEEDS_REVIEW"
    assert codes(d) == {"PO_EXISTS"}
    assert d["purchase_order"]["po_number"] == po.po_number
    assert any("inferred PO-1001" in r for r in [x["message"] for x in d["decision"]["reasons"]])


def test_inference_refuses_when_two_pos_fit(client, llm, db, world):
    vendor, _ = world
    add_po(db, vendor, number="PO-1002", items=[("Office chairs", "50", "1000")])
    d = invoice_detail(
        client, upload(client, llm, invoice_payload(purchase_order_number=None))["invoice_id"]
    )
    assert d["decision_status"] == "NEEDS_REVIEW"
    assert d["purchase_order"] is None
    message = next(r["message"] for r in d["decision"]["reasons"] if r["code"] == "PO_EXISTS")
    assert "PO-1001" in message and "PO-1002" in message


def test_recurring_amount_outside_window_is_not_a_duplicate(client, llm, world):
    first = invoice_payload(invoice_number="RENT-01", invoice_date="2026-01-05",
                            due_date="2026-02-05", subtotal="1000.00", tax_amount="180.00",
                            total_amount="1180.00",
                            line_items=[{"description": "Office chairs", "quantity": "1",
                                         "unit_price": "1000.00", "tax_percentage": "18",
                                         "total_amount": "1000.00"}])  # fmt: skip
    upload(client, llm, first, filename="a.pdf")
    later = {**first, "invoice_number": "RENT-02", "invoice_date": "2026-06-05",
             "due_date": "2026-07-05"}  # fmt: skip
    d = invoice_detail(client, upload(client, llm, later, filename="b.pdf")["invoice_id"])
    assert "DUP_POTENTIAL" not in codes(d)
    assert d["decision_status"] == "APPROVED"


def test_money_uses_indian_grouping():
    from app.services.checks import money

    assert money(Decimal("506220"), "INR") == "₹5,06,220.00"
    assert money(Decimal("3050"), "USD") == "$3,050.00"


def test_repair_gstin_fixes_ocr_lookalikes_only_when_check_digit_confirms():
    from app.utils.normalize import gstin_checksum_valid, repair_gstin

    real = "27AABCO1015O1ZH"  # letters O in the PAN part
    assert gstin_checksum_valid(real)
    assert repair_gstin("27AABC01015O1ZH") == real  # letter O read as zero
    assert repair_gstin("27AABCO1O15O1ZH") == real  # zero read as letter O in a digit slot
    assert repair_gstin(real) == real
    typo = "27AABCO1815O1ZH"  # a genuinely different digit: must stay invalid
    assert repair_gstin(typo) == typo
    assert not gstin_checksum_valid(repair_gstin(typo))
    assert repair_gstin(None) is None
    assert repair_gstin("SHORT") == "SHORT"


def test_extraction_schema_flattens_structured_text_fields():
    from app.schemas.extraction import ExtractedInvoice

    parsed = ExtractedInvoice.model_validate(
        {"bank_account_details": {"bank_name": "Yes Bank", "account_number": "50200010017037", "ifsc": "YESB0001001"},
         "total_amount": "1,14,460.00", "line_items": [{"quantity": "100 BOX", "unit_price": "450.00"}]}
    )  # fmt: skip
    assert "50200010017037" in parsed.bank_account_details and "YESB0001001" in parsed.bank_account_details
    assert str(parsed.total_amount) == "114460.00"
    assert str(parsed.line_items[0].quantity) == "100"
