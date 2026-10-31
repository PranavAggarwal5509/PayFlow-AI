from datetime import date
from decimal import Decimal
import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencies.providers import get_llm, get_storage
from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError
from app.core.security import CurrentUser, get_current_user
from app.database.session import get_db, get_session_factory
from app.models.enums import Stage
from app.models.invoice import Invoice
from app.repositories import invoice_repository as repo
from app.schemas.common import ApiResponse, page_meta
from app.schemas.invoice import InvoiceDetail, InvoiceListItem, UploadResult
from app.services import invoice_service, pipeline
from app.services.llm_extractor import LLMProvider
from app.storage import StorageBackend

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invoices", tags=["Invoices"])


def start_processing(settings: Settings, storage: StorageBackend, llm: LLMProvider, invoice_id: UUID, run_id: UUID):
    """Background task: execute the complete invoice processing pipeline directly."""
    try:
        with get_session_factory()() as db:
            pipeline.run_inline(pipeline.PipelineContext(db, settings, storage, llm), run_id)
    except Exception as exc:
        logger.exception("Background processing task failed for invoice %s, run %s", invoice_id, run_id)
        try:
            with get_session_factory()() as db:
                pipeline._persist_failure(
                    db,
                    run_id,
                    Stage.DOCUMENT_EXTRACTION,
                    f"Background task failed unexpectedly: {exc}",
                    "UNEXPECTED",
                )
        except Exception:
            logger.exception("Failed to persist background task fallback failure for run %s", run_id)


@router.post("/upload", response_model=ApiResponse[UploadResult], status_code=201)
async def upload_invoice(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    storage: StorageBackend = Depends(get_storage),
    llm: LLMProvider = Depends(get_llm),
    user: CurrentUser = Depends(get_current_user),
):
    # Read at most limit+1 bytes so an oversized upload is detected without buffering it all.
    data = await file.read(settings.max_upload_bytes + 1)
    invoice, run = invoice_service.create_invoice_from_upload(
        db, settings, storage, filename=file.filename, content_type=file.content_type,
        data=data, uploaded_by=user.id,
    )  # fmt: skip
    background_tasks.add_task(start_processing, settings, storage, llm, invoice.id, run.id)
    return ApiResponse(
        data=UploadResult(
            invoice_id=invoice.id, run_id=run.id, invoice_number=None,
            processing_status=invoice.processing_status,
        )
    )


@router.get("", response_model=ApiResponse[list[InvoiceListItem]])
def list_invoices(
    q: str | None = None,
    query: str | None = None,
    decision_status: str | None = None,
    processing_status: str | None = None,
    vendor_id: UUID | None = None,
    currency: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    min_amount: Decimal | None = None,
    max_amount: Decimal | None = None,
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
    po_number: str | None = None,
    sort_by: str = "uploaded_at",
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    search_query = q or query
    effective_min_amount = min_amount if min_amount is not None else amount_min
    effective_max_amount = max_amount if max_amount is not None else amount_max
    filters = repo.InvoiceFilters(
        q=search_query,
        decision_status=decision_status,
        processing_status=processing_status,
        vendor_id=vendor_id,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
        min_amount=effective_min_amount,
        max_amount=effective_max_amount,
        po_number=po_number,
    )
    items, total = repo.list_invoices(db, filters, sort_by, sort_dir == "desc", page, page_size)
    return ApiResponse(data=items, meta=page_meta(page, page_size, total))


@router.get("/{invoice_id}", response_model=ApiResponse[InvoiceDetail])
def get_invoice(
    invoice_id: UUID, db: Session = Depends(get_db), _: CurrentUser = Depends(get_current_user)
):
    detail = repo.get_invoice_detail(db, invoice_id)
    if detail is None:
        raise NotFoundError("Invoice not found.")
    return ApiResponse(data=detail)


@router.get("/{invoice_id}/document")
def get_invoice_document(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
    _: CurrentUser = Depends(get_current_user),
):
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise NotFoundError("Invoice not found.")
    try:
        path = storage.resolve_path(invoice.stored_file_path)
    except ValueError as exc:
        raise NotFoundError("Document not found.") from exc
    if not path.is_file():
        raise NotFoundError("Document file is missing from storage.")
    return FileResponse(
        path, media_type="application/pdf", filename=invoice.original_file_name,
        content_disposition_type="inline",
    )  # fmt: skip


@router.post("/{invoice_id}/retry", response_model=ApiResponse[UploadResult], status_code=202)
def retry_invoice(
    invoice_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    storage: StorageBackend = Depends(get_storage),
    llm: LLMProvider = Depends(get_llm),
    user: CurrentUser = Depends(get_current_user),
):
    run = invoice_service.create_retry_run(db, invoice_id, user_id=user.id)
    background_tasks.add_task(start_processing, settings, storage, llm, invoice_id, run.id)
    invoice = db.get(Invoice, invoice_id)
    assert invoice is not None
    return ApiResponse(
        data=UploadResult(
            invoice_id=invoice_id, run_id=run.id, invoice_number=invoice.invoice_number,
            processing_status=invoice.processing_status,
        )
    )
