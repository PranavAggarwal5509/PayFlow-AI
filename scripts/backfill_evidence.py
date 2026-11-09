"""Recompute click-to-highlight PDF evidence for invoices already in the database.

    python scripts/backfill_evidence.py              # every invoice that has extracted data
    python scripts/backfill_evidence.py --missing    # only invoices without evidence yet

Reads each stored PDF (Supabase bucket or local storage), finds where every extracted value is
printed and saves the bounding boxes in invoices.visual_evidence. Only that column is written;
decisions, checks and amounts are untouched. Safe to run repeatedly.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select  # noqa: E402

from app.api.dependencies.providers import get_storage  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.database.session import get_session_factory  # noqa: E402
from app.models import Invoice  # noqa: E402
from app.services.evidence_service import rebuild_evidence  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--missing", action="store_true", help="only invoices that have no evidence yet")
    args = parser.parse_args()

    settings = get_settings()
    storage = get_storage(settings)
    done = skipped = failed = 0
    with get_session_factory()() as db:
        stmt = select(Invoice).where(Invoice.extracted_data.is_not(None)).order_by(Invoice.uploaded_at)
        for invoice in db.scalars(stmt):
            if args.missing and invoice.visual_evidence:
                skipped += 1
                continue
            try:
                if rebuild_evidence(invoice, storage):
                    db.commit()
                    done += 1
                    found = sum(1 for v in (invoice.visual_evidence or {}).values()
                                if isinstance(v, dict) and v.get("evidence_status") != "NOT_FOUND")  # fmt: skip
                    print(f"  {invoice.invoice_number or invoice.original_file_name:<22} {found} fields located")
                else:
                    skipped += 1
            except Exception as exc:  # noqa: BLE001 - keep going; report at the end
                db.rollback()
                failed += 1
                print(f"  {invoice.original_file_name}: {exc}")
    print(f"Evidence rebuilt for {done} invoice(s); skipped {skipped}; failed {failed}.")


if __name__ == "__main__":
    main()
