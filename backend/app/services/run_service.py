"""Processing-run lifecycle and stage tracking (what the live progress tracker reads)."""

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.database.base import utcnow
from app.models.enums import ProcessingStatus, RunStatus, Stage, StageStatus
from app.models.invoice import Invoice
from app.models.processing import ProcessingRun, StageEvent
from app.services.audit_service import record_audit


def create_run(db: Session, invoice: Invoice, *, triggered_by: str) -> ProcessingRun:
    next_number = (
        db.scalar(
            select(func.coalesce(func.max(ProcessingRun.run_number), 0)).where(
                ProcessingRun.invoice_id == invoice.id
            )
        )
        or 0
    ) + 1
    run = ProcessingRun(
        id=uuid.uuid4(),
        invoice_id=invoice.id,
        run_number=next_number,
        status=RunStatus.QUEUED.value,
        current_stage=Stage.UPLOAD_RECEIVED.value,
        triggered_by=triggered_by,
    )
    db.add(run)
    db.flush()
    now = utcnow()
    db.add(
        StageEvent(
            run_id=run.id,
            stage=Stage.UPLOAD_RECEIVED.value,
            status=StageStatus.COMPLETED.value,
            started_at=now,
            completed_at=now,
            message="Invoice received.",
        )
    )
    record_audit(
        db,
        action="RUN_CREATED",
        actor_type="USER" if triggered_by != "system" else "SYSTEM",
        actor_id=triggered_by,
        invoice_id=invoice.id,
        run_id=run.id,
        description=f"Processing run #{next_number} created.",
    )
    return run


def claim_run(db: Session, run_id: uuid.UUID) -> bool:
    """Atomically move QUEUED → RUNNING. Returns False if another worker already claimed it.

    This is the guard against duplicate or concurrent triggers for the same run.
    """
    result = db.execute(
        update(ProcessingRun)
        .where(ProcessingRun.id == run_id, ProcessingRun.status == RunStatus.QUEUED.value)
        .values(status=RunStatus.RUNNING.value)
    )
    claimed = result.rowcount == 1
    if claimed:
        run = db.get(ProcessingRun, run_id)
        assert run is not None
        record_audit(
            db, action="RUN_STARTED", actor_type="WORKFLOW", invoice_id=run.invoice_id, run_id=run_id,
            description="Workflow claimed the processing run.",
        )  # fmt: skip
    db.commit()
    return claimed


def _get_event(db: Session, run: ProcessingRun, stage: str) -> StageEvent | None:
    return db.scalar(
        select(StageEvent).where(StageEvent.run_id == run.id, StageEvent.stage == stage)
    )


def begin_stage(db: Session, run: ProcessingRun, stage: Stage, message: str | None = None) -> None:
    """Idempotently mark a stage IN_PROGRESS (does not downgrade a finished stage)."""
    run.current_stage = stage.value
    event = _get_event(db, run, stage.value)
    if event is None:
        db.add(
            StageEvent(
                run_id=run.id, stage=stage.value, status=StageStatus.IN_PROGRESS.value,
                started_at=utcnow(), message=message,
            )
        )  # fmt: skip
    elif event.status in (StageStatus.FAILED.value, StageStatus.COMPLETED.value):
        # A re-entry (e.g. stage retry) restarts the stage.
        event.status = StageStatus.IN_PROGRESS.value
        event.completed_at = None
        event.started_at = utcnow()
    db.flush()


def finish_stage(
    db: Session, run: ProcessingRun, stage: Stage, status: StageStatus, message: str | None = None
) -> None:
    event = _get_event(db, run, stage.value)
    if event is None:
        event = StageEvent(run_id=run.id, stage=stage.value, started_at=utcnow(), status=status.value)
        db.add(event)
    event.status = status.value
    event.message = message
    if status != StageStatus.IN_PROGRESS:
        event.completed_at = utcnow()
    db.flush()


def fail_run(
    db: Session, run: ProcessingRun, stage: Stage, message: str, category: str = "UNEXPECTED"
) -> None:
    """Technical failure: visible to the UI, retryable, and never a business REJECTED."""
    finish_stage(db, run, stage, StageStatus.FAILED, message)
    run.status = RunStatus.FAILED.value
    run.current_stage = stage.value
    run.error_message = message
    run.error_category = category
    run.completed_at = utcnow()
    invoice = db.get(Invoice, run.invoice_id)
    if invoice is not None:
        invoice.processing_status = ProcessingStatus.FAILED.value
    record_audit(
        db, action="RUN_FAILED", actor_type="WORKFLOW", invoice_id=run.invoice_id, run_id=run.id,
        new_value=category, description=f"{stage.value}: {message}",
    )  # fmt: skip


def complete_run(db: Session, run: ProcessingRun) -> None:
    run.status = RunStatus.COMPLETED.value
    run.completed_at = utcnow()
    record_audit(
        db, action="RUN_COMPLETED", actor_type="WORKFLOW", invoice_id=run.invoice_id, run_id=run.id,
        description="Processing run completed.",
    )  # fmt: skip

