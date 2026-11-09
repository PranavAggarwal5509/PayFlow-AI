from datetime import date, datetime, time
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.core.errors import ForbiddenError, NotFoundError
from app.core.security import CurrentUser, Permission, require
from app.database.session import get_db
from app.models.enums import ReviewAction
from app.models.invoice import Invoice
from app.models.processing import Decision, Review
from app.repositories import invoice_repository as repo
from app.schemas.common import ApiResponse, page_meta
from app.schemas.invoice import ReviewDecisionIn, ReviewDetail, ReviewListItem, ReviewOut
from app.services import dashboard_service, review_service

router = APIRouter(prefix="/reviews", tags=["Reviews"])
dashboard = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", response_model=ApiResponse[list[ReviewListItem]])
def list_reviews(
    review_status: str | None = Query(None, description="OPEN, or a specific status"),
    issue_type: str | None = None,
    vendor_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require(Permission.INVOICES_VIEW)),
):
    stmt = select(Review).join(Invoice, Invoice.id == Review.invoice_id)
    if review_status == "OPEN":
        stmt = stmt.where(Review.review_status.in_(review_service.OPEN_STATUSES))
    elif review_status:
        stmt = stmt.where(Review.review_status == review_status)
    if issue_type:
        stmt = stmt.where(Review.issue_type == issue_type)
    if vendor_id:
        stmt = stmt.where(Invoice.vendor_id == vendor_id)
    if date_from:
        stmt = stmt.where(Invoice.uploaded_at >= datetime.combine(date_from, time.min))
    if date_to:
        stmt = stmt.where(Invoice.uploaded_at <= datetime.combine(date_to, time.max))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            Invoice.invoice_number.ilike(like) | Invoice.vendor_name_raw.ilike(like)
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    reviews = list(
        db.scalars(
            stmt.options(
                selectinload(Review.invoice).selectinload(Invoice.vendor),
                selectinload(Review.invoice).selectinload(Invoice.runs),
            )
            .order_by(Invoice.uploaded_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).unique()
    )
    # The run that sent each invoice to review = its latest NEEDS_REVIEW decision.
    invoice_ids = [r.invoice_id for r in reviews]
    review_runs: dict[UUID, UUID] = {}
    issues: dict[UUID, str] = {}
    flagged = db.scalars(
        select(Decision)
        .where(Decision.invoice_id.in_(invoice_ids), Decision.status == "NEEDS_REVIEW")
        .order_by(Decision.created_at)
    )
    for d in flagged:  # ascending, so the latest decision wins
        review_runs[d.invoice_id] = d.processing_run_id
        reason = next((x for x in d.reasons if x["severity"] != "INFO"), None)
        if reason:
            issues[d.invoice_id] = reason["message"]
    items = [
        ReviewListItem(
            id=r.id, invoice_id=r.invoice_id, invoice_number=r.invoice.invoice_number,
            vendor_name=r.invoice.vendor.vendor_name if r.invoice.vendor else r.invoice.vendor_name_raw,
            currency=r.invoice.currency, total_amount=r.invoice.total_amount,
            issue=issues.get(r.invoice_id), issue_type=r.issue_type,
            uploaded_at=r.invoice.uploaded_at, review_status=r.review_status,
            review_run_id=review_runs.get(r.invoice_id) or (r.invoice.runs[-1].id if r.invoice.runs else None),
        )  # fmt: skip
        for r in reviews
    ]
    return ApiResponse(data=items, meta=page_meta(page, page_size, total))


@router.get("/{review_id}", response_model=ApiResponse[ReviewDetail])
def get_review(review_id: UUID, db: Session = Depends(get_db), _: CurrentUser = Depends(require(Permission.INVOICES_VIEW))):
    review = db.get(Review, review_id)
    if review is None:
        raise NotFoundError("Review not found.")
    detail = repo.get_invoice_detail(db, review.invoice_id)
    assert detail is not None
    return ApiResponse(data=ReviewDetail(review=ReviewOut.model_validate(review), invoice=detail))


@router.post("/{review_id}/decision", response_model=ApiResponse[ReviewOut])
def decide_review(
    review_id: UUID, body: ReviewDecisionIn, db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: CurrentUser = Depends(require(Permission.REVIEW_ACT)),
):  # fmt: skip
    _check_approval_authority(db, review_id, body.action, user)
    review = review_service.apply_review_decision(
        db, review_id, body.action, body.comment.strip(), user_id=user.id, settings=settings
    )
    return ApiResponse(data=ReviewOut.model_validate(review))


@dashboard.get("/stats")
def stats(
    days: int = Query(30, ge=1, le=365),
    source_origin: str = Query("ALL", description="ALL (default), LIVE_UPLOAD or SEED_HISTORY"),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require(Permission.INVOICES_VIEW)),
):
    from app.services.analytics_service import get_operational_metrics

    base_stats = dashboard_service.get_stats(db, dashboard_service.normalize_origin(source_origin))
    base_stats["analytics"] = get_operational_metrics(db, days=days)
    return ApiResponse(data=base_stats)


@dashboard.get("/developer-analytics")
def developer_analytics(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require(Permission.DEVELOPER_VIEW)),
):
    from app.services.analytics_service import get_operational_metrics

    metrics = get_operational_metrics(db, days=days)
    return ApiResponse(data=metrics)


@dashboard.get("/recent-activity")
def recent_activity(
    limit: int = Query(15, ge=1, le=50),
    source_origin: str = Query("ALL", description="ALL (default), LIVE_UPLOAD or SEED_HISTORY"),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require(Permission.INVOICES_VIEW)),
):
    origin = dashboard_service.normalize_origin(source_origin)
    return ApiResponse(data=dashboard_service.recent_activity(db, limit, origin))



def _check_approval_authority(db: Session, review_id: UUID, action: ReviewAction, user: CurrentUser) -> None:
    """Segregation of duties: only holders of review:approve_high_value may approve an invoice the
    rules engine flagged as above the auto-approval limit."""
    if action != ReviewAction.APPROVE or user.can(Permission.REVIEW_HIGH_VALUE):
        return
    review = db.get(Review, review_id)
    if review is None:
        return  # the service raises the proper 404
    decision = db.scalar(
        select(Decision).where(Decision.invoice_id == review.invoice_id).order_by(Decision.created_at.desc()).limit(1)
    )
    if decision and any(r.get("code") == "APPROVAL_LIMIT" for r in decision.reasons or []):
        raise ForbiddenError(
            "This invoice is above the auto-approval limit. Only a Finance Manager or Administrator can approve it."
        )
