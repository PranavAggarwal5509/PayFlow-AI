"""Deterministic decision engine.

Input: the persisted check results of one run. Output: status + explainable reasons.
No LLM and no workflow expression ever sets a decision; they can only call this function.

Rules (in priority order):
  1. Any FAILED check with impact REJECT                      → REJECTED  (hard-failure rules only)
  2. Any FAILED/WARNING check with impact REVIEW, or any
     approval-critical check missing / not performed          → NEEDS_REVIEW
  3. Otherwise                                                → APPROVED
"""

from dataclasses import dataclass, field

from app.core.config import Settings
from app.models.enums import CheckStatus, DecisionStatus, Impact
from app.services.checks import LABELS, Check, CheckResult

REQUIRED_FOR_APPROVAL = (
    Check.REQUIRED_FIELDS, Check.CURRENCY_SUPPORTED, Check.AMOUNTS_VALID, Check.TOTAL_ARITHMETIC,
    Check.VENDOR_MATCH, Check.VENDOR_STATUS, Check.PO_EXISTS, Check.PO_VENDOR, Check.PO_STATUS,
    Check.PO_CURRENCY, Check.PO_BALANCE, Check.PO_LINE_ITEMS, Check.DUP_FILE, Check.DUP_BUSINESS, Check.DUP_POTENTIAL,
)  # fmt: skip


@dataclass
class DecisionReason:
    code: str
    severity: str  # BLOCKING | WARNING | INFO
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "severity": self.severity, "message": self.message}


@dataclass
class DecisionOutcome:
    status: DecisionStatus
    reasons: list[DecisionReason] = field(default_factory=list)

    @property
    def issue_type(self) -> str | None:
        """Primary issue code, used to categorise the review queue."""
        for reason in self.reasons:
            if reason.severity in ("BLOCKING", "WARNING"):
                return reason.code
        return None


def decide(results: list[CheckResult], settings: Settings) -> DecisionOutcome:
    by_type = {r.validation_type: r for r in results}
    rejects = [r for r in results if r.status == CheckStatus.FAILED and r.impact == Impact.REJECT]
    reviews = [
        r
        for r in results
        if r.status in (CheckStatus.FAILED, CheckStatus.WARNING) and r.impact == Impact.REVIEW
    ]

    reasons: list[DecisionReason] = []
    reasons += [DecisionReason(r.validation_type, "BLOCKING", r.message) for r in rejects]
    reasons += [
        DecisionReason(
            r.validation_type,
            "BLOCKING" if r.status == CheckStatus.FAILED else "WARNING",
            r.message,
        )
        for r in reviews
    ]

    required = list(REQUIRED_FOR_APPROVAL)
    if settings.require_gstin_for_approval:
        required.append(Check.VENDOR_GSTIN)
    not_done = [
        code
        for code in required
        if code not in by_type or by_type[code].status == CheckStatus.SKIPPED
    ]

    if rejects:
        status = DecisionStatus.REJECTED
    elif reviews:
        status = DecisionStatus.NEEDS_REVIEW
    elif not_done:
        status = DecisionStatus.NEEDS_REVIEW
        reasons += [
            DecisionReason(code, "WARNING", f"{LABELS.get(code, code)} could not be completed.")
            for code in not_done
        ]
    else:
        status = DecisionStatus.APPROVED

    # Positive context so reviewers see what *did* work.
    reasons += [
        DecisionReason(r.validation_type, "INFO", r.message)
        for r in results
        if r.status == CheckStatus.PASSED
    ]
    return DecisionOutcome(status=status, reasons=reasons)

