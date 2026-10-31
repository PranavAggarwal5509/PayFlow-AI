import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import NotFoundError
from app.core.security import CurrentUser, get_current_user
from app.database.session import get_db, get_session_factory
from app.models.enums import RunStatus
from app.models.invoice import Invoice
from app.models.processing import ProcessingRun, StageEvent
from app.repositories.invoice_repository import run_summary
from app.schemas.common import ApiResponse, page_meta
from app.schemas.invoice import RunDetail, RunSummary, StageEventOut

router = APIRouter(prefix="/runs", tags=["Processing"])

TERMINAL = {RunStatus.COMPLETED.value, RunStatus.FAILED.value}


def build_run_detail(db: Session, run: ProcessingRun) -> RunDetail:
    summary = run_summary(run, run.invoice)
    stages = db.scalars(
        select(StageEvent).where(StageEvent.run_id == run.id).order_by(StageEvent.started_at)
    )
    latest_number = db.scalar(
        select(func.max(ProcessingRun.run_number)).where(ProcessingRun.invoice_id == run.invoice_id)
    )
    return RunDetail(
        **summary.model_dump(),
        stages=[StageEventOut.model_validate(s) for s in stages],
        can_retry=run.status == RunStatus.FAILED.value and run.run_number == latest_number,
    )


@router.get("", response_model=ApiResponse[list[RunSummary]])
def list_runs(
    status: str | None = None,
    invoice_id: UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    stmt = select(ProcessingRun)
    if status:
        stmt = stmt.where(ProcessingRun.status == status)
    if invoice_id:
        stmt = stmt.where(ProcessingRun.invoice_id == invoice_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.options(selectinload(ProcessingRun.invoice))
        .order_by(ProcessingRun.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return ApiResponse(
        data=[run_summary(r, r.invoice) for r in rows], meta=page_meta(page, page_size, total)
    )


@router.get("/{run_id}", response_model=ApiResponse[RunDetail])
def get_run(run_id: UUID, db: Session = Depends(get_db), _: CurrentUser = Depends(get_current_user)):
    run = db.get(ProcessingRun, run_id)
    if run is None:
        raise NotFoundError("Processing run not found.")
    return ApiResponse(data=build_run_detail(db, run))


def _snapshot(run_id: UUID) -> dict | None:
    with get_session_factory()() as db:
        run = db.get(ProcessingRun, run_id)
        if run is None:
            return None
        return json.loads(build_run_detail(db, run).model_dump_json())


@router.get("/{run_id}/events")
async def run_events(run_id: UUID, db: Session = Depends(get_db), _: CurrentUser = Depends(get_current_user)):
    """Server-Sent Events carrying the real persisted run state (no simulated progress)."""
    if db.get(ProcessingRun, run_id) is None:
        raise NotFoundError("Processing run not found.")
    db.close()

    async def stream():
        last: str | None = None
        idle = 0
        for _ in range(900):  # ≤ 15 min
            snapshot = await asyncio.to_thread(_snapshot, run_id)
            if snapshot is None:
                return
            payload = json.dumps(snapshot)
            if payload != last:
                last, idle = payload, 0
                yield f"event: run\ndata: {payload}\n\n"
                if snapshot["status"] in TERMINAL:
                    yield "event: done\ndata: {}\n\n"
                    return
            else:
                idle += 1
                if idle % 15 == 0:
                    yield ": keep-alive\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )  # fmt: skip


__all__ = ["Invoice", "router"]

