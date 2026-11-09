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


def _count_origin(db: Session, origin: str | None, *conditions) -> int:
    stmt = select(func.count(Invoice.id))
    if origin:
        stmt = stmt.where(Invoice.source_origin == origin)
    if conditions:
        stmt = stmt.where(*conditions)
    return db.scalar(stmt) or 0


ORIGINS = ("LIVE_UPLOAD", "SEED_HISTORY")


def normalize_origin(value: str | None) -> str | None:
    """'ALL' / empty -> None (every invoice); otherwise one of ORIGINS."""
    upper = (value or "").strip().upper()
    return upper if upper in ORIGINS else None


def _scope(origin: str | None) -> tuple:
    return (Invoice.source_origin == origin,) if origin else ()


def _delta(current: int, previous: int) -> float | None:
    if previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


def get_stats(db: Session, origin: str | None = None) -> dict:
    """Overview metrics for one dataset: None = all invoices, or LIVE_UPLOAD / SEED_HISTORY."""
    now = utcnow()
    cur_start = now - timedelta(days=PERIOD_DAYS)
    prev_start = now - timedelta(days=PERIOD_DAYS * 2)

    def period_counts(*conditions) -> tuple[int, int]:
        current = _count_origin(db, origin, Invoice.uploaded_at >= cur_start, *conditions)
        previous = _count_origin(
            db, origin, Invoice.uploaded_at >= prev_start, Invoice.uploaded_at < cur_start, *conditions
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
            "value": _count_origin(db, origin, *conditions),
            "change_percent": _delta(cur, prev),
            "last_30_days": cur,
        }

    decided = kpis["approved"]["value"] + kpis["rejected"]["value"] + kpis["needs_review"]["value"]
    approval_rate = round(kpis["approved"]["value"] / decided * 100, 1) if decided else None

    value_by_currency = {
        currency: Decimal(total)
        for currency, total in db.execute(
            select(Invoice.currency, func.coalesce(func.sum(Invoice.total_amount), 0))
            .where(*_scope(origin), Invoice.currency.is_not(None))
            .group_by(Invoice.currency)
        )
    }

    pending_reviews = (
        db.scalar(
            select(func.count(Review.id))
            .join(Invoice, Invoice.id == Review.invoice_id)
            .where(
                *_scope(origin),
                Review.review_status.in_(
                    [ReviewStatus.PENDING.value, ReviewStatus.CLARIFICATION_REQUESTED.value]
                ),
            )
        )
        or 0
    )

    # Compute detailed Portfolio Breakdown
    portfolio = {
        "all": {
            "total": _count_origin(db, None),
            "approved": _count_origin(db, None, Invoice.decision_status == approved),
            "needs_review": _count_origin(db, None, Invoice.decision_status == needs_review),
            "rejected": _count_origin(db, None, Invoice.decision_status == rejected),
            "failed": _count_origin(db, None, Invoice.processing_status == failed),
        },
        "live": {
            "total": _count_origin(db, "LIVE_UPLOAD"),
            "approved": _count_origin(db, "LIVE_UPLOAD", Invoice.decision_status == approved),
            "needs_review": _count_origin(db, "LIVE_UPLOAD", Invoice.decision_status == needs_review),
            "rejected": _count_origin(db, "LIVE_UPLOAD", Invoice.decision_status == rejected),
            "failed": _count_origin(db, "LIVE_UPLOAD", Invoice.processing_status == failed),
        },
        "historical": {
            "total": _count_origin(db, "SEED_HISTORY"),
            "approved": _count_origin(db, "SEED_HISTORY", Invoice.decision_status == approved),
            "needs_review": _count_origin(db, "SEED_HISTORY", Invoice.decision_status == needs_review),
            "rejected": _count_origin(db, "SEED_HISTORY", Invoice.decision_status == rejected),
            "failed": _count_origin(db, "SEED_HISTORY", Invoice.processing_status == failed),
        },
    }

    return {
        "source_origin": origin or "ALL",
        "kpis": kpis,
        "portfolio": portfolio,
        "approval_rate": approval_rate,
        "pending_reviews": pending_reviews,
        "total_value_by_currency": value_by_currency,
        "average_processing_seconds": _average_processing_seconds(db, origin),
        "monthly_volume": _monthly(db, origin),
        "daily_volume": _daily(db, now - timedelta(days=PERIOD_DAYS - 1), origin),
        "decision_distribution": _distribution(db, origin),
        "decision_distribution_detailed": _distribution_detailed(db),
        "recent_failed_runs": _recent_failed(db),
        "exceptions_by_control": _exceptions_by_control(db, origin),
        "value_at_risk": _value_at_risk(db, origin),
    }


def _average_processing_seconds(db: Session, origin: str | None = None) -> float | None:
    rows = db.execute(
        select(ProcessingRun.started_at, ProcessingRun.completed_at)
        .join(Invoice, Invoice.id == ProcessingRun.invoice_id)
        .where(ProcessingRun.status == RunStatus.COMPLETED.value, *_scope(origin))
        .order_by(ProcessingRun.completed_at.desc())
        .limit(200)
    ).all()
    durations = [(c.replace(tzinfo=None) - s.replace(tzinfo=None)).total_seconds() for s, c in rows if c]
    return round(sum(durations) / len(durations), 1) if durations else None


def _monthly(db: Session, origin: str | None = None) -> list[dict]:
    year, month = extract("year", Invoice.uploaded_at), extract("month", Invoice.uploaded_at)
    rows = db.execute(
        select(
            year.label("y"), month.label("m"), func.count(Invoice.id),
            func.coalesce(func.sum(Invoice.total_amount), 0),
        )  # fmt: skip
        .where(*_scope(origin))
        .group_by("y", "m")
        .order_by("y", "m")
    ).all()
    return [
        {"month": f"{int(y):04d}-{int(m):02d}", "count": count, "value": Decimal(value)}
        for y, m, count, value in rows[-12:]
    ]


def _daily(db: Session, since, origin: str | None = None) -> list[dict]:
    year = extract("year", Invoice.uploaded_at)
    month = extract("month", Invoice.uploaded_at)
    day = extract("day", Invoice.uploaded_at)
    rows = db.execute(
        select(year.label("y"), month.label("m"), day.label("d"), func.count(Invoice.id))
        .where(*_scope(origin), Invoice.uploaded_at >= since)
        .group_by("y", "m", "d")
        .order_by("y", "m", "d")
    ).all()
    return [{"date": f"{int(y):04d}-{int(m):02d}-{int(d):02d}", "count": c} for y, m, d, c in rows]


def _distribution(db: Session, origin: str | None = None) -> list[dict]:
    rows = db.execute(
        select(Invoice.decision_status, func.count(Invoice.id))
        .where(*_scope(origin), Invoice.decision_status.is_not(None))
        .group_by(Invoice.decision_status)
    ).all()
    out = [{"status": status, "count": count} for status, count in rows]
    # For invoices that failed technical processing before a decision was reached
    failed_undecided = db.scalar(
        select(func.count(Invoice.id)).where(
            *_scope(origin),
            Invoice.processing_status == ProcessingStatus.FAILED.value,
            Invoice.decision_status.is_(None),
        )
    ) or 0
    processing = _count_origin(db, origin, Invoice.processing_status == ProcessingStatus.PROCESSING.value)
    if failed_undecided:
        out.append({"status": "PROCESSING_FAILED", "count": failed_undecided})
    if processing:
        out.append({"status": "PROCESSING", "count": processing})
    return out


def _distribution_detailed(db: Session) -> dict:
    """Detailed breakdown for stacked/segmented distribution charts."""
    def get_counts(origin: str):
        rows = dict(
            db.execute(
                select(Invoice.decision_status, func.count(Invoice.id))
                .where(Invoice.source_origin == origin, Invoice.decision_status.is_not(None))
                .group_by(Invoice.decision_status)
            ).all()
        )
        failed_undecided = db.scalar(
            select(func.count(Invoice.id)).where(
                Invoice.source_origin == origin,
                Invoice.processing_status == ProcessingStatus.FAILED.value,
                Invoice.decision_status.is_(None),
            )
        ) or 0
        return {
            "approved": rows.get(DecisionStatus.APPROVED.value, 0),
            "needs_review": rows.get(DecisionStatus.NEEDS_REVIEW.value, 0),
            "rejected": rows.get(DecisionStatus.REJECTED.value, 0),
            "failed": failed_undecided,
            "total": sum(rows.values()) + failed_undecided,
        }

    live = get_counts("LIVE_UPLOAD")
    hist = get_counts("SEED_HISTORY")
    return {
        "live": live,
        "historical": hist,
        "combined": {
            "approved": live["approved"] + hist["approved"],
            "needs_review": live["needs_review"] + hist["needs_review"],
            "rejected": live["rejected"] + hist["rejected"],
            "failed": live["failed"] + hist["failed"],
            "total": live["total"] + hist["total"],
        },
    }


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


def recent_activity(db: Session, limit: int = 15, origin: str | None = None) -> list[dict]:
    interesting = ("INVOICE_UPLOADED", "DECISION", "REVIEW_APPROVE", "REVIEW_REJECT",
                   "REVIEW_REQUEST_CLARIFICATION", "RUN_FAILED", "RUN_RETRY")  # fmt: skip
    rows = db.execute(
        select(AuditLog, Invoice)
        .join(Invoice, Invoice.id == AuditLog.invoice_id)
        .where(AuditLog.action.in_(interesting), *_scope(origin))
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



def _exceptions_by_control(db: Session, origin: str | None = None) -> list[dict]:
    """How many invoices each control flagged (latest decision per invoice)."""
    from app.models.processing import Decision

    latest: dict = {}
    rows = db.execute(
        select(Decision.invoice_id, Decision.created_at, Decision.reasons)
        .join(Invoice, Invoice.id == Decision.invoice_id)
        .where(*_scope(origin))
    ).all()
    for invoice_id, created_at, reasons in rows:
        if invoice_id not in latest or created_at > latest[invoice_id][0]:
            latest[invoice_id] = (created_at, reasons or [])
    counts: dict[str, dict] = {}
    for _, reasons in latest.values():
        for code in {r["code"]: r for r in reasons if r.get("severity") in ("BLOCKING", "WARNING")}:
            entry = counts.setdefault(code, {"code": code, "count": 0})
            entry["count"] += 1
    return sorted(counts.values(), key=lambda e: (-e["count"], e["code"]))


def _value_at_risk(db: Session, origin: str | None = None) -> dict:
    """Invoice value approved, held for review or blocked by rejection, per currency."""
    out: dict[str, dict[str, Decimal]] = {"held": {}, "blocked": {}, "approved": {}}
    buckets = {
        DecisionStatus.NEEDS_REVIEW.value: "held",
        DecisionStatus.REJECTED.value: "blocked",
        DecisionStatus.APPROVED.value: "approved",
    }
    rows = db.execute(
        select(Invoice.decision_status, Invoice.currency, func.coalesce(func.sum(Invoice.total_amount), 0))
        .where(*_scope(origin), Invoice.currency.is_not(None))
        .where(Invoice.decision_status.in_(list(buckets)))
        .group_by(Invoice.decision_status, Invoice.currency)
    ).all()
    for status, currency, total in rows:
        out[buckets[status]][currency] = Decimal(total)
    return out
