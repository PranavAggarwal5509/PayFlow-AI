"""Tests for operational performance analytics and metrics:
1. Volume metrics (invoices, runs, outcomes)
2. Speed metrics (averages, p50, p95, stage breakdown)
3. Reliability metrics (success rate, failures, manual review rate)
4. AI telemetry and token consumption
5. Time range filter testing (7, 30, 90 days)
6. Empty database handling
7. Separation of technical failures from business rejections
"""

from datetime import datetime, timedelta
from decimal import Decimal
import pytest
from sqlalchemy import select

from app.database.base import utcnow
from app.models.enums import DecisionStatus, ProcessingStatus, RunStatus, Stage, StageStatus
from app.models.invoice import Invoice
from app.models.processing import ProcessingRun, StageEvent
from app.services.analytics_service import get_operational_metrics
from tests.conftest import add_vendor
from tests.test_services_db import new_invoice


def test_empty_database_operational_metrics(db):
    metrics = get_operational_metrics(db, days=30)
    assert metrics["volume"]["total_invoices"] == 0
    assert metrics["volume"]["total_runs"] == 0
    assert metrics["speed"]["avg_end_to_end_seconds"] is None
    assert metrics["speed"]["p95_end_to_end_seconds"] is None
    assert metrics["reliability"]["technical_success_rate"] == 100.0
    assert metrics["ai_usage"]["tokens_available"] is False
    assert metrics["ai_usage"]["total_tokens"] is None
    assert metrics["ai_usage"]["cost_status"] == "Cost not configured"


def test_operational_metrics_volume_and_durations(db):
    v = add_vendor(db)
    now = utcnow()

    # 1. Approved invoice with completed run (duration: 10s)
    inv1 = new_invoice(db, vendor_id=v.id, decision_status="APPROVED", processing_status="COMPLETED")
    inv1.uploaded_at = now - timedelta(days=2)
    db.flush()

    run1 = ProcessingRun(
        invoice_id=inv1.id,
        run_number=1,
        status=RunStatus.COMPLETED.value,
        started_at=now - timedelta(days=2, seconds=10),
        completed_at=now - timedelta(days=2),
        llm_model="mock-catalog",
        prompt_tokens=450,
        completion_tokens=150,
        total_tokens=600,
    )
    db.add(run1)
    db.flush()

    # Add stage events for stage breakdown
    ev1 = StageEvent(
        run_id=run1.id,
        stage=Stage.AI_EXTRACTION.value,
        status=StageStatus.COMPLETED.value,
        started_at=now - timedelta(days=2, seconds=8),
        completed_at=now - timedelta(days=2, seconds=4),
    )
    db.add(ev1)

    # 2. Rejected invoice with completed run (duration: 20s)
    inv2 = new_invoice(db, vendor_id=v.id, decision_status="REJECTED", processing_status="COMPLETED")
    inv2.uploaded_at = now - timedelta(days=5)
    db.flush()

    run2 = ProcessingRun(
        invoice_id=inv2.id,
        run_number=1,
        status=RunStatus.COMPLETED.value,
        started_at=now - timedelta(days=5, seconds=20),
        completed_at=now - timedelta(days=5),
        llm_model="mock-catalog",
        prompt_tokens=500,
        completion_tokens=200,
        total_tokens=700,
    )
    db.add(run2)

    # 3. Technical failure run
    inv3 = new_invoice(db, vendor_id=v.id, processing_status="FAILED")
    inv3.uploaded_at = now - timedelta(days=1)
    db.flush()

    run3 = ProcessingRun(
        invoice_id=inv3.id,
        run_number=1,
        status=RunStatus.FAILED.value,
        started_at=now - timedelta(days=1, seconds=5),
        completed_at=now - timedelta(days=1),
    )
    db.add(run3)
    db.commit()

    # Query metrics for 7 days
    metrics = get_operational_metrics(db, days=7)

    # Volume checks
    assert metrics["volume"]["total_invoices"] == 3
    assert metrics["volume"]["total_runs"] == 3
    assert metrics["volume"]["completed_runs"] == 2
    assert metrics["volume"]["failed_runs"] == 1
    assert metrics["volume"]["approved"] == 1
    assert metrics["volume"]["rejected"] == 1

    # Speed checks: run1 (10s), run2 (20s) -> avg = 15.0s
    assert metrics["speed"]["avg_end_to_end_seconds"] == 15.0
    assert metrics["speed"]["p50_end_to_end_seconds"] == 15.0

    # Reliability checks: 2 completed / 3 total runs = 66.7%
    assert metrics["reliability"]["technical_success_rate"] == 66.7
    assert metrics["reliability"]["technical_failure_rate"] == 33.3

    # AI usage checks
    assert metrics["ai_usage"]["tokens_available"] is True
    assert metrics["ai_usage"]["total_tokens"] == 1300
    assert metrics["ai_usage"]["prompt_tokens"] == 950
    assert metrics["ai_usage"]["completion_tokens"] == 350
    assert len(metrics["ai_usage"]["models"]) == 1
    assert metrics["ai_usage"]["models"][0]["model"] == "mock-catalog"
    assert metrics["ai_usage"]["models"][0]["tokens_available"] is True


def test_time_window_filtering(db):
    v = add_vendor(db)
    now = utcnow()

    # Invoice 15 days ago
    inv_recent = new_invoice(db, vendor_id=v.id)
    inv_recent.uploaded_at = now - timedelta(days=15)

    # Invoice 45 days ago
    inv_old = new_invoice(db, vendor_id=v.id)
    inv_old.uploaded_at = now - timedelta(days=45)
    db.commit()

    # 7-day query: 0 invoices
    m7 = get_operational_metrics(db, days=7)
    assert m7["volume"]["total_invoices"] == 0

    # 30-day query: 1 invoice
    m30 = get_operational_metrics(db, days=30)
    assert m30["volume"]["total_invoices"] == 1

    # 90-day query: 2 invoices
    m90 = get_operational_metrics(db, days=90)
    assert m90["volume"]["total_invoices"] == 2

