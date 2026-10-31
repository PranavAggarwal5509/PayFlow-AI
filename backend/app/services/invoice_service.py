"""Upload, retry, and background processing."""

import hashlib
import logging
import os
import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ConflictError, FileTooLargeError, NotFoundError, UnsupportedFileError
from app.models.enums import ProcessingStatus, RunStatus
from app.models.invoice import Invoice
from app.models.processing import ProcessingRun
from app.services import run_service
from app.services.audit_service import record_audit
from app.storage import StorageBackend

logger = logging.getLogger(__name__)

ALLOWED_MIME = {"application/pdf", "application/x-pdf"}


def _safe_name(filename: str | None) -> str:
    name = os.path.basename((filename or "invoice.pdf").replace("\\", "/"))
    name = re.sub(r"[^\w.\- ()]", "_", name).strip() or "invoice.pdf"
    return name[:255]


def validate_upload(filename: str | None, content_type: str | None, data: bytes, settings: Settings):
    if not filename or not filename.lower().endswith(".pdf"):
        raise UnsupportedFileError("Only PDF files (.pdf) are accepted.")
    if (content_type or "").split(";")[0].strip().lower() not in ALLOWED_MIME:
        raise UnsupportedFileError("The file type must be application/pdf.")
    if len(data) > settings.max_upload_bytes:
        raise FileTooLargeError(f"The file exceeds the {settings.max_upload_size_mb} MB limit.")
    if not data:
        raise UnsupportedFileError("The uploaded file is empty.")
    if not data.lstrip()[:5] == b"%PDF-":
        raise UnsupportedFileError("The file does not look like a PDF document.")


def create_invoice_from_upload(
    db: Session, settings: Settings, storage: StorageBackend, *,
    filename: str | None, content_type: str | None, data: bytes, uploaded_by: str,
) -> tuple[Invoice, ProcessingRun]:  # fmt: skip
    """Validate, store the file, and create the invoice + first run in one transaction."""
    validate_upload(filename, content_type, data, settings)
    key = storage.save(data)
    try:
        invoice = Invoice(
            original_file_name=_safe_name(filename),
            stored_file_path=key,
            file_size_bytes=len(data),
            file_hash=hashlib.sha256(data).hexdigest(),
            processing_status=ProcessingStatus.PROCESSING.value,
            uploaded_by=uploaded_by,
        )
        db.add(invoice)
        db.flush()
        run = run_service.create_run(db, invoice, triggered_by=uploaded_by)
        record_audit(
            db, action="INVOICE_UPLOADED", actor_type="USER", actor_id=uploaded_by,
            invoice_id=invoice.id, run_id=run.id, new_value=invoice.original_file_name,
            description=f"Uploaded {invoice.original_file_name} ({len(data):,} bytes).",
        )  # fmt: skip
        db.commit()
    except Exception:
        db.rollback()
        raise
    return invoice, run


def create_retry_run(db: Session, invoice_id: UUID, *, user_id: str) -> ProcessingRun:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise NotFoundError("Invoice not found.")
    latest = db.scalar(
        select(ProcessingRun)
        .where(ProcessingRun.invoice_id == invoice_id)
        .order_by(ProcessingRun.run_number.desc())
        .limit(1)
    )
    if latest is None or latest.status != RunStatus.FAILED.value:
        raise ConflictError("Only invoices whose latest processing run failed can be retried.")
    invoice.processing_status = ProcessingStatus.PROCESSING.value
    run = run_service.create_run(db, invoice, triggered_by=user_id)
    record_audit(
        db, action="RUN_RETRY", actor_type="USER", actor_id=user_id, invoice_id=invoice.id,
        run_id=run.id, old_value=str(latest.run_number), new_value=str(run.run_number),
        description=f"Retry of failed run #{latest.run_number}.",
    )  # fmt: skip
    db.commit()
    return run
