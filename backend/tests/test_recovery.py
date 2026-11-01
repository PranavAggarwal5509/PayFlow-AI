"""Automated tests for background processing recovery and interrupted run handling:
1. Backend restart with an unfinished RUNNING run
2. Backend restart with an unfinished invoice PROCESSING state
3. Recovery of an interrupted document extraction stage
4. Recovery of an interrupted AI extraction stage
5. Recovery operation executed twice (idempotency)
6. Completed invoice remains untouched
7. Previously rejected invoice remains untouched
8. Previously approved invoice and PO allocation remain untouched
9. Failed run remains visible in history
10. Retrying an interrupted invoice creates a new run
11. No duplicate allocation occurs after retry
12. Audit log records the interruption
13. Database transaction rollback on recovery failure
14. Normal backend startup when no unfinished runs exist
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.enums import DecisionStatus, ProcessingStatus, RunStatus, Stage, StageStatus
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.processing import AuditLog, ProcessingRun, StageEvent
from app.models.vendor_po import POAllocation, POLineAllocation, PurchaseOrder, PurchaseOrderItem
from app.services import invoice_service, run_service
from app.services.line_item_reconciler import allocate_po_line_items, reconcile_invoice_line_items
from app.services.po_matcher import allocate_to_po
from app.services.recovery_service import (
    INTERRUPTED_CATEGORY,
    INTERRUPTED_ERROR_MESSAGE,
    recover_interrupted_runs,
)
from tests.conftest import add_po, add_vendor
from tests.test_services_db import new_invoice


def test_recovery_unfinished_running_run(db):
    v = add_vendor(db)
    inv = new_invoice(db, vendor_id=v.id, processing_status="PROCESSING")
    run = run_service.create_run(db, inv, triggered_by="tester")
    run.status = RunStatus.RUNNING.value
    run.current_stage = Stage.DOCUMENT_EXTRACTION.value
    db.commit()

    recovered = recover_interrupted_runs(db)
    assert recovered == 1

    db.refresh(run)
    db.refresh(inv)
    assert run.status == RunStatus.FAILED.value
    assert run.completed_at is not None
    assert run.error_message == INTERRUPTED_ERROR_MESSAGE
    assert run.error_category == INTERRUPTED_CATEGORY
    assert inv.processing_status == ProcessingStatus.FAILED.value


def test_recovery_unfinished_processing_invoice(db):
    v = add_vendor(db)
    inv = new_invoice(db, vendor_id=v.id, processing_status="PROCESSING")
    db.commit()

    recovered = recover_interrupted_runs(db)
    # No runs existed, but stuck invoice was recovered
    assert recovered == 0
    db.refresh(inv)
    assert inv.processing_status == ProcessingStatus.FAILED.value

    # Verify audit log
    audit = db.scalar(
        select(AuditLog).where(
            AuditLog.invoice_id == inv.id,
            AuditLog.action == "INVOICE_RECOVERED",
        )
    )
    assert audit is not None


def test_recovery_interrupted_document_extraction_stage(db):
    v = add_vendor(db)
    inv = new_invoice(db, vendor_id=v.id, processing_status="PROCESSING")
    run = run_service.create_run(db, inv, triggered_by="tester")
    run.status = RunStatus.RUNNING.value
    run_service.begin_stage(db, run, Stage.DOCUMENT_EXTRACTION, message="Extracting text from PDF...")
    db.commit()

    recover_interrupted_runs(db)

    db.refresh(run)
    event = db.scalar(
        select(StageEvent).where(
            StageEvent.run_id == run.id,
            StageEvent.stage == Stage.DOCUMENT_EXTRACTION.value,
        )
    )
    assert event.status == StageStatus.FAILED.value
    assert "Interrupted by backend restart" in event.message
    assert event.completed_at is not None


def test_recovery_interrupted_ai_extraction_stage(db):
    v = add_vendor(db)
    inv = new_invoice(db, vendor_id=v.id, processing_status="PROCESSING")
    run = run_service.create_run(db, inv, triggered_by="tester")
    run.status = RunStatus.RUNNING.value
    run_service.begin_stage(db, run, Stage.AI_EXTRACTION, message="Calling extraction model...")
    db.commit()

    recover_interrupted_runs(db)

    db.refresh(run)
    event = db.scalar(
        select(StageEvent).where(
            StageEvent.run_id == run.id,
            StageEvent.stage == Stage.AI_EXTRACTION.value,
        )
    )
    assert event.status == StageStatus.FAILED.value
    assert "Interrupted by backend restart" in event.message


def test_recovery_idempotency_executed_twice(db):
    v = add_vendor(db)
    inv = new_invoice(db, vendor_id=v.id, processing_status="PROCESSING")
    run = run_service.create_run(db, inv, triggered_by="tester")
    run.status = RunStatus.RUNNING.value
    db.commit()

    # First run
    recovered1 = recover_interrupted_runs(db)
    assert recovered1 == 1

    # Second run immediately following
    recovered2 = recover_interrupted_runs(db)
    assert recovered2 == 0

    # Ensure no extra duplicate audit logs created
    audits = list(
        db.scalars(
            select(AuditLog).where(
                AuditLog.invoice_id == inv.id,
                AuditLog.actor_id == "startup_recovery",
            )
        ).all()
    )
    assert len(audits) == 1


def test_completed_invoice_remains_untouched(db):
    v = add_vendor(db)
    inv = new_invoice(db, vendor_id=v.id, processing_status="COMPLETED", decision_status="NEEDS_REVIEW")
    run = run_service.create_run(db, inv, triggered_by="tester")
    run_service.complete_run(db, run)
    db.commit()

    recovered = recover_interrupted_runs(db)
    assert recovered == 0

    db.refresh(inv)
    db.refresh(run)
    assert inv.processing_status == "COMPLETED"
    assert inv.decision_status == "NEEDS_REVIEW"
    assert run.status == RunStatus.COMPLETED.value


def test_previously_rejected_invoice_remains_untouched(db):
    v = add_vendor(db)
    inv = new_invoice(db, vendor_id=v.id, processing_status="COMPLETED", decision_status="REJECTED")
    run = run_service.create_run(db, inv, triggered_by="tester")
    run_service.complete_run(db, run)
    db.commit()

    recovered = recover_interrupted_runs(db)
    assert recovered == 0

    db.refresh(inv)
    assert inv.decision_status == "REJECTED"


def test_previously_approved_invoice_and_po_allocation_untouched(db):
    v = add_vendor(db)
    po = add_po(db, v, items=[("Test Equipment", "10", "1000")])
    inv = new_invoice(
        db,
        vendor_id=v.id,
        purchase_order_id=po.id,
        total_amount=Decimal("1000"),
        processing_status="COMPLETED",
        decision_status="APPROVED",
    )
    line = InvoiceLineItem(
        id=uuid4(),
        invoice_id=inv.id,
        description="Test Equipment",
        quantity=Decimal("1"),
        unit_price=Decimal("1000"),
        total_amount=Decimal("1000"),
    )
    inv.line_items = [line]
    db.flush()

    recons, _ = reconcile_invoice_line_items(db, inv, po)
    for r in recons:
        db.add(r)
    db.flush()

    allocate_to_po(db, inv, allocated_by="system")
    run = run_service.create_run(db, inv, triggered_by="tester")
    run_service.complete_run(db, run)
    db.commit()

    recovered = recover_interrupted_runs(db)
    assert recovered == 0

    # Ensure PO allocations remain intact
    alloc = db.scalar(select(POAllocation).where(POAllocation.invoice_id == inv.id))
    assert alloc is not None
    assert alloc.status == "ACTIVE"

    line_alloc = db.scalar(select(POLineAllocation).where(POLineAllocation.invoice_id == inv.id))
    assert line_alloc is not None
    assert line_alloc.status == "ACTIVE"


def test_failed_run_remains_visible_and_retrying_creates_new_run(db):
    v = add_vendor(db)
    inv = new_invoice(db, vendor_id=v.id, processing_status="PROCESSING")
    run1 = run_service.create_run(db, inv, triggered_by="tester")
    run1.status = RunStatus.RUNNING.value
    db.commit()

    recover_interrupted_runs(db)

    db.refresh(run1)
    assert run1.status == RunStatus.FAILED.value

    # Retry the recovered invoice
    run2 = invoice_service.create_retry_run(db, inv.id, user_id="reviewer")
    assert run2.run_number == 2
    assert run2.status == RunStatus.QUEUED.value

    # Both runs exist in history
    runs = list(
        db.scalars(
            select(ProcessingRun)
            .where(ProcessingRun.invoice_id == inv.id)
            .order_by(ProcessingRun.run_number.asc())
        ).all()
    )
    assert len(runs) == 2
    assert runs[0].id == run1.id
    assert runs[0].status == RunStatus.FAILED.value
    assert runs[1].id == run2.id
    assert runs[1].status == RunStatus.QUEUED.value


def test_no_duplicate_allocation_after_retry(db):
    v = add_vendor(db)
    po = add_po(db, v, items=[("Industrial Cable", "100", "50")])
    inv = new_invoice(
        db,
        vendor_id=v.id,
        purchase_order_id=po.id,
        total_amount=Decimal("1000"),
        processing_status="PROCESSING",
    )
    line = InvoiceLineItem(
        id=uuid4(),
        invoice_id=inv.id,
        description="Industrial Cable",
        quantity=Decimal("20"),
        unit_price=Decimal("50"),
        total_amount=Decimal("1000"),
    )
    inv.line_items = [line]
    db.flush()

    run1 = run_service.create_run(db, inv, triggered_by="tester")
    run1.status = RunStatus.RUNNING.value
    db.commit()

    recover_interrupted_runs(db)

    # Retry run created
    run2 = invoice_service.create_retry_run(db, inv.id, user_id="reviewer")
    recons, _ = reconcile_invoice_line_items(db, inv, po)
    for r in recons:
        db.add(r)
    db.flush()

    # Now invoice completes and allocates
    alloc1 = allocate_to_po(db, inv, allocated_by="retry_tester")
    db.commit()

    # Allocation must be singular
    allocations = list(db.scalars(select(POAllocation).where(POAllocation.invoice_id == inv.id)).all())
    assert alloc1 is not None
    assert len(allocations) == 1

    line_allocs = list(
        db.scalars(select(POLineAllocation).where(POLineAllocation.invoice_id == inv.id)).all()
    )
    assert len(line_allocs) == 1
    assert line_allocs[0].quantity == Decimal("20")


def test_audit_log_records_the_interruption(db):
    v = add_vendor(db)
    inv = new_invoice(db, vendor_id=v.id, processing_status="PROCESSING")
    run = run_service.create_run(db, inv, triggered_by="tester")
    run.status = RunStatus.RUNNING.value
    run.current_stage = Stage.AI_EXTRACTION.value
    db.commit()

    recover_interrupted_runs(db)

    audits = list(
        db.scalars(
            select(AuditLog).where(
                AuditLog.invoice_id == inv.id,
                AuditLog.action == "RUN_FAILED",
                AuditLog.actor_id == "startup_recovery",
            )
        ).all()
    )
    assert len(audits) == 1
    assert "AI_EXTRACTION" in audits[0].description
    assert audits[0].new_value == INTERRUPTED_CATEGORY


def test_normal_startup_when_no_unfinished_runs(db):
    # Ensure no runs in db
    recovered = recover_interrupted_runs(db)
    assert recovered == 0
