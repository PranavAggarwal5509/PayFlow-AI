"""Deterministic invoice validation (data completeness + financial arithmetic).

Pure functions over an `Invoice` ORM object: no I/O, trivially unit-testable.
All money maths uses Decimal in the invoice's own currency.
"""

from datetime import date, timedelta
from decimal import Decimal

from app.core.config import Settings
from app.models.enums import CheckStatus
from app.models.invoice import Invoice
from app.services.checks import Check, CheckResult, money, passed, review, skipped

REQUIRED_FIELD_LABELS = {
    "invoice_number": "Invoice number",
    "vendor_name_raw": "Vendor name",
    "invoice_date": "Invoice date",
    "currency": "Currency",
    "total_amount": "Total amount",
}


def validate_data(invoice: Invoice, settings: Settings) -> list[CheckResult]:
    return [
        _required_fields(invoice),
        _invoice_date(invoice),
        _currency(invoice, settings),
        _amounts_valid(invoice),
        _line_items_valid(invoice),
        _extraction_quality(invoice),
    ]


def validate_financials(invoice: Invoice, settings: Settings) -> list[CheckResult]:
    tolerance = settings.tolerance_for(invoice.currency)
    return [
        _total_arithmetic(invoice, tolerance),
        _line_item_math(invoice, tolerance),
        _line_items_sum(invoice, tolerance),
        _tax_rates(invoice, settings, tolerance),
        _approval_limit(invoice, settings),
    ]


# ---------------------------------------------------------------- data checks
def _required_fields(invoice: Invoice) -> CheckResult:
    missing = [
        label
        for attr, label in REQUIRED_FIELD_LABELS.items()
        if getattr(invoice, attr) in (None, "")
    ]
    if missing:
        return review(
            Check.REQUIRED_FIELDS,
            f"Missing required field(s): {', '.join(missing)}.",
            actual=", ".join(missing),
        )
    return passed(Check.REQUIRED_FIELDS, "All required invoice fields were extracted.")


def _invoice_date(invoice: Invoice) -> CheckResult:
    raw = (invoice.extracted_data or {}).get("invoice_date")
    if invoice.invoice_date is None:
        if raw:
            return review(
                Check.INVOICE_DATE, f"Invoice date '{raw}' is not a valid date.", actual=raw
            )
        return skipped(Check.INVOICE_DATE, "Invoice date is missing.")
    if invoice.invoice_date > date.today() + timedelta(days=1):
        return review(
            Check.INVOICE_DATE,
            "Invoice date is in the future.",
            actual=invoice.invoice_date.isoformat(),
            status=CheckStatus.WARNING,
        )
    if invoice.due_date and invoice.due_date < invoice.invoice_date:
        return review(
            Check.INVOICE_DATE,
            "Due date is earlier than the invoice date.",
            expected=f">= {invoice.invoice_date.isoformat()}",
            actual=invoice.due_date.isoformat(),
            status=CheckStatus.WARNING,
        )
    return passed(
        Check.INVOICE_DATE, "Invoice date is valid.", actual=invoice.invoice_date.isoformat()
    )


def _currency(invoice: Invoice, settings: Settings) -> CheckResult:
    if not invoice.currency:
        return skipped(Check.CURRENCY_SUPPORTED, "Currency is missing.")
    if invoice.currency not in settings.currency_set:
        return review(
            Check.CURRENCY_SUPPORTED,
            f"Currency {invoice.currency} is not supported.",
            expected=", ".join(sorted(settings.currency_set)),
            actual=invoice.currency,
        )
    return passed(Check.CURRENCY_SUPPORTED, "Currency is supported.", actual=invoice.currency)


def _amounts_valid(invoice: Invoice) -> CheckResult:
    amounts = {
        "Subtotal": invoice.subtotal,
        "Tax amount": invoice.tax_amount,
        "Total amount": invoice.total_amount,
    }
    negatives = [name for name, value in amounts.items() if value is not None and value < 0]
    if invoice.total_amount is not None and invoice.total_amount == 0:
        negatives.append("Total amount (zero)")
    if negatives:
        return review(
            Check.AMOUNTS_VALID,
            f"Invalid amount(s): {', '.join(negatives)}.",
            expected="Positive total, non-negative subtotal and tax",
        )
    if invoice.total_amount is None:
        return skipped(Check.AMOUNTS_VALID, "Total amount is missing.")
    return passed(Check.AMOUNTS_VALID, "All amounts are valid.")


def _line_items_valid(invoice: Invoice) -> CheckResult:
    if not invoice.line_items:
        return review(
            Check.LINE_ITEMS_VALID, "No line items could be extracted.", status=CheckStatus.WARNING
        )
    problems: list[str] = []
    for index, item in enumerate(invoice.line_items, start=1):
        if item.quantity is not None and item.quantity <= 0:
            problems.append(f"line {index}: quantity must be positive")
        if item.unit_price is not None and item.unit_price < 0:
            problems.append(f"line {index}: unit price is negative")
        if item.total_amount is not None and item.total_amount < 0:
            problems.append(f"line {index}: total is negative")
    if problems:
        return review(Check.LINE_ITEMS_VALID, "Invalid line item(s): " + "; ".join(problems) + ".")
    return passed(Check.LINE_ITEMS_VALID, f"{len(invoice.line_items)} line item(s) are valid.")


def _extraction_quality(invoice: Invoice) -> CheckResult:
    uncertain = (invoice.extracted_data or {}).get("uncertain_fields") or []
    if uncertain:
        return review(
            Check.EXTRACTION_QUALITY,
            f"The AI was uncertain about: {', '.join(uncertain)}.",
            actual=", ".join(uncertain),
            status=CheckStatus.WARNING,
        )
    return passed(Check.EXTRACTION_QUALITY, "No uncertain fields were reported by extraction.")


# ------------------------------------------------------------ financial checks
def _total_arithmetic(invoice: Invoice, tolerance: Decimal) -> CheckResult:
    if invoice.total_amount is None:
        return skipped(Check.TOTAL_ARITHMETIC, "Total amount is missing.")
    if invoice.subtotal is None:
        return review(
            Check.TOTAL_ARITHMETIC,
            "Subtotal is missing, so the invoice total could not be verified.",
            actual=money(invoice.total_amount, invoice.currency),
            status=CheckStatus.WARNING,
        )
    if invoice.tax_amount is None and invoice.total_amount != invoice.subtotal:
        return review(
            Check.TOTAL_ARITHMETIC,
            "Tax amount is missing and the total differs from the subtotal.",
            expected=money(invoice.subtotal, invoice.currency),
            actual=money(invoice.total_amount, invoice.currency),
            status=CheckStatus.WARNING,
        )
    expected = invoice.subtotal + (invoice.tax_amount or Decimal("0"))
    difference = abs(expected - invoice.total_amount)
    if difference > tolerance:
        return review(
            Check.TOTAL_ARITHMETIC,
            f"Invoice total differs from subtotal + tax by {money(difference, invoice.currency)}.",
            expected=money(expected, invoice.currency),
            actual=money(invoice.total_amount, invoice.currency),
        )
    return passed(
        Check.TOTAL_ARITHMETIC,
        "Total equals subtotal + tax"
        + (f" (within {money(tolerance, invoice.currency)} rounding)." if difference else "."),
        expected=money(expected, invoice.currency),
        actual=money(invoice.total_amount, invoice.currency),
    )


def _line_item_math(invoice: Invoice, tolerance: Decimal) -> CheckResult:
    checked, bad = 0, []
    for index, item in enumerate(invoice.line_items, start=1):
        if None in (item.quantity, item.unit_price, item.total_amount):
            continue
        checked += 1
        base = item.quantity * item.unit_price
        with_tax = base * (1 + (item.tax_percentage or Decimal("0")) / 100)
        if min(abs(base - item.total_amount), abs(with_tax - item.total_amount)) > tolerance:
            bad.append(index)
    if not checked:
        return skipped(Check.LINE_ITEM_MATH, "No line items had quantity, price and total.")
    if bad:
        return review(
            Check.LINE_ITEM_MATH,
            f"Quantity × unit price does not match the line total on line(s): {bad}.",
            status=CheckStatus.WARNING,
        )
    return passed(Check.LINE_ITEM_MATH, "Line item quantity × price matches line totals.")


def _line_items_sum(invoice: Invoice, tolerance: Decimal) -> CheckResult:
    totals = [i.total_amount for i in invoice.line_items if i.total_amount is not None]
    if not totals or invoice.subtotal is None:
        return skipped(Check.LINE_ITEMS_SUM, "Line items or subtotal unavailable.")
    line_sum = sum(totals, Decimal("0"))
    # Line totals may be quoted before or after tax.
    candidates = [invoice.subtotal] + ([invoice.total_amount] if invoice.total_amount else [])
    if any(abs(line_sum - c) <= tolerance for c in candidates):
        return passed(
            Check.LINE_ITEMS_SUM,
            "Line items add up to the invoice subtotal.",
            expected=money(invoice.subtotal, invoice.currency),
            actual=money(line_sum, invoice.currency),
        )
    return review(
        Check.LINE_ITEMS_SUM,
        "Line items do not add up to the invoice subtotal.",
        expected=money(invoice.subtotal, invoice.currency),
        actual=money(line_sum, invoice.currency),
        status=CheckStatus.WARNING,
    )



def _tax_rates(invoice: Invoice, settings: Settings, tolerance: Decimal) -> CheckResult:
    """GST sanity: every line uses a notified GST slab, and the stated tax equals the line tax."""
    rated = [i for i in invoice.line_items if i.tax_percentage is not None]
    if not rated:
        return skipped(Check.TAX_RATES, "No per-line tax rates were printed on the invoice.")
    if invoice.currency == "INR":
        invalid = sorted(
            {f"{i.tax_percentage.normalize():f}%" for i in rated if i.tax_percentage not in settings.gst_rate_set}
        )
        if invalid:
            return review(
                Check.TAX_RATES,
                f"Tax rate(s) {', '.join(invalid)} are not valid GST slabs.",
                expected=", ".join(f"{r.normalize():f}%" for r in sorted(settings.gst_rate_set)),
                actual=", ".join(invalid),
            )
    if invoice.tax_amount is None or any(None in (i.quantity, i.unit_price) for i in rated):
        return passed(Check.TAX_RATES, "All line tax rates are valid GST slabs.")
    computed = sum(
        (i.quantity * i.unit_price * i.tax_percentage / 100 for i in rated), Decimal("0")
    ).quantize(Decimal("0.01"))
    allowed = tolerance * max(len(rated), 1)
    if abs(computed - invoice.tax_amount) > allowed:
        return review(
            Check.TAX_RATES,
            "Stated tax does not equal the tax implied by the line-item rates "
            f"(difference {money(abs(computed - invoice.tax_amount), invoice.currency)}).",
            expected=money(computed, invoice.currency),
            actual=money(invoice.tax_amount, invoice.currency),
            status=CheckStatus.WARNING,
        )
    return passed(
        Check.TAX_RATES,
        "Tax rates are valid and the stated tax matches the line-item rates.",
        expected=money(computed, invoice.currency),
        actual=money(invoice.tax_amount, invoice.currency),
    )


def _approval_limit(invoice: Invoice, settings: Settings) -> CheckResult:
    """Delegation of authority: high-value invoices always get a named human approver."""
    if invoice.total_amount is None or not invoice.currency:
        return skipped(Check.APPROVAL_LIMIT, "Total or currency unavailable.")
    rate = settings.fx_table.get(invoice.currency)
    if rate is None:
        return review(
            Check.APPROVAL_LIMIT,
            f"No reference FX rate for {invoice.currency}; cannot evaluate the approval limit.",
            actual=invoice.currency,
            status=CheckStatus.WARNING,
        )
    inr_value = (invoice.total_amount * rate).quantize(Decimal("0.01"))
    limit = settings.auto_approval_limit_inr
    shown = money(inr_value, "INR") + ("" if invoice.currency == "INR" else f" (at {rate} INR/{invoice.currency})")
    if inr_value > limit:
        return review(
            Check.APPROVAL_LIMIT,
            f"Invoice value {shown} exceeds the {money(limit, 'INR')} auto-approval limit. "
            "A finance approver must sign off.",
            expected=f"<= {money(limit, 'INR')}",
            actual=money(inr_value, "INR"),
            status=CheckStatus.WARNING,
        )
    return passed(
        Check.APPROVAL_LIMIT,
        f"Invoice value {shown} is within the {money(limit, 'INR')} auto-approval limit.",
        expected=f"<= {money(limit, 'INR')}",
        actual=money(inr_value, "INR"),
    )
