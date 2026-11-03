"""Processing pipeline stages.

Each function is one workflow stage. They are called by the internal API (n8n) — or, in
`WORKFLOW_MODE=inline`, by `run_inline`. Every stage:
  * is idempotent (safe to retry),
  * persists its own results and stage status,
  * never decides an invoice outcome except `stage_decision` via the decision engine.
"""

import hashlib
import logging
import time
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ConflictError, ProcessingError, TransientError
from app.core.logging import bind_context
from app.models.enums import (
    CheckStatus,
    DecisionStatus,
    Impact,
    ProcessingStatus,
    ReviewStatus,
    RunStatus,
    Stage,
    StageStatus,
)
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.processing import Decision, ProcessingRun, Review, ValidationResult
from app.schemas.extraction import ExtractedInvoice
from app.services import (
    duplicate_detector,
    ocr_service,
    pdf_extractor,
    po_matcher,
    run_service,
    validation_engine,
    vendor_service,
)
from app.services.audit_service import record_audit
from app.services.checks import Check, CheckResult
from app.services.decision_engine import DecisionOutcome, DecisionReason, decide
from app.services.llm_extractor import LLMProvider, extract_structured_invoice
from app.storage import StorageBackend
from app.utils.dates import parse_date

logger = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    db: Session
    settings: Settings
    storage: StorageBackend
    llm: LLMProvider


# --------------------------------------------------------------- stage plumbing
def load_active_run(db: Session, run_id: object, *, must_be_running: bool = True) -> ProcessingRun:
    run = db.get(ProcessingRun, run_id)
    if run is None:
        raise ConflictError("Processing run not found.")
    if must_be_running and run.status != RunStatus.RUNNING.value:
        raise ConflictError(f"Run is {run.status}; it cannot accept further stages.")
    bind_context(invoice_id=run.invoice_id, run_id=run.id)
    return run


def execute_stage(ctx: PipelineContext, run: ProcessingRun, stage: Stage, action):
    """Run `action` with uniform error mapping.

    * ProcessingError  → run FAILED (permanent), re-raised as HTTP 422
    * TransientError / DB outage → rollback, state untouched, HTTP 503 so n8n retries
    * anything else    → run FAILED with a generic message; details only in the log
    """
    bind_context(stage=stage.value)
    db = ctx.db
    try:
        run_service.begin_stage(db, run, stage)
        result = action()
        db.commit()
        return result
    except ProcessingError as exc:
        db.rollback()
        _persist_failure(db, run.id, stage, exc.message, exc.category)
        raise
    except TransientError:
        db.rollback()
        raise
    except OperationalError as exc:
        db.rollback()
        logger.error("Database unavailable", extra={"error_category": "DATABASE"})
        raise TransientError("Database temporarily unavailable.", category="DATABASE") from exc
    except Exception as exc:
        db.rollback()
        logger.exception("Unexpected stage failure", extra={"error_category": "UNEXPECTED"})
        message = "An unexpected error occurred while processing this invoice."
        _persist_failure(db, run.id, stage, message, "UNEXPECTED")
        raise ProcessingError(message, category="UNEXPECTED") from exc


def _persist_failure(db: Session, run_id: object, stage: Stage, message: str, category: str) -> None:
    run = db.get(ProcessingRun, run_id)
    if run is not None and run.status != RunStatus.FAILED.value:
        run_service.fail_run(db, run, stage, message, category)
        db.commit()


def _save_results(
    db: Session, run: ProcessingRun, results: list[CheckResult], stage: Stage
) -> StageStatus:
    """Replace this run's rows for these check types (idempotent) and return the stage status."""
    types = [r.validation_type for r in results]
    db.execute(
        delete(ValidationResult).where(
            ValidationResult.processing_run_id == run.id,
            ValidationResult.validation_type.in_(types),
        )
    )
    for r in results:
        db.add(
            ValidationResult(
                invoice_id=run.invoice_id,
                processing_run_id=run.id,
                validation_type=r.validation_type,
                status=r.status.value,
                impact=r.impact.value,
                expected_value=r.expected_value,
                actual_value=r.actual_value,
                message=r.message,
            )
        )
    attention = any(r.status in (CheckStatus.FAILED, CheckStatus.WARNING) for r in results)
    status = StageStatus.NEEDS_ATTENTION if attention else StageStatus.COMPLETED
    run_service.finish_stage(db, run, stage, status, _stage_summary(results))
    return status


def _stage_summary(results: list[CheckResult]) -> str:
    issues = [r.message for r in results if r.status in (CheckStatus.FAILED, CheckStatus.WARNING)]
    return issues[0] if issues else "All checks passed."


def _invoice(db: Session, run: ProcessingRun) -> Invoice:
    invoice = db.get(Invoice, run.invoice_id)
    assert invoice is not None
    return invoice


# ----------------------------------------------------------------------- stages
def stage_document_extraction(ctx: PipelineContext, run: ProcessingRun, *, allow_ocr: bool) -> dict:
    def action() -> dict:
        invoice = _invoice(ctx.db, run)
        if invoice.extracted_text:  # already extracted in a previous run — reuse
            run_service.finish_stage(
                ctx.db, run, Stage.DOCUMENT_EXTRACTION, StageStatus.COMPLETED, "Reused existing text."
            )
            return _doc_info(invoice, needs_ocr=False)

        pdf_bytes = ctx.storage.read(invoice.stored_file_path)
        document = pdf_extractor.extract_text(pdf_bytes)
        if not pdf_extractor.is_text_sufficient(document, ctx.settings.ocr_min_chars_per_page):
            if not allow_ocr:
                return {"needs_ocr": True, "method": "TEXT", "page_count": document.page_count}
            document = ocr_service.ocr_document(pdf_bytes, ctx.settings.ocr_dpi)

        invoice.extracted_text = document.text
        invoice.extraction_method = document.method
        invoice.page_count = document.page_count
        run_service.finish_stage(
            ctx.db, run, Stage.DOCUMENT_EXTRACTION, StageStatus.COMPLETED,
            f"Read {document.page_count} page(s) using {document.method}.",
        )  # fmt: skip
        return _doc_info(invoice, needs_ocr=False)

    return execute_stage(ctx, run, Stage.DOCUMENT_EXTRACTION, action)


def _doc_info(invoice: Invoice, *, needs_ocr: bool) -> dict:
    return {
        "needs_ocr": needs_ocr,
        "method": invoice.extraction_method,
        "page_count": invoice.page_count,
        "characters": len(invoice.extracted_text or ""),
    }


def stage_ai_extraction(ctx: PipelineContext, run: ProcessingRun) -> dict:
    def action() -> dict:
        invoice = _invoice(ctx.db, run)
        if not invoice.extracted_text:
            raise ProcessingError("No document text is available to extract from.", category="NO_TEXT")
        text_hash = hashlib.sha256(invoice.extracted_text.encode()).hexdigest()
        reused = invoice.extracted_data is not None and invoice.extraction_text_hash == text_hash
        start_t = time.perf_counter()
        if not reused:  # avoid paying for the same extraction twice
            extracted = extract_structured_invoice(
                ctx.llm, invoice.extracted_text, max_retries=ctx.settings.gemini_max_retries
            )
            apply_extraction(ctx.db, invoice, extracted)
            invoice.extraction_text_hash = text_hash

            # Record LLM token telemetry if provided by the model provider
            telemetry = getattr(extracted, "_telemetry", None)
            if telemetry and isinstance(telemetry, dict):
                run.prompt_tokens = telemetry.get("prompt_tokens")
                run.completion_tokens = telemetry.get("completion_tokens")
                run.total_tokens = telemetry.get("total_tokens")

        # Extract visual evidence locally from PDF/OCR layout
        try:
            pdf_bytes = ctx.storage.read(invoice.stored_file_path)
            from app.services.document_layout import extract_ocr_layout, extract_pdf_layout
            from app.services.evidence_service import build_invoice_visual_evidence

            if invoice.extraction_method == "OCR":
                layout = extract_ocr_layout(pdf_bytes)
            else:
                layout = extract_pdf_layout(pdf_bytes)
            if invoice.extracted_data:
                invoice.visual_evidence = build_invoice_visual_evidence(invoice.extracted_data, layout)
        except Exception as e:
            logger.warning("Could not extract visual layout coordinates: %s", e)

        duration_ms = int((time.perf_counter() - start_t) * 1000)
        run.extraction_duration_ms = duration_ms
        if ctx.settings.llm_provider == "gemini":
            run.llm_model = ctx.settings.gemini_model
        else:
            run.llm_model = "mock-catalog"

        run_service.finish_stage(
            ctx.db, run, Stage.AI_EXTRACTION, StageStatus.COMPLETED,
            "Reused previous extraction." if reused else "Structured data extracted.",
        )  # fmt: skip
        record_audit(
            ctx.db, action="AI_EXTRACTION", actor_type="WORKFLOW", invoice_id=invoice.id,
            run_id=run.id, description="Reused previous extraction." if reused else "Extracted fields via LLM.",
        )  # fmt: skip
        return {"reused": reused, "invoice_number": invoice.invoice_number}

    return execute_stage(ctx, run, Stage.AI_EXTRACTION, action)


def apply_extraction(db: Session, invoice: Invoice, data: ExtractedInvoice) -> None:
    """Copy validated LLM output onto the invoice. Values are stored as extracted, never fixed."""
    invoice.invoice_number = data.invoice_number
    invoice.vendor_name_raw = data.vendor_name
    invoice.vendor_gstin_raw = data.vendor_gstin
    invoice.po_number_raw = data.purchase_order_number
    invoice.invoice_date = parse_date(data.invoice_date)
    invoice.due_date = parse_date(data.due_date)
    invoice.currency = data.currency
    invoice.subtotal = data.subtotal
    invoice.tax_amount = data.tax_amount
    invoice.total_amount = data.total_amount
    invoice.extracted_data = data.model_dump(mode="json")
    db.execute(delete(InvoiceLineItem).where(InvoiceLineItem.invoice_id == invoice.id))
    invoice.line_items = [
        InvoiceLineItem(
            position=index,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            tax_percentage=item.tax_percentage,
            total_amount=item.total_amount,
        )
        for index, item in enumerate(data.line_items)
    ]


def stage_validate(ctx: PipelineContext, run: ProcessingRun, scope: str) -> list[CheckResult]:
    stage = Stage.DATA_VALIDATION if scope == "data" else Stage.FINANCIAL_VALIDATION

    def action() -> list[CheckResult]:
        invoice = _invoice(ctx.db, run)
        if scope == "data":
            results = validation_engine.validate_data(invoice, ctx.settings)
        else:
            results = validation_engine.validate_financials(invoice, ctx.settings)
        _save_results(ctx.db, run, results, stage)
        return results

    return execute_stage(ctx, run, stage, action)


def stage_vendor_check(ctx: PipelineContext, run: ProcessingRun) -> list[CheckResult]:
    def action() -> list[CheckResult]:
        invoice = _invoice(ctx.db, run)
        results = vendor_service.verify_vendor(ctx.db, invoice, ctx.settings)
        _save_results(ctx.db, run, results, Stage.VENDOR_VERIFICATION)
        return results

    return execute_stage(ctx, run, Stage.VENDOR_VERIFICATION, action)


def stage_po_match(ctx: PipelineContext, run: ProcessingRun) -> list[CheckResult]:
    def action() -> list[CheckResult]:
        invoice = _invoice(ctx.db, run)
        results = po_matcher.match_purchase_order(ctx.db, invoice)
        _save_results(ctx.db, run, results, Stage.PO_MATCHING)
        return results

    return execute_stage(ctx, run, Stage.PO_MATCHING, action)


def stage_duplicate_check(ctx: PipelineContext, run: ProcessingRun) -> list[CheckResult]:
    def action() -> list[CheckResult]:
        invoice = _invoice(ctx.db, run)
        results = duplicate_detector.detect_duplicates(ctx.db, invoice, ctx.settings)
        _save_results(ctx.db, run, results, Stage.DUPLICATE_CHECK)
        return results

    return execute_stage(ctx, run, Stage.DUPLICATE_CHECK, action)


def load_run_results(db: Session, run_id: object) -> list[CheckResult]:
    rows = db.scalars(select(ValidationResult).where(ValidationResult.processing_run_id == run_id))
    return [
        CheckResult(
            validation_type=r.validation_type,
            status=CheckStatus(r.status),
            impact=Impact(r.impact),
            message=r.message,
            expected_value=r.expected_value,
            actual_value=r.actual_value,
        )
        for r in rows
    ]


def stage_decision(ctx: PipelineContext, run: ProcessingRun) -> DecisionOutcome:
    def action() -> DecisionOutcome:
        db = ctx.db
        invoice = _invoice(db, run)
        existing = db.scalar(select(Decision).where(Decision.processing_run_id == run.id))
        if existing:  # idempotent: the decision for a run is made exactly once
            return DecisionOutcome(
                DecisionStatus(existing.status),
                [DecisionReason(**r) for r in existing.reasons],
            )

        outcome = decide(load_run_results(db, run.id), ctx.settings)
        if outcome.status == DecisionStatus.APPROVED:
            tol = (
                ctx.settings.inr_rounding_tolerance
                if invoice.currency == "INR"
                else ctx.settings.default_rounding_tolerance
            )
            outcome = _allocate_or_downgrade(db, invoice, outcome, tolerance=tol)

        db.add(
            Decision(
                invoice_id=invoice.id,
                processing_run_id=run.id,
                status=outcome.status.value,
                reasons=[r.as_dict() for r in outcome.reasons],
            )
        )
        invoice.decision_status = outcome.status.value
        invoice.processing_status = ProcessingStatus.COMPLETED.value
        if outcome.status == DecisionStatus.NEEDS_REVIEW:
            _open_review(db, invoice, outcome)
        record_audit(
            db, action="DECISION", actor_type="SYSTEM", invoice_id=invoice.id, run_id=run.id,
            new_value=outcome.status.value,
            description="; ".join(r.message for r in outcome.reasons if r.severity != "INFO")
            or "All checks passed.",
        )  # fmt: skip
        stage_status = (
            StageStatus.COMPLETED
            if outcome.status == DecisionStatus.APPROVED
            else StageStatus.NEEDS_ATTENTION
        )
        run_service.finish_stage(db, run, Stage.DECISION, stage_status, outcome.status.value)
        run_service.complete_run(db, run)
        return outcome

    return execute_stage(ctx, run, Stage.DECISION, action)


def _allocate_or_downgrade(
    db: Session, invoice: Invoice, outcome: DecisionOutcome, tolerance: Decimal = Decimal("0")
) -> DecisionOutcome:
    """Reserve PO balance under a row lock. If another invoice consumed it first → NEEDS_REVIEW."""
    try:
        po_matcher.allocate_to_po(db, invoice, allocated_by="system", tolerance=tolerance)
    except ValueError as exc:
        reasons = [DecisionReason(Check.PO_BALANCE, "BLOCKING", str(exc)), *outcome.reasons]
        return DecisionOutcome(DecisionStatus.NEEDS_REVIEW, reasons)
    return outcome


def _open_review(db: Session, invoice: Invoice, outcome: DecisionOutcome) -> None:
    if db.scalar(select(Review).where(Review.invoice_id == invoice.id)):
        return
    db.add(
        Review(
            invoice_id=invoice.id,
            review_status=ReviewStatus.PENDING.value,
            issue_type=outcome.issue_type,
        )
    )


def amount_or_zero(value: Decimal | None) -> Decimal:
    return value if value is not None else Decimal("0")


# -------------------------------------------------------------- inline execution
def run_inline(ctx: PipelineContext, run_id: object) -> None:
    """Sequential in-process execution of the invoice verification pipeline."""
    if not run_service.claim_run(ctx.db, run_id):
        return
    run = load_active_run(ctx.db, run_id)
    try:
        info = stage_document_extraction(ctx, run, allow_ocr=False)
        if info["needs_ocr"]:
            stage_document_extraction(ctx, run, allow_ocr=True)
        stage_ai_extraction(ctx, run)
        stage_validate(ctx, run, "data")
        stage_vendor_check(ctx, run)
        stage_po_match(ctx, run)
        stage_duplicate_check(ctx, run)
        stage_validate(ctx, run, "financial")
        stage_decision(ctx, run)
    except ProcessingError:
        pass  # already persisted as a FAILED run with audit
    except TransientError as exc:
        _persist_failure(
            ctx.db,
            run.id,
            Stage(run.current_stage or Stage.UPLOAD_RECEIVED.value),
            exc.message,
            exc.category,
        )
    except Exception as exc:
        logger.exception("Unexpected pipeline failure during run %s", run_id)
        current = run.current_stage or Stage.UPLOAD_RECEIVED.value
        try:
            stage_enum = Stage(current)
        except ValueError:
            stage_enum = Stage.DOCUMENT_EXTRACTION
        _persist_failure(
            ctx.db,
            run.id,
            stage_enum,
            f"An unexpected error occurred during processing: {exc}",
            "UNEXPECTED",
        )
