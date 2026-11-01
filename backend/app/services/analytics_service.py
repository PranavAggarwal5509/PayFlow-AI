"""Operational analytics and telemetry aggregates."""

from datetime import datetime, timedelta
from decimal import Decimal
import numpy as np

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.database.base import utcnow
from app.models.enums import DecisionStatus, ProcessingStatus, RunStatus, Stage
from app.models.invoice import Invoice
from app.models.processing import AuditLog, ProcessingRun, StageEvent


def get_operational_metrics(db: Session, days: int = 30) -> dict:
    """Calculate comprehensive AP operational and AI metrics over the given time window."""
    now = utcnow()
    since = now - timedelta(days=days)

    # 1. Volume & Runs
    total_invoices = db.scalar(select(func.count(Invoice.id)).where(Invoice.uploaded_at >= since)) or 0
    total_runs = db.scalar(select(func.count(ProcessingRun.id)).where(ProcessingRun.started_at >= since)) or 0
    completed_runs = db.scalar(
        select(func.count(ProcessingRun.id)).where(
            ProcessingRun.started_at >= since, ProcessingRun.status == RunStatus.COMPLETED.value
        )
    ) or 0
    failed_runs = db.scalar(
        select(func.count(ProcessingRun.id)).where(
            ProcessingRun.started_at >= since, ProcessingRun.status == RunStatus.FAILED.value
        )
    ) or 0

    # Business decisions
    approved_count = db.scalar(
        select(func.count(Invoice.id)).where(
            Invoice.uploaded_at >= since, Invoice.decision_status == DecisionStatus.APPROVED.value
        )
    ) or 0
    needs_review_count = db.scalar(
        select(func.count(Invoice.id)).where(
            Invoice.uploaded_at >= since, Invoice.decision_status == DecisionStatus.NEEDS_REVIEW.value
        )
    ) or 0
    rejected_count = db.scalar(
        select(func.count(Invoice.id)).where(
            Invoice.uploaded_at >= since, Invoice.decision_status == DecisionStatus.REJECTED.value
        )
    ) or 0

    # 2. Speed (Durations & Latencies)
    run_rows = db.execute(
        select(ProcessingRun.started_at, ProcessingRun.completed_at)
        .where(ProcessingRun.started_at >= since, ProcessingRun.status == RunStatus.COMPLETED.value)
    ).all()

    durations = [
        (c.replace(tzinfo=None) - s.replace(tzinfo=None)).total_seconds()
        for s, c in run_rows
        if c and s
    ]

    avg_e2e = round(float(np.mean(durations)), 2) if durations else None
    p50_e2e = round(float(np.percentile(durations, 50)), 2) if durations else None
    p95_e2e = round(float(np.percentile(durations, 95)), 2) if durations else None

    # Stage durations breakdown
    stage_events = db.execute(
        select(StageEvent.stage, StageEvent.started_at, StageEvent.completed_at)
        .where(StageEvent.started_at >= since, StageEvent.completed_at.is_not(None))
    ).all()

    stage_durations: dict[str, list[float]] = {}
    for st, s, c in stage_events:
        if s and c:
            d = (c.replace(tzinfo=None) - s.replace(tzinfo=None)).total_seconds()
            stage_durations.setdefault(st, []).append(d)

    stage_breakdown = [
        {
            "stage": st,
            "avg_seconds": round(float(np.mean(d_list)), 2),
            "p95_seconds": round(float(np.percentile(d_list, 95)), 2),
            "count": len(d_list),
        }
        for st, d_list in stage_durations.items()
    ]
    stage_breakdown.sort(key=lambda x: x["avg_seconds"], reverse=True)

    # 3. Reliability & Extraction Methods
    ocr_invoices = db.scalar(
        select(func.count(Invoice.id)).where(Invoice.uploaded_at >= since, Invoice.extraction_method == "OCR")
    ) or 0
    digital_invoices = db.scalar(
        select(func.count(Invoice.id)).where(Invoice.uploaded_at >= since, Invoice.extraction_method == "TEXT")
    ) or 0

    retry_count = db.scalar(
        select(func.count(AuditLog.id)).where(AuditLog.created_at >= since, AuditLog.action == "RUN_RETRY")
    ) or 0
    recovery_count = db.scalar(
        select(func.count(AuditLog.id)).where(AuditLog.created_at >= since, AuditLog.actor_id == "startup_recovery")
    ) or 0

    tech_success_rate = round((completed_runs / total_runs * 100), 1) if total_runs else 100.0
    tech_failure_rate = round((failed_runs / total_runs * 100), 1) if total_runs else 0.0
    manual_review_rate = round((needs_review_count / total_invoices * 100), 1) if total_invoices else 0.0

    # 4. AI Telemetry & Tokens
    ai_runs = db.execute(
        select(
            ProcessingRun.llm_model,
            func.coalesce(func.sum(ProcessingRun.prompt_tokens), 0),
            func.coalesce(func.sum(ProcessingRun.completion_tokens), 0),
            func.coalesce(func.sum(ProcessingRun.total_tokens), 0),
            func.count(ProcessingRun.id),
            func.avg(ProcessingRun.extraction_duration_ms),
        )
        .where(ProcessingRun.started_at >= since, ProcessingRun.llm_model.is_not(None))
        .group_by(ProcessingRun.llm_model)
    ).all()

    model_telemetry = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens_all = 0
    gemini_requests = 0

    for model, p_tok, c_tok, tot_tok, reqs, avg_ms in ai_runs:
        total_prompt_tokens += int(p_tok)
        total_completion_tokens += int(c_tok)
        total_tokens_all += int(tot_tok)
        gemini_requests += int(reqs)
        model_telemetry.append({
            "model": model,
            "requests": int(reqs),
            "prompt_tokens": int(p_tok),
            "completion_tokens": int(c_tok),
            "total_tokens": int(tot_tok),
            "avg_latency_ms": round(float(avg_ms), 1) if avg_ms else None,
        })

    # AI extraction average from stage events specifically
    ai_event_durations = stage_durations.get(Stage.AI_EXTRACTION.value, [])
    avg_ai_duration = round(float(np.mean(ai_event_durations)), 2) if ai_event_durations else None

    doc_event_durations = stage_durations.get(Stage.DOCUMENT_EXTRACTION.value, [])
    avg_doc_duration = round(float(np.mean(doc_event_durations)), 2) if doc_event_durations else None

    return {
        "period_days": days,
        "volume": {
            "total_invoices": total_invoices,
            "total_runs": total_runs,
            "completed_runs": completed_runs,
            "failed_runs": failed_runs,
            "approved": approved_count,
            "needs_review": needs_review_count,
            "rejected": rejected_count,
        },
        "speed": {
            "avg_end_to_end_seconds": avg_e2e,
            "p50_end_to_end_seconds": p50_e2e,
            "p95_end_to_end_seconds": p95_e2e,
            "avg_ai_extraction_seconds": avg_ai_duration,
            "avg_document_extraction_seconds": avg_doc_duration,
            "stage_breakdown": stage_breakdown,
        },
        "reliability": {
            "technical_success_rate": tech_success_rate,
            "technical_failure_rate": tech_failure_rate,
            "manual_review_rate": manual_review_rate,
            "retry_count": retry_count,
            "recovery_count": recovery_count,
            "ocr_count": ocr_invoices,
            "digital_count": digital_invoices,
        },
        "ai_usage": {
            "gemini_request_count": gemini_requests,
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_tokens_all,
            "models": model_telemetry,
            "cost_status": "Cost not configured",
            "cost_details": None,
        },
    }

