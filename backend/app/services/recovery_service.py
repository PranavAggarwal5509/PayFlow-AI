"""Startup recovery of interrupted invoice processing runs.

When the backend restarts while invoice runs are in RUNNING or QUEUED state,
or when an invoice is left in PROCESSING state, this service safely marks them
as FAILED with explanatory error messages, closes active stages, keeps records
retryable, and appends audit logs.

Preserves financial integrity:
- Never changes an invoice that already reached a terminal business outcome (APPROVED, NEEDS_REVIEW, REJECTED).
- Never approves or rejects an invoice.
- Preserves committed PO allocations and historical records.
- Completely idempotent.
"""

import logging
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.base import utcnow
from app.models.enums import DecisionStatus, ProcessingStatus, RunStatus, Stage, StageStatus
from app.models.invoice import Invoice
from app.models.processing import ProcessingRun, StageEvent
from app.services.audit_service import record_audit

logger = logging.getLogger("payflow.recovery")

INTERRUPTED_ERROR_MESSAGE = "Processing interrupted by backend restart. Safe to retry."
INTERRUPTED_CATEGORY = "SERVER_RESTART"


def recover_interrupted_runs(db: Session) -> int:
    """Scan and recover unfinished processing runs and stuck invoices.

    Returns:
        The count of recovered runs.
    """
    now = utcnow()

    # Find runs left in QUEUED or RUNNING status
    interrupted_runs = list(
        db.scalars(
            select(ProcessingRun)
            .where(ProcessingRun.status.in_([RunStatus.QUEUED.value, RunStatus.RUNNING.value]))
            .order_by(ProcessingRun.started_at.asc())
        ).all()
    )

    recovered_count = 0
    for run in interrupted_runs:
        invoice = db.get(Invoice, run.invoice_id)

        # Mark any in-progress stage events as FAILED
        active_events = list(
            db.scalars(
                select(StageEvent).where(
                    StageEvent.run_id == run.id,
                    StageEvent.status == StageStatus.IN_PROGRESS.value,
                )
            ).all()
        )
        for ev in active_events:
            ev.status = StageStatus.FAILED.value
            ev.completed_at = now
            ev.message = (
                f"{ev.message} (Interrupted by backend restart)"
                if ev.message
                else "Interrupted by backend restart"
            )

        # Transition run to FAILED
        run.status = RunStatus.FAILED.value
        run.completed_at = now
        run.error_message = INTERRUPTED_ERROR_MESSAGE
        run.error_category = INTERRUPTED_CATEGORY

        # Update invoice processing status if it hasn't reached a terminal state
        if invoice is not None:
            # Only update processing_status to FAILED if not already completed/failed
            if invoice.processing_status == ProcessingStatus.PROCESSING.value:
                invoice.processing_status = ProcessingStatus.FAILED.value

        # Record audit log
        stage_desc = f" at stage '{run.current_stage}'" if run.current_stage else ""
        record_audit(
            db,
            action="RUN_FAILED",
            actor_type="SYSTEM",
            actor_id="startup_recovery",
            invoice_id=run.invoice_id,
            run_id=run.id,
            new_value=INTERRUPTED_CATEGORY,
            description=f"Processing run #{run.run_number} recovered after backend restart{stage_desc}.",
        )
        recovered_count += 1
        logger.warning(
            "Recovered interrupted run #%s for invoice %s (stage: %s)",
            run.run_number,
            run.invoice_id,
            run.current_stage,
        )

    # In addition, check for any orphan invoices in PROCESSING state that have no running run
    stuck_invoices = list(
        db.scalars(
            select(Invoice).where(Invoice.processing_status == ProcessingStatus.PROCESSING.value)
        ).all()
    )
    for inv in stuck_invoices:
        # Check if there is already a terminal run or no active run
        active_run = db.scalar(
            select(ProcessingRun).where(
                ProcessingRun.invoice_id == inv.id,
                ProcessingRun.status.in_([RunStatus.QUEUED.value, RunStatus.RUNNING.value]),
            )
        )
        if not active_run:
            inv.processing_status = ProcessingStatus.FAILED.value
            record_audit(
                db,
                action="INVOICE_RECOVERED",
                actor_type="SYSTEM",
                actor_id="startup_recovery",
                invoice_id=inv.id,
                description="Invoice reset from stuck PROCESSING status to FAILED after backend restart.",
            )
            logger.warning("Recovered stuck PROCESSING status for invoice %s", inv.id)

    db.commit()
    return recovered_count

