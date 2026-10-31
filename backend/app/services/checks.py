"""Shared types for deterministic checks."""

from dataclasses import dataclass
from decimal import Decimal

from app.models.enums import CheckStatus, Impact


class Check:
    """Validation type codes (stored in validation_results.validation_type)."""

    REQUIRED_FIELDS = "REQUIRED_FIELDS"
    INVOICE_DATE = "INVOICE_DATE"
    CURRENCY_SUPPORTED = "CURRENCY_SUPPORTED"
    AMOUNTS_VALID = "AMOUNTS_VALID"
    LINE_ITEMS_VALID = "LINE_ITEMS_VALID"
    EXTRACTION_QUALITY = "EXTRACTION_QUALITY"
    TOTAL_ARITHMETIC = "TOTAL_ARITHMETIC"
    LINE_ITEM_MATH = "LINE_ITEM_MATH"
    LINE_ITEMS_SUM = "LINE_ITEMS_SUM"
    VENDOR_MATCH = "VENDOR_MATCH"
    VENDOR_STATUS = "VENDOR_STATUS"
    VENDOR_GSTIN = "VENDOR_GSTIN"
    PO_EXISTS = "PO_EXISTS"
    PO_VENDOR = "PO_VENDOR"
    PO_STATUS = "PO_STATUS"
    PO_CURRENCY = "PO_CURRENCY"
    PO_BALANCE = "PO_BALANCE"
    PO_LINE_ITEMS = "PO_LINE_ITEMS"
    DUP_FILE = "DUP_FILE"
    DUP_BUSINESS = "DUP_BUSINESS"
    DUP_POTENTIAL = "DUP_POTENTIAL"


LABELS = {
    Check.REQUIRED_FIELDS: "Required fields",
    Check.INVOICE_DATE: "Invoice date",
    Check.CURRENCY_SUPPORTED: "Currency",
    Check.AMOUNTS_VALID: "Amounts",
    Check.LINE_ITEMS_VALID: "Line items",
    Check.EXTRACTION_QUALITY: "Extraction confidence",
    Check.TOTAL_ARITHMETIC: "Invoice total",
    Check.LINE_ITEM_MATH: "Line item arithmetic",
    Check.LINE_ITEMS_SUM: "Line items vs subtotal",
    Check.VENDOR_MATCH: "Vendor match",
    Check.VENDOR_STATUS: "Vendor status",
    Check.VENDOR_GSTIN: "Vendor GSTIN",
    Check.PO_EXISTS: "Purchase order found",
    Check.PO_VENDOR: "PO vendor",
    Check.PO_STATUS: "PO status",
    Check.PO_CURRENCY: "PO currency",
    Check.PO_BALANCE: "PO balance",
    Check.PO_LINE_ITEMS: "PO line items",
    Check.DUP_FILE: "Exact file duplicate",
    Check.DUP_BUSINESS: "Duplicate invoice number",
    Check.DUP_POTENTIAL: "Potential duplicate",
}


@dataclass
class CheckResult:
    validation_type: str
    status: CheckStatus
    message: str
    impact: Impact = Impact.NONE
    expected_value: str | None = None
    actual_value: str | None = None


def passed(vtype: str, message: str, *, expected: object = None, actual: object = None):
    return CheckResult(
        vtype, CheckStatus.PASSED, message, Impact.NONE, _s(expected), _s(actual)
    )


def review(
    vtype: str, message: str, *, expected: object = None, actual: object = None,
    status: CheckStatus = CheckStatus.FAILED,
):  # fmt: skip
    return CheckResult(vtype, status, message, Impact.REVIEW, _s(expected), _s(actual))


def reject(vtype: str, message: str, *, expected: object = None, actual: object = None):
    return CheckResult(
        vtype, CheckStatus.FAILED, message, Impact.REJECT, _s(expected), _s(actual)
    )


def skipped(vtype: str, message: str):
    return CheckResult(vtype, CheckStatus.SKIPPED, message, Impact.NONE)


def _s(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return f"{value:,.2f}"
    return str(value)


def money(amount: Decimal | None, currency: str | None) -> str:
    symbol = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}.get(currency or "", "")
    suffix = "" if symbol else f" {currency}" if currency else ""
    return f"{symbol}{amount:,.2f}{suffix}" if amount is not None else "—"

