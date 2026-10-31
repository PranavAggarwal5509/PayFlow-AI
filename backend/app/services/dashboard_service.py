"""Dashboard aggregates — all computed from the database, nothing hardcoded."""

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.database.base import utcnow
from app.models.enums import DecisionStatus, ProcessingStatus, ReviewStatus, RunStatus
from app.models.invoice import Invoice
from app.models.processing import AuditLog, ProcessingRun, Review

PERIOD_DAYS = 30


def _count(db: Session, *conditions) -> int:
    return db.scalar(select(func.count(Invoice.id)).where(*conditions)) or 0


def _delta(current: int, previous: int) -> float | None:
    if previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


def get_stats(db: Session) -> dict:
    now = utcnow()
    cur_start = now - timedelta(days=PERIOD_DAYS)
    prev_start = now - timedelta(days=PERIOD_DAYS * 2)

    def period_counts(*conditions) -> tuple[int, int]:
        current = _count(db, Invoice.uploaded_at >= cur_start, *conditions)
        previous = _count(
            db, Invoice.uploaded_at >= prev_start, Invoice.uploaded_at < cur_start, *conditions
        )
        return current, previous

    approved = DecisionStatus.APPROVED.value
    needs_review = DecisionStatus.NEEDS_REVIEW.value
    rejected = DecisionStatus.REJECTED.value
    failed = ProcessingStatus.FAILED.value

    kpis = {}
    for key, conditions in {
        "total": (),
        "approved": (Invoice.decision_status == approved,),
        "needs_review": (Invoice.decision_status == needs_review,),
        "rejected": (Invoice.decision_status == rejected,),
        "failed": (Invoice.processing_status == failed,),
    }.items():
        cur, prev = period_counts(*conditions)
        kpis[key] = {
            "value": _count(db, *conditions),
            "change_percent": _delta(cur, prev),
            "last_30_days": cur,
        }

    decided = kpis["approved"]["value"] + kpis["rejected"]["value"] + kpis["needs_review"]["value"]
    approval_rate = round(kpis["approved"]["value"] / decided * 100, 1) if decided else None

    value_by_currency = {
        currency: Decimal(total)
        for currency, total in db.execute(
            select(Invoice.currency, func.coalesce(func.sum(Invoice.total_amount), 0))
            .where(Invoice.currency.is_not(None))
            .group_by(Invoice.currency)
        )
    }

    pending_reviews = (
        db.scalar(
            select(func.count(Review.id)).where(
                Review.review_status.in_(
                    [ReviewStatus.PENDING.value, ReviewStatus.CLARIFICATION_REQUESTED.value]
                )
            )
        )
        or 0
    )

    return {
        "kpis": kpis,
        "approval_rate": approval_rate,
        "pending_reviews": pending_reviews,
        "total_value_by_currency": value_by_currency,
        "average_processing_seconds": _average_processing_seconds(db),
        "monthly_volume": _monthly(db),
        "daily_volume": _daily(db, now - timedelta(days=PERIOD_DAYS - 1)),
        "decision_distribution": _distribution(db),
        "recent_failed_runs": _recent_failed(db),
    }


def _average_processing_seconds(db: Session) -> float | None:
    rows = db.execute(
        select(ProcessingRun.started_at, ProcessingRun.completed_at)
        .where(ProcessingRun.status == RunStatus.COMPLETED.value)
        .order_by(ProcessingRun.completed_at.desc())
        .limit(200)
    ).all()
    durations = [(c.replace(tzinfo=None) - s.replace(tzinfo=None)).total_seconds() for s, c in rows if c]
    return round(sum(durations) / len(durations), 1) if durations else None


def _monthly(db: Session) -> list[dict]:
    year, month = extract("year", Invoice.uploaded_at), extract("month", Invoice.uploaded_at)
    rows = db.execute(
        select(
            year.label("y"), month.label("m"), func.count(Invoice.id),
            func.coalesce(func.sum(Invoice.total_amount), 0),
        )  # fmt: skip
        .group_by("y", "m")
        .order_by("y", "m")
    ).all()
    return [
        {"month": f"{int(y):04d}-{int(m):02d}", "count": count, "value": Decimal(value)}
        for y, m, count, value in rows[-12:]
    ]


def _daily(db: Session, since) -> list[dict]:
    year = extract("year", Invoice.uploaded_at)
    month = extract("month", Invoice.uploaded_at)
    day = extract("day", Invoice.uploaded_at)
    rows = db.execute(
        select(year.label("y"), month.label("m"), day.label("d"), func.count(Invoice.id))
        .where(Invoice.uploaded_at >= since)
        .group_by("y", "m", "d")
        .order_by("y", "m", "d")
    ).all()
    return [{"date": f"{int(y):04d}-{int(m):02d}-{int(d):02d}", "count": c} for y, m, d, c in rows]


def _distribution(db: Session) -> list[dict]:
    rows = db.execute(
        select(Invoice.decision_status, func.count(Invoice.id))
        .where(Invoice.decision_status.is_not(None))
        .group_by(Invoice.decision_status)
    ).all()
    out = [{"status": status, "count": count} for status, count in rows]
    failed = _count(db, Invoice.processing_status == ProcessingStatus.FAILED.value)
    processing = _count(db, Invoice.processing_status == ProcessingStatus.PROCESSING.value)
    if failed:
        out.append({"status": "PROCESSING_FAILED", "count": failed})
    if processing:
        out.append({"status": "PROCESSING", "count": processing})
    return out


def _recent_failed(db: Session, limit: int = 5) -> list[dict]:
    rows = db.execute(
        select(ProcessingRun, Invoice)
        .join(Invoice, Invoice.id == ProcessingRun.invoice_id)
        .where(ProcessingRun.status == RunStatus.FAILED.value)
        .order_by(ProcessingRun.started_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "run_id": run.id, "invoice_id": inv.id,
            "invoice_number": inv.invoice_number or inv.original_file_name,
            "stage": run.current_stage, "message": run.error_message, "started_at": run.started_at,
        }  # fmt: skip
        for run, inv in rows
    ]


def recent_activity(db: Session, limit: int = 15) -> list[dict]:
    interesting = ("INVOICE_UPLOADED", "DECISION", "REVIEW_APPROVE", "REVIEW_REJECT",
                   "REVIEW_REQUEST_CLARIFICATION", "RUN_FAILED", "RUN_RETRY")  # fmt: skip
    rows = db.execute(
        select(AuditLog, Invoice)
        .join(Invoice, Invoice.id == AuditLog.invoice_id)
        .where(AuditLog.action.in_(interesting))
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": log.id, "invoice_id": inv.id,
            "invoice_number": inv.invoice_number or inv.original_file_name,
            "action": log.action, "actor": log.actor_id or log.actor_type,
            "description": log.description, "new_value": log.new_value, "created_at": log.created_at,
        }  # fmt: skip
        for log, inv in rows
    ]

