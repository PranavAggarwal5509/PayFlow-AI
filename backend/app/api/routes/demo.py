from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.providers import get_storage
from app.core.config import Settings, get_settings
from app.core.errors import ForbiddenError
from app.core.security import CurrentUser, Permission, require
from app.database.session import get_db
from app.schemas.common import ApiResponse
from app.services import demo_reset_service
from app.storage import StorageBackend

router = APIRouter(prefix="/demo", tags=["Demo"])


def _enabled(settings: Settings) -> None:
    if not settings.allow_demo_reset:
        raise ForbiddenError("Demo reset is disabled in this environment.")


@router.get("/reset")
def reset_preview(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: CurrentUser = Depends(require(Permission.DEMO_RESET)),
):
    """Counts of what a reset would delete. Nothing is changed."""
    _enabled(settings)
    return ApiResponse(data=demo_reset_service.preview(db).as_dict())


@router.post("/reset")
def reset(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    storage: StorageBackend = Depends(get_storage),
    user: CurrentUser = Depends(require(Permission.DEMO_RESET)),
):
    """Delete every live demo upload (and its runs, reviews, allocations, audit entries and PDFs)."""
    _enabled(settings)
    return ApiResponse(data=demo_reset_service.reset_live_uploads(db, storage, actor=user.id).as_dict())
