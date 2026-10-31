"""Seed PostgreSQL with the synthetic demo data.

    python scripts/seed_database.py            # vendors, purchase orders, processed history
    python scripts/seed_database.py --reset    # wipe demo tables first (destructive!)

Vendors and POs come from sample_data/*.json. The history invoices are pushed through the *real*
deterministic pipeline (validation -> vendor -> PO -> duplicate -> decision), so allocations, reviews,
audit logs and dashboard numbers are produced by the same code that handles live uploads. Only the
document-reading and LLM stages are skipped (their output is taken from the JSON files).
"""

import argparse
import json
import random
import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.database.base import Base, utcnow  # noqa: E402
from app.database.session import get_engine, get_session_factory  # noqa: E402
from app.models import (  # noqa: E402
    AuditLog,
    Invoice,
    ProcessingRun,
    PurchaseOrder,
    PurchaseOrderItem,
    Review,
    Vendor,
)
from app.models.enums import Stage, StageStatus  # noqa: E402
from app.schemas.extraction import ExtractedInvoice, ExtractedLineItem  # noqa: E402
from app.services import pdf_extractor, pipeline, run_service  # noqa: E402
from app.services.invoice_service import create_invoice_from_upload  # noqa: E402
from app.storage import LocalStorage  # noqa: E402
from app.utils.normalize import normalize_vendor_name  # noqa: E402

DATA = ROOT / "sample_data"


def seed_vendors(db) -> dict[str, Vendor]:
    vendors: dict[str, Vendor] = {}
    for row in json.loads((DATA / "vendors" / "vendors.json").read_text(encoding="utf-8")):
        vendor = db.scalar(select(Vendor).where(Vendor.vendor_code == row["vendor_code"]))
        if vendor is None:
            vendor = Vendor(vendor_code=row["vendor_code"], is_demo=True)
            db.add(vendor)
        vendor.vendor_name = row["vendor_name"]
        vendor.normalized_name = normalize_vendor_name(row["vendor_name"])
        vendor.gstin, vendor.address = row["gstin"], row["address"]
        vendor.email, vendor.phone, vendor.status = row["email"], row["phone"], row["status"]
        vendors[row["vendor_code"]] = vendor
    db.commit()
    return vendors


def seed_purchase_orders(db, vendors: dict[str, Vendor]) -> None:
    from datetime import date

    for row in json.loads((DATA / "purchase_orders" / "purchase_orders.json").read_text(encoding="utf-8")):
        if db.scalar(select(PurchaseOrder).where(PurchaseOrder.po_number == row["po_number"])):
            continue
        po = PurchaseOrder(
            po_number=row["po_number"], vendor_id=vendors[row["vendor_code"]].id,
            po_date=date.fromisoformat(row["po_date"]), currency=row["currency"],
            total_amount=Decimal(row["total_amount"]), status=row["status"],
            description=row["description"], is_demo=True,
        )  # fmt: skip
        for item in row["items"]:
            qty, price = Decimal(str(item["quantity"])), Decimal(str(item["unit_price"]))
            po.items.append(
                PurchaseOrderItem(description=item["description"], quantity=qty, unit_price=price,
                                  total_amount=qty * price)  # fmt: skip
            )
        db.add(po)
    db.commit()


def seed_history(db, storage: LocalStorage) -> int:
    settings = get_settings()
    history = json.loads((DATA / "invoices" / "history" / "history.json").read_text(encoding="utf-8"))
    rng = random.Random(42)
    created = 0
    for row in sorted(history, key=lambda r: -r["days_ago"]):
        if db.scalar(select(Invoice).where(Invoice.original_file_name == row["file"])):
            continue
        pdf = (DATA / "invoices" / "history" / row["file"]).read_bytes()
        invoice, run = create_invoice_from_upload(
            db, settings, storage, filename=row["file"], content_type="application/pdf",
            data=pdf, uploaded_by="seed-script",
        )  # fmt: skip
        uploaded_at = utcnow() - timedelta(days=row["days_ago"], hours=rng.randint(0, 8))
        invoice.uploaded_at = uploaded_at
        document = pdf_extractor.extract_text(pdf)
        invoice.extracted_text, invoice.extraction_method = document.text, "TEXT"
        invoice.page_count = document.page_count
        extracted = ExtractedInvoice(
            vendor_name=row["vendor"], vendor_gstin=row["gstin"], invoice_number=row["invoice_number"],
            invoice_date=row["invoice_date"], due_date=row["due_date"], purchase_order_number=row["po_number"],
            currency=row["currency"], subtotal=row["subtotal"], tax_amount=row["tax"], total_amount=row["total"],
            line_items=[ExtractedLineItem(**i) for i in row["items"]],
        )  # fmt: skip
        pipeline.apply_extraction(db, invoice, extracted)
        db.commit()

        ctx = pipeline.PipelineContext(db, settings, storage, llm=None)  # type: ignore[arg-type]
        run_service.claim_run(db, run.id)
        live = pipeline.load_active_run(db, run.id)
        for stage in (Stage.DOCUMENT_EXTRACTION, Stage.AI_EXTRACTION):
            run_service.begin_stage(db, live, stage)
            run_service.finish_stage(db, live, stage, StageStatus.COMPLETED, "Loaded from sample data.")
        db.commit()
        pipeline.stage_validate(ctx, live, "data")
        pipeline.stage_vendor_check(ctx, live)
        pipeline.stage_po_match(ctx, live)
        pipeline.stage_duplicate_check(ctx, live)
        pipeline.stage_validate(ctx, live, "financial")
        pipeline.stage_decision(ctx, live)
        _backdate(db, invoice, run.id, uploaded_at, rng)
        created += 1
        print(f"  history {row['file']:<22} -> {invoice.decision_status}")
    return created


def _backdate(db, invoice: Invoice, run_id, uploaded_at, rng: random.Random) -> None:
    """Make the run / audit timestamps consistent with the historical upload date."""
    run = db.get(ProcessingRun, run_id)
    run.started_at = uploaded_at
    duration = rng.randint(18, 52)
    run.completed_at = uploaded_at + timedelta(seconds=duration)
    for index, event in enumerate(run.stage_events):
        event.started_at = uploaded_at + timedelta(seconds=index * duration // 9)
        event.completed_at = uploaded_at + timedelta(seconds=(index + 1) * duration // 9)
    for log in db.scalars(select(AuditLog).where(AuditLog.invoice_id == invoice.id)):
        log.created_at = uploaded_at + timedelta(seconds=duration)
    review = db.scalar(select(Review).where(Review.invoice_id == invoice.id))
    if review:
        review.created_at = review.updated_at = uploaded_at + timedelta(seconds=duration)
    db.commit()


def reset(db) -> None:
    print("Resetting all application tables ...")
    Base.metadata.drop_all(get_engine())
    Base.metadata.create_all(get_engine())
    db.expire_all()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="drop and recreate tables (destructive)")
    parser.add_argument("--no-history", action="store_true", help="only seed vendors and purchase orders")
    args = parser.parse_args()

    storage = LocalStorage(get_settings().upload_dir)
    with get_session_factory()() as db:
        if args.reset:
            reset(db)
        vendors = seed_vendors(db)
        seed_purchase_orders(db, vendors)
        print(f"Vendors: {len(vendors)}  POs: {db.query(PurchaseOrder).count()}")
        if not args.no_history:
            print(f"History invoices processed: {seed_history(db, storage)}")


if __name__ == "__main__":
    main()
