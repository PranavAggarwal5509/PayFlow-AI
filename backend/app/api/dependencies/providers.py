from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database.session import get_db
from app.services.llm_extractor import LLMProvider, get_llm_provider
from app.services.pipeline import PipelineContext
from app.storage import LocalStorage, StorageBackend


@lru_cache
def _storage_for(root: str) -> LocalStorage:
    return LocalStorage(__import__("pathlib").Path(root))


def get_storage(settings: Settings = Depends(get_settings)) -> StorageBackend:
    return _storage_for(str(settings.upload_dir))


def get_llm(settings: Settings = Depends(get_settings)) -> LLMProvider:
    return get_llm_provider(settings)


def get_pipeline_context(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    storage: StorageBackend = Depends(get_storage),
    llm: LLMProvider = Depends(get_llm),
) -> PipelineContext:
    return PipelineContext(db=db, settings=settings, storage=storage, llm=llm)

