"""Vendor lookup and verification. A fuzzy name match is only ever a *suggestion*."""

import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.enums import CheckStatus, VendorStatus
from app.models.invoice import Invoice
from app.models.vendor_po import Vendor
from app.services.checks import Check, CheckResult, passed, reject, review, skipped
from app.utils.normalize import (
    gstin_check_digit,
    gstin_checksum_valid,
    normalize_gstin,
    normalize_vendor_name,
    parse_bank_details,
    repair_gstin,
)

GSTIN_PATTERN = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


@dataclass
class VendorMatch:
    kind: str  # GSTIN | EXACT_NAME | FUZZY | AMBIGUOUS | NOT_FOUND
    vendor: Vendor | None = None  # only set when the match is authoritative
    candidates: list[Vendor] = field(default_factory=list)  # suggestions (fuzzy / ambiguous)


def find_vendor(
    db: Session, name: str | None, gstin: str | None, settings: Settings
) -> VendorMatch:
    clean_gstin = repair_gstin(normalize_gstin(gstin))
    if clean_gstin:
        by_gstin = db.scalar(select(Vendor).where(Vendor.gstin == clean_gstin))
        if by_gstin:
            return VendorMatch("GSTIN", vendor=by_gstin)

    normalized = normalize_vendor_name(name)
    if not normalized:
        return VendorMatch("NOT_FOUND")

    exact = list(db.scalars(select(Vendor).where(Vendor.normalized_name == normalized)))
    if len(exact) == 1:
        return VendorMatch("EXACT_NAME", vendor=exact[0])
    if len(exact) > 1:
        return VendorMatch("AMBIGUOUS", candidates=exact)

    fuzzy = [
        v
        for v in db.scalars(select(Vendor))
        if fuzz.token_sort_ratio(normalized, v.normalized_name) >= settings.vendor_fuzzy_threshold
    ]
    if len(fuzzy) == 1:
        return VendorMatch("FUZZY", candidates=fuzzy)
    if len(fuzzy) > 1:
        return VendorMatch("AMBIGUOUS", candidates=fuzzy)
    return VendorMatch("NOT_FOUND")


def verify_vendor(db: Session, invoice: Invoice, settings: Settings) -> list[CheckResult]:
    """Resolve the vendor, link it to the invoice only if authoritative, and return checks."""
    match = find_vendor(db, invoice.vendor_name_raw, invoice.vendor_gstin_raw, settings)
    invoice.vendor_id = match.vendor.id if match.vendor else None
    claimed = invoice.vendor_name_raw

    if match.kind in ("GSTIN", "EXACT_NAME"):
        vendor = match.vendor
        assert vendor is not None
        results = [_match_result(match, vendor, claimed)]
        results.append(_status_result(vendor))
        results.append(_gstin_result(vendor, invoice, settings))
        results.append(_bank_result(vendor, invoice))
        return results

    names = ", ".join(v.vendor_name for v in match.candidates)
    if match.kind == "FUZZY":
        match_result = review(
            Check.VENDOR_MATCH,
            f"'{claimed}' is not an exact vendor match. Possible vendor: {names}. "
            "Manual confirmation required.",
            actual=claimed,
            expected=names,
            status=CheckStatus.WARNING,
        )
    elif match.kind == "AMBIGUOUS":
        match_result = review(
            Check.VENDOR_MATCH,
            f"Multiple vendors could match '{claimed}': {names}.",
            actual=claimed,
            expected=names,
        )
    else:
        match_result = review(
            Check.VENDOR_MATCH,
            f"Vendor '{claimed or 'unknown'}' was not found in the vendor register.",
            actual=claimed,
        )
    return [
        match_result,
        skipped(Check.VENDOR_STATUS, "Vendor not confirmed, status not checked."),
        skipped(Check.VENDOR_GSTIN, "Vendor not confirmed, GSTIN not checked."),
        skipped(Check.VENDOR_BANK, "Vendor not confirmed, bank details not checked."),
    ]


def _match_result(match: VendorMatch, vendor: Vendor, claimed: str | None) -> CheckResult:
    if match.kind == "GSTIN":
        similarity = fuzz.token_sort_ratio(
            normalize_vendor_name(claimed), vendor.normalized_name
        )
        if claimed and similarity < 70:
            return review(
                Check.VENDOR_MATCH,
                f"Matched {vendor.vendor_name} by GSTIN, but the invoice names "
                f"'{claimed}'. Please confirm.",
                expected=vendor.vendor_name,
                actual=claimed,
                status=CheckStatus.WARNING,
            )
        return passed(
            Check.VENDOR_MATCH,
            f"Vendor matched by GSTIN: {vendor.vendor_name} ({vendor.vendor_code}).",
            actual=vendor.vendor_name,
        )
    return passed(
        Check.VENDOR_MATCH,
        f"Vendor matched by name: {vendor.vendor_name} ({vendor.vendor_code}).",
        actual=vendor.vendor_name,
    )


def _status_result(vendor: Vendor) -> CheckResult:
    if vendor.status == VendorStatus.ACTIVE.value:
        return passed(Check.VENDOR_STATUS, "Vendor is active.", actual=vendor.status)
    if vendor.status == VendorStatus.INACTIVE.value:
        return reject(
            Check.VENDOR_STATUS,
            f"Vendor {vendor.vendor_name} is inactive and cannot be paid.",
            expected=VendorStatus.ACTIVE.value,
            actual=vendor.status,
        )
    return review(
        Check.VENDOR_STATUS,
        f"Vendor {vendor.vendor_name} is pending onboarding approval.",
        expected=VendorStatus.ACTIVE.value,
        actual=vendor.status,
    )


def _gstin_result(vendor: Vendor, invoice: Invoice, settings: Settings) -> CheckResult:
    printed = normalize_gstin(invoice.vendor_gstin_raw)
    invoice_gstin = repair_gstin(printed)
    repaired = f" (OCR misread {printed} corrected using the GSTIN layout and check digit)" if invoice_gstin != printed else ""
    if not invoice_gstin:
        message = "Vendor GSTIN is not shown on the invoice, so it could not be verified."
        if settings.require_gstin_for_approval:
            return review(Check.VENDOR_GSTIN, message, status=CheckStatus.WARNING)
        return passed(Check.VENDOR_GSTIN, message)
    if not GSTIN_PATTERN.match(invoice_gstin):
        return review(
            Check.VENDOR_GSTIN,
            "GSTIN on the invoice has an invalid format.",
            actual=invoice_gstin,
        )
    if not gstin_checksum_valid(invoice_gstin):
        return review(
            Check.VENDOR_GSTIN,
            "GSTIN on the invoice fails the GSTN check-digit validation — likely a typo, "
            "a scanning error or a fabricated registration.",
            expected=f"check digit {gstin_check_digit(invoice_gstin)}",
            actual=invoice_gstin,
        )
    if not vendor.gstin:
        return review(
            Check.VENDOR_GSTIN,
            "No GSTIN is registered for this vendor, so the invoice GSTIN could not be verified.",
            actual=invoice_gstin,
            status=CheckStatus.WARNING,
        )
    if vendor.gstin != invoice_gstin:
        return review(
            Check.VENDOR_GSTIN,
            "GSTIN on the invoice does not match the registered vendor GSTIN.",
            expected=vendor.gstin,
            actual=invoice_gstin,
        )
    return passed(
        Check.VENDOR_GSTIN, f"Vendor GSTIN matches the register{repaired}.", expected=vendor.gstin,
        actual=invoice_gstin,
    )  # fmt: skip


def _bank_result(vendor: Vendor, invoice: Invoice) -> CheckResult:
    """Bank-account change fraud control (the most common B2B payment-diversion scheme).

    Remittance details printed on an invoice are never trusted on their own: they must match the
    verified vendor master. A mismatch holds payment until the change is confirmed out-of-band.
    """
    printed = (invoice.extracted_data or {}).get("bank_account_details")
    account, ifsc = parse_bank_details(printed)
    if not account and not ifsc:
        return passed(
            Check.VENDOR_BANK,
            "No remittance details printed on the invoice; payment will use the verified vendor master.",
        )
    if not vendor.bank_account_number:
        return review(
            Check.VENDOR_BANK,
            "The invoice carries bank details but no verified account is on file for this vendor. "
            "Verify the account before first payment.",
            actual=_mask(account) if account else ifsc,
            status=CheckStatus.WARNING,
        )
    mismatches = []
    if account and account != vendor.bank_account_number:
        mismatches.append("account number")
    if ifsc and vendor.bank_ifsc and ifsc != vendor.bank_ifsc:
        mismatches.append("IFSC")
    if mismatches:
        return review(
            Check.VENDOR_BANK,
            f"Bank {' and '.join(mismatches)} on the invoice differ from the verified vendor master. "
            "Possible payment-diversion fraud: hold payment and confirm with the vendor by phone "
            "using contact details already on file.",
            expected=f"{_mask(vendor.bank_account_number)} / {vendor.bank_ifsc or '—'}",
            actual=f"{_mask(account) if account else '—'} / {ifsc or '—'}",
        )
    return passed(
        Check.VENDOR_BANK,
        "Bank details on the invoice match the verified vendor master.",
        expected=_mask(vendor.bank_account_number),
        actual=_mask(account) if account else ifsc,
    )


def _mask(account: str | None) -> str:
    if not account:
        return "—"
    return f"XXXX{account[-4:]}"
