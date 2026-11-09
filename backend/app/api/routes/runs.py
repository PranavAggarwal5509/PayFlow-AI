import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import NotFoundError
from app.core.security import CurrentUser, Permission, require
from app.database.session import get_db, get_session_factory
from app.models.enums import RunStatus
from app.models.invoice import Invoice
from app.models.processing import Decision, ProcessingRun, StageEvent, ValidationResult
from app.repositories.invoice_repository import run_summary
from app.schemas.common import ApiResponse, page_meta
from app.schemas.invoice import (
    RunCheck,
    RunDecision,
    RunDetail,
    RunInvoiceSnapshot,
    RunSummary,
    StageEventOut,
)
from app.services.checks import LABELS

router = APIRouter(prefix="/runs", tags=["Processing"])

TERMINAL = {RunStatus.COMPLETED.value, RunStatus.FAILED.value}


def build_run_detail(db: Session, run: ProcessingRun) -> RunDetail:
    summary = run_summary(run, run.invoice)
    stages = db.scalars(
        select(StageEvent).where(StageEvent.run_id == run.id).order_by(StageEvent.started_at)
    )
    latest_number = db.scalar(
        select(func.max(ProcessingRun.run_number)).where(ProcessingRun.invoice_id == run.invoice_id)
    )
    checks = db.scalars(
        select(ValidationResult)
        .where(ValidationResult.processing_run_id == run.id)
        .order_by(ValidationResult.created_at)
    )
    decision = db.scalar(select(Decision).where(Decision.processing_run_id == run.id))
    invoice = run.invoice
    return RunDetail(
        **summary.model_dump(),
        stages=[StageEventOut.model_validate(s) for s in stages],
        can_retry=run.status == RunStatus.FAILED.value and run.run_number == latest_number,
        checks=[
            RunCheck(
                validation_type=c.validation_type,
                label=LABELS.get(c.validation_type, c.validation_type),
                stage=CHECK_STAGE.get(c.validation_type, "DATA_VALIDATION"),
                status=c.status,
                impact=c.impact,
                message=c.message,
                expected_value=c.expected_value,
                actual_value=c.actual_value,
            )
            for c in checks
        ],
        decision=RunDecision(status=decision.status, reasons=decision.reasons) if decision else None,
        invoice=RunInvoiceSnapshot(
            vendor_name=invoice.vendor.vendor_name if invoice.vendor else invoice.vendor_name_raw,
            vendor_matched=invoice.vendor_id is not None,
            total_amount=invoice.total_amount,
            currency=invoice.currency,
            po_number=invoice.purchase_order.po_number if invoice.purchase_order else invoice.po_number_raw,
            invoice_date=invoice.invoice_date,
            extraction_method=invoice.extraction_method,
            page_count=invoice.page_count,
            line_item_count=len(invoice.line_items),
        ),
    )


# Which pipeline stage produces each check (drives the per-stage breakdown in the live view).
CHECK_STAGE = {
    **dict.fromkeys(
        ["REQUIRED_FIELDS", "INVOICE_DATE", "CURRENCY_SUPPORTED", "AMOUNTS_VALID", "LINE_ITEMS_VALID",
         "EXTRACTION_QUALITY"], "DATA_VALIDATION"),
    **dict.fromkeys(["VENDOR_MATCH", "VENDOR_STATUS", "VENDOR_GSTIN", "VENDOR_BANK"], "VENDOR_VERIFICATION"),
    **dict.fromkeys(["PO_EXISTS", "PO_VENDOR", "PO_STATUS", "PO_CURRENCY", "PO_BALANCE", "PO_LINE_ITEMS"],
                    "PO_MATCHING"),
    **dict.fromkeys(["DUP_FILE", "DUP_BUSINESS", "DUP_POTENTIAL"], "DUPLICATE_CHECK"),
    **dict.fromkeys(["TOTAL_ARITHMETIC", "LINE_ITEM_MATH", "LINE_ITEMS_SUM", "TAX_RATES", "APPROVAL_LIMIT"],
                    "FINANCIAL_VALIDATION"),
}  # fmt: skip


@router.get("", response_model=ApiResponse[list[RunSummary]])
def list_runs(
    status: str | None = None,
    invoice_id: UUID | None = None,
    exclude_synthetic: bool = True,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require(Permission.INVOICES_VIEW)),
):
    stmt = select(ProcessingRun).join(Invoice, Invoice.id == ProcessingRun.invoice_id)
    if exclude_synthetic:
        stmt = stmt.where(
            Invoice.source_origin == "LIVE_UPLOAD",
            ProcessingRun.triggered_by != "seed_historical_harness",
        )
    if status:
        stmt = stmt.where(ProcessingRun.status == status)
    if invoice_id:
        stmt = stmt.where(ProcessingRun.invoice_id == invoice_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.options(selectinload(ProcessingRun.invoice))
        .order_by(ProcessingRun.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return ApiResponse(
        data=[run_summary(r, r.invoice) for r in rows], meta=page_meta(page, page_size, total)
    )


@router.get("/{run_id}", response_model=ApiResponse[RunDetail])
def get_run(run_id: UUID, db: Session = Depends(get_db), _: CurrentUser = Depends(require(Permission.INVOICES_VIEW))):
    run = db.get(ProcessingRun, run_id)
    if run is None:
        raise NotFoundError("Processing run not found.")
    return ApiResponse(data=build_run_detail(db, run))


def _snapshot(run_id: UUID) -> dict | None:
    with get_session_factory()() as db:
        run = db.get(ProcessingRun, run_id)
        if run is None:
            return None
        return json.loads(build_run_detail(db, run).model_dump_json())


@router.get("/{run_id}/events")
async def run_events(run_id: UUID, db: Session = Depends(get_db), _: CurrentUser = Depends(require(Permission.INVOICES_VIEW))):
    """Server-Sent Events carrying the real persisted run state (no simulated progress)."""
    if db.get(ProcessingRun, run_id) is None:
        raise NotFoundError("Processing run not found.")
    db.close()

    async def stream():
        last: str | None = None
        idle = 0
        for _ in range(2250):  # ≤ 15 min
            snapshot = await asyncio.to_thread(_snapshot, run_id)
            if snapshot is None:
                return
            payload = json.dumps(snapshot)
            if payload != last:
                last, idle = payload, 0
                yield f"event: run\ndata: {payload}\n\n"
                if snapshot["status"] in TERMINAL:
                    yield "event: done\ndata: {}\n\n"
                    return
            else:
                idle += 1
                if idle % 35 == 0:
                    yield ": keep-alive\n\n"
            await asyncio.sleep(0.4)

    return StreamingResponse(
        stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )  # fmt: skip


__all__ = ["Invoice", "router"]

