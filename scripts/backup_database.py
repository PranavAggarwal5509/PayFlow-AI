"""Dump every table of the configured database to JSON (one file per table).

    python scripts/backup_database.py                 # -> backups/db_<timestamp>/
    python scripts/backup_database.py --out some/dir

Used automatically by `seed_database.py --rebuild` before anything is dropped, so a rebuild of the
Supabase database is always reversible.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import MetaData, select  # noqa: E402

from app.database.session import get_engine  # noqa: E402


def backup(out: Path | None = None) -> Path:
    out = out or ROOT / "backups" / f"db_{datetime.now():%Y%m%d_%H%M%S}"
    out.mkdir(parents=True, exist_ok=True)
    engine = get_engine()
    meta = MetaData()
    meta.reflect(bind=engine)
    summary = {}
    with engine.connect() as conn:
        for table in meta.sorted_tables:
            rows = [dict(r._mapping) for r in conn.execute(select(table))]
            (out / f"{table.name}.json").write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")
            summary[table.name] = len(rows)
    (out / "_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Backed up {sum(summary.values())} rows from {len(summary)} tables to {out}")
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    backup(parser.parse_args().out)
