"""Demo reset: remove every LIVE_UPLOAD invoice and everything that hangs off it.

Used by the "Reset demo" button so scenario PDFs can be processed again from a clean slate
(otherwise the exact-duplicate check would reject every re-upload).

Never touched: SEED_HISTORY invoices and their runs, vendors, purchase orders, users, settings.
Deletion runs in one transaction in foreign-key order; stored PDFs are removed afterwards and
only when no remaining invoice still references the same storage key.
"""

from dataclasses import asdict, dataclass

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.models.enums import RunStatus
from app.models.invoice import Invoice, InvoiceLineItem, LineItemReconciliation
from app.models.processing import (
    AuditLog,
    Decision,
    NotificationDraft,
    ProcessingRun,
    Review,
    StageEvent,
    ValidationResult,
)
from app.models.vendor_po import POAllocation, POLineAllocation
from app.services.audit_service import record_audit
from app.storage import StorageBackend

LIVE = "LIVE_UPLOAD"


@dataclass
class ResetSummary:
    invoices: int = 0
    runs: int = 0
    reviews: int = 0
    decisions: int = 0
    checks: int = 0
    po_allocations: int = 0
    email_drafts: int = 0
    audit_entries: int = 0
    files: int = 0
    seeded_invoices_kept: int = 0

    def as_dict(self) -> dict:
        return asdict(self)


def _count(db: Session, model, *conditions) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0


def preview(db: Session) -> ResetSummary:
    """What a reset would remove right now (nothing is changed)."""
    ids = list(db.scalars(select(Invoice.id).where(Invoice.source_origin == LIVE)))
    kept = _count(db, Invoice, Invoice.source_origin != LIVE)
    if not ids:
        return ResetSummary(seeded_invoices_kept=kept)
    run_ids = list(db.scalars(select(ProcessingRun.id).where(ProcessingRun.invoice_id.in_(ids))))
    return ResetSummary(
        invoices=len(ids),
        runs=len(run_ids),
        reviews=_count(db, Review, Review.invoice_id.in_(ids)),
        decisions=_count(db, Decision, Decision.invoice_id.in_(ids)),
        checks=_count(db, ValidationResult, ValidationResult.invoice_id.in_(ids)),
        po_allocations=_count(db, POAllocation, POAllocation.invoice_id.in_(ids))
        + _count(db, POLineAllocation, POLineAllocation.invoice_id.in_(ids)),
        email_drafts=_count(db, NotificationDraft, NotificationDraft.invoice_id.in_(ids)),
        audit_entries=_count(
            db, AuditLog, or_(AuditLog.invoice_id.in_(ids), AuditLog.processing_run_id.in_(run_ids or [None]))
        ),
        files=len(set(db.scalars(select(Invoice.stored_file_path).where(Invoice.id.in_(ids))))),
        seeded_invoices_kept=kept,
    )


def reset_live_uploads(db: Session, storage: StorageBackend, *, actor: str) -> ResetSummary:
    """Delete all live uploads atomically, then their files. Refuses while a run is still processing."""
    busy = db.scalar(
        select(func.count())
        .select_from(ProcessingRun)
        .join(Invoice, Invoice.id == ProcessingRun.invoice_id)
        .where(Invoice.source_origin == LIVE, ProcessingRun.status.in_([RunStatus.RUNNING.value, RunStatus.QUEUED.value]))
    )
    if busy:
        raise ConflictError("An invoice is still being processed. Wait for it to finish, then reset.")

    summary = preview(db)
    if summary.invoices == 0:
        return summary

    ids = list(db.scalars(select(Invoice.id).where(Invoice.source_origin == LIVE)))
    run_ids = list(db.scalars(select(ProcessingRun.id).where(ProcessingRun.invoice_id.in_(ids))))
    keys = set(db.scalars(select(Invoice.stored_file_path).where(Invoice.id.in_(ids))))
    still_used = set(
        db.scalars(select(Invoice.stored_file_path).where(Invoice.source_origin != LIVE, Invoice.stored_file_path.in_(keys)))
    )

    # Children first (foreign-key order), all in one transaction.
    for statement in (
        delete(POLineAllocation).where(POLineAllocation.invoice_id.in_(ids)),
        delete(LineItemReconciliation).where(LineItemReconciliation.invoice_id.in_(ids)),
        delete(POAllocation).where(POAllocation.invoice_id.in_(ids)),
        delete(Decision).where(Decision.invoice_id.in_(ids)),
        delete(ValidationResult).where(ValidationResult.invoice_id.in_(ids)),
        delete(Review).where(Review.invoice_id.in_(ids)),
        delete(NotificationDraft).where(NotificationDraft.invoice_id.in_(ids)),
        delete(AuditLog).where(or_(AuditLog.invoice_id.in_(ids), AuditLog.processing_run_id.in_(run_ids or [None]))),
        delete(StageEvent).where(StageEvent.run_id.in_(run_ids or [None])),
        delete(ProcessingRun).where(ProcessingRun.invoice_id.in_(ids)),
        delete(InvoiceLineItem).where(InvoiceLineItem.invoice_id.in_(ids)),
        delete(Invoice).where(Invoice.id.in_(ids)),
    ):
        db.execute(statement.execution_options(synchronize_session=False))
    record_audit(
        db, action="DEMO_RESET", actor_type="USER", actor_id=actor,
        description=f"Removed {summary.invoices} live demo invoice(s) and {summary.runs} run(s); seeded history kept.",
    )  # fmt: skip
    db.commit()

    # Files last: a failed delete leaves an orphan file, never a dangling database row.
    removed = 0
    for key in keys - still_used:
        if not key:
            continue
        try:
            storage.delete(key)
            removed += 1
        except Exception:  # noqa: BLE001 - best effort; the data reset already succeeded
            continue
    summary.files = removed
    return summary
