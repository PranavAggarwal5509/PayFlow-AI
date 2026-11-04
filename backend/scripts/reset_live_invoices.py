"""Reusable utility to safely reset and delete all LIVE_UPLOAD invoices in PayFlow AI.

Features:
- Default dry-run preview: shows exact counts of all entities that would be deleted.
- Requires explicit confirmation flag: --execute --confirm DELETE_ALL_LIVE_UPLOADS
- Pre-deletion verification: creates a timestamped SQL backup and archives target PDFs.
- Atomic deletion within a database transaction respecting all foreign key constraints.
- Removes orphaned uploaded PDF files from the upload directory only.
- Strict isolation: NEVER touches SEED_HISTORY records, vendors, purchase orders, or config.
- Idempotent: safe to run multiple times.
"""

import argparse
import datetime
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))
# Also check if /app/backend exists (inside container when script copied to /app/scripts)
if Path("/app/backend").exists() and "/app/backend" not in sys.path:
    sys.path.insert(0, "/app/backend")

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_session_factory
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


EXPECTED_CONFIRM_STRING = "DELETE_ALL_LIVE_UPLOADS"


def get_live_invoice_inventory(db: Session) -> Dict:
    """Collect all live invoices and count their dependent relational records."""
    live_invoices = db.execute(
        select(Invoice).where(Invoice.source_origin == "LIVE_UPLOAD")
    ).scalars().all()

    live_ids = [inv.id for inv in live_invoices]
    if not live_ids:
        return {
            "invoice_ids": [],
            "live_invoices": 0,
            "line_items": 0,
            "processing_runs": 0,
            "stage_events": 0,
            "decisions": 0,
            "reviews": 0,
            "audit_logs": 0,
            "validation_results": 0,
            "po_allocations": 0,
            "po_line_allocations": 0,
            "line_reconciliations": 0,
            "notification_drafts": 0,
            "visual_evidence": 0,
            "stored_pdf_paths": [],
        }

    # Processing runs
    run_ids = db.execute(
        select(ProcessingRun.id).where(ProcessingRun.invoice_id.in_(live_ids))
    ).scalars().all()

    # Stage events
    stage_events_count = (
        db.scalar(
            select(func.count(StageEvent.id)).where(
                StageEvent.run_id.in_(run_ids)
            )
        )
        if run_ids
        else 0
    ) or 0

    # Line items
    line_item_ids = db.execute(
        select(InvoiceLineItem.id).where(InvoiceLineItem.invoice_id.in_(live_ids))
    ).scalars().all()

    # Decisions
    decisions_count = (
        db.scalar(select(func.count(Decision.id)).where(Decision.invoice_id.in_(live_ids)))
        or 0
    )

    # Reviews
    reviews_count = (
        db.scalar(select(func.count(Review.id)).where(Review.invoice_id.in_(live_ids)))
        or 0
    )

    # Audit logs (either directly on invoice_id or on run_id)
    audit_filter = AuditLog.invoice_id.in_(live_ids)
    if run_ids:
        audit_filter = audit_filter | AuditLog.processing_run_id.in_(run_ids)
    audit_logs_count = db.scalar(select(func.count(AuditLog.id)).where(audit_filter)) or 0

    # Validation results
    validation_results_count = (
        db.scalar(
            select(func.count(ValidationResult.id)).where(
                ValidationResult.invoice_id.in_(live_ids)
            )
        )
        or 0
    )

    # PO allocations
    po_allocations_count = (
        db.scalar(
            select(func.count(POAllocation.id)).where(POAllocation.invoice_id.in_(live_ids))
        )
        or 0
    )

    # PO line allocations
    po_line_allocations_count = (
        db.scalar(
            select(func.count(POLineAllocation.id)).where(
                POLineAllocation.invoice_id.in_(live_ids)
            )
        )
        or 0
    )

    # Line item reconciliations
    line_reconciliations_count = (
        db.scalar(
            select(func.count(LineItemReconciliation.id)).where(
                LineItemReconciliation.invoice_id.in_(live_ids)
            )
        )
        or 0
    )

    # Notification drafts
    notification_drafts_count = (
        db.scalar(
            select(func.count(NotificationDraft.id)).where(
                NotificationDraft.invoice_id.in_(live_ids)
            )
        )
        or 0
    )

    # Visual evidence count
    visual_evidence_count = sum(
        1 for inv in live_invoices if inv.visual_evidence is not None
    )

    # Unique stored file paths of live invoices
    stored_pdf_paths = [
        inv.stored_file_path for inv in live_invoices if inv.stored_file_path
    ]

    return {
        "invoice_ids": live_ids,
        "run_ids": run_ids,
        "line_item_ids": line_item_ids,
        "live_invoices": len(live_invoices),
        "line_items": len(line_item_ids),
        "processing_runs": len(run_ids),
        "stage_events": stage_events_count,
        "decisions": decisions_count,
        "reviews": reviews_count,
        "audit_logs": audit_logs_count,
        "validation_results": validation_results_count,
        "po_allocations": po_allocations_count,
        "po_line_allocations": po_line_allocations_count,
        "line_reconciliations": line_reconciliations_count,
        "notification_drafts": notification_drafts_count,
        "visual_evidence": visual_evidence_count,
        "stored_pdf_paths": stored_pdf_paths,
    }


def find_safe_pdfs_to_remove(
    db: Session, target_paths: List[str], upload_dir: Path
) -> List[Path]:
    """Identify which PDFs belong strictly to live invoices and are unreferenced by remaining records."""
    if not target_paths:
        return []

    # Check if any remaining invoice (e.g. SEED_HISTORY) references any of these paths
    remaining_references = db.execute(
        select(Invoice.stored_file_path).where(
            Invoice.source_origin != "LIVE_UPLOAD",
            Invoice.stored_file_path.in_(target_paths),
        )
    ).scalars().all()
    protected_paths = set(remaining_references)

    safe_files = []
    for rel_path in set(target_paths):
        if rel_path in protected_paths:
            continue
        full_path = (upload_dir / rel_path).resolve()
        # Ensure file is inside upload_dir
        if full_path.is_file() and str(full_path).startswith(str(upload_dir.resolve())):
            safe_files.append(full_path)

    return safe_files


def create_pre_deletion_backup(
    upload_dir: Path, pdf_files_to_backup: List[Path]
) -> Path:
    """Create timestamped SQL backup and backup of targeted PDF files."""
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_base = upload_dir.parent / "backups" / f"reset_live_{timestamp}"
    backup_base.mkdir(parents=True, exist_ok=True)
    pdf_backup_dir = backup_base / "target_pdfs"
    pdf_backup_dir.mkdir(parents=True, exist_ok=True)

    # 1. Back up PDF files
    for pdf in pdf_files_to_backup:
        if pdf.exists():
            shutil.copy2(pdf, pdf_backup_dir / pdf.name)

    # 2. Database backup via docker exec if on host, or pre-staged file in upload volume, or local pg_dump
    sql_backup_file = backup_base / "payflow_pre_reset.sql"
    dump_success = False

    # Check if a pre-generated backup was staged in upload_dir (e.g. from host helper or previous step)
    staged_backup = upload_dir / "_db_pre_reset_backup.sql"
    if staged_backup.exists() and staged_backup.stat().st_size > 1000:
        shutil.move(str(staged_backup), str(sql_backup_file))
        dump_success = True

    # Try docker exec first (standard project deployment when run from host)
    if not dump_success:
        try:
            proc = subprocess.run(
                ["docker", "exec", "payflow-ai-postgres-1", "pg_dump", "-U", "payflow", "-d", "payflow"],
                capture_output=True,
                check=True,
            )
            if proc.stdout and len(proc.stdout) > 1000:
                sql_backup_file.write_bytes(proc.stdout)
                dump_success = True
        except Exception:
            pass

    # If docker not available, try pg_dump directly (if installed locally or inside container)
    if not dump_success:
        try:
            settings = get_settings()
            env = os.environ.copy()
            if settings.postgres_password:
                env["PGPASSWORD"] = settings.postgres_password
            proc = subprocess.run(
                ["pg_dump", "-U", settings.postgres_user, "-h", settings.postgres_host, "-p", str(settings.postgres_port), "-d", settings.postgres_db],
                capture_output=True,
                env=env,
            )
            if proc.returncode == 0 and proc.stdout and len(proc.stdout) > 1000:
                sql_backup_file.write_bytes(proc.stdout)
                dump_success = True
        except Exception:
            pass

    # Verify backup
    if not dump_success or not sql_backup_file.exists() or sql_backup_file.stat().st_size < 1000:
        raise RuntimeError(
            f"Pre-deletion database backup failed or produced empty file: {sql_backup_file}"
        )

    return backup_base


def execute_deletion(db: Session, inventory: Dict, safe_pdf_files: List[Path]) -> None:
    """Execute deletion of all LIVE_UPLOAD dependent records in strict FK order."""
    live_ids = inventory["invoice_ids"]
    run_ids = inventory["run_ids"]
    line_item_ids = inventory["line_item_ids"]

    if not live_ids:
        return

    # 1. po_line_allocations
    if live_ids:
        db.query(POLineAllocation).filter(POLineAllocation.invoice_id.in_(live_ids)).delete(synchronize_session=False)

    # 2. line_item_reconciliations
    if live_ids:
        db.query(LineItemReconciliation).filter(LineItemReconciliation.invoice_id.in_(live_ids)).delete(synchronize_session=False)

    # 3. po_allocations
    if live_ids:
        db.query(POAllocation).filter(POAllocation.invoice_id.in_(live_ids)).delete(synchronize_session=False)

    # 4. decisions
    if live_ids:
        db.query(Decision).filter(Decision.invoice_id.in_(live_ids)).delete(synchronize_session=False)

    # 5. validation_results
    if live_ids:
        db.query(ValidationResult).filter(ValidationResult.invoice_id.in_(live_ids)).delete(synchronize_session=False)

    # 6. reviews
    if live_ids:
        db.query(Review).filter(Review.invoice_id.in_(live_ids)).delete(synchronize_session=False)

    # 7. notification_drafts
    if live_ids:
        db.query(NotificationDraft).filter(NotificationDraft.invoice_id.in_(live_ids)).delete(synchronize_session=False)

    # 8. audit_logs (invoice_id or processing_run_id)
    if live_ids or run_ids:
        audit_query = db.query(AuditLog)
        if run_ids:
            audit_query = audit_query.filter(
                (AuditLog.invoice_id.in_(live_ids)) | (AuditLog.processing_run_id.in_(run_ids))
            )
        else:
            audit_query = audit_query.filter(AuditLog.invoice_id.in_(live_ids))
        audit_query.delete(synchronize_session=False)

    # 9. stage_events
    if run_ids:
        db.query(StageEvent).filter(StageEvent.run_id.in_(run_ids)).delete(synchronize_session=False)

    # 10. processing_runs
    if live_ids:
        db.query(ProcessingRun).filter(ProcessingRun.invoice_id.in_(live_ids)).delete(synchronize_session=False)

    # 11. invoice_line_items
    if live_ids:
        db.query(InvoiceLineItem).filter(InvoiceLineItem.invoice_id.in_(live_ids)).delete(synchronize_session=False)

    # 12. invoices
    db.query(Invoice).filter(Invoice.id.in_(live_ids)).delete(synchronize_session=False)

    db.commit()

    # 13. File cleanup: Remove only safe, unreferenced PDFs from upload directory
    removed_count = 0
    for pdf_path in safe_pdf_files:
        try:
            if pdf_path.exists():
                pdf_path.unlink()
                removed_count += 1
        except Exception as e:
            print(f"Warning: Could not remove PDF file {pdf_path}: {e}")

    inventory["removed_pdf_files"] = removed_count


def print_report(inventory: Dict, mode: str, backup_dir: Path = None):
    """Print structured summary report."""
    border = "=" * 65
    print("\n" + border)
    if mode == "DRY_RUN":
        print(" PAYFLOW AI — RESET LIVE INVOICES (DRY RUN PREVIEW)")
        print(" No changes were made. Use --execute --confirm to apply.")
    else:
        print(" PAYFLOW AI — RESET LIVE INVOICES (COMPLETED)")
        if backup_dir:
            print(f" Backup archived at: {backup_dir}")
    print(border)
    print(f" Live Invoices to delete:          {inventory['live_invoices']:>5}")
    print(f" Related Line Items:               {inventory['line_items']:>5}")
    print(f" Processing Runs:                  {inventory['processing_runs']:>5}")
    print(f" Stage Events:                     {inventory['stage_events']:>5}")
    print(f" Financial Decisions:              {inventory['decisions']:>5}")
    print(f" Review Records:                   {inventory['reviews']:>5}")
    print(f" Audit Logs:                       {inventory['audit_logs']:>5}")
    print(f" Validation Results:               {inventory['validation_results']:>5}")
    print(f" PO Allocations:                   {inventory['po_allocations']:>5}")
    print(f" PO Line Allocations:              {inventory['po_line_allocations']:>5}")
    print(f" Line Item Reconciliations:        {inventory['line_reconciliations']:>5}")
    print(f" Visual Evidence Records:          {inventory['visual_evidence']:>5}")
    pdf_stat = inventory.get("removed_pdf_files", len(inventory["stored_pdf_paths"]))
    print(f" Original PDF Files to remove:     {pdf_stat:>5}")
    print(border + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Reset and permanently remove all LIVE_UPLOAD invoices from PayFlow AI."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the deletion. Defaults to false (dry-run).",
    )
    parser.add_argument(
        "--confirm",
        type=str,
        default="",
        help=f"Must equal '{EXPECTED_CONFIRM_STRING}' to execute.",
    )
    args = parser.parse_args()

    settings = get_settings()
    session_factory = get_session_factory()
    upload_dir = Path(settings.upload_dir)

    with session_factory() as db:
        inventory = get_live_invoice_inventory(db)

        if inventory["live_invoices"] == 0:
            print("No live invoices found. Database is already clean.")
            return 0

        safe_pdf_files = find_safe_pdfs_to_remove(
            db, inventory["stored_pdf_paths"], upload_dir
        )

        # Dry-run mode
        if not args.execute:
            print_report(inventory, mode="DRY_RUN")
            print("To delete all live invoices, run:")
            print(
                f"  python scripts/reset_live_invoices.py --execute --confirm {EXPECTED_CONFIRM_STRING}\n"
            )
            return 0

        # Confirmation check
        if args.confirm != EXPECTED_CONFIRM_STRING:
            print(f"ERROR: Invalid confirmation token '{args.confirm}'.")
            print(f"Required: --confirm {EXPECTED_CONFIRM_STRING}")
            return 1

        # Pre-deletion backup
        print("Creating pre-deletion backup...")
        backup_dir = create_pre_deletion_backup(upload_dir, safe_pdf_files)
        print(f"Backup verified and saved to: {backup_dir}")

        # Safe transactional deletion
        print("Executing transactional deletion...")
        execute_deletion(db, inventory, safe_pdf_files)
        print_report(inventory, mode="EXECUTE", backup_dir=backup_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
