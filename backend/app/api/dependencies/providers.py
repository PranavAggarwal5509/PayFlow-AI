from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database.session import get_db
from app.services.llm_extractor import LLMProvider, get_llm_provider
from app.services.pipeline import PipelineContext
from app.storage import LocalStorage, StorageBackend, SupabaseStorage


@lru_cache
def _storage_for(root: str) -> LocalStorage:
    return LocalStorage(__import__("pathlib").Path(root))


@lru_cache
def _supabase_storage_for(url: str, key: str, bucket: str) -> SupabaseStorage:
    return SupabaseStorage(supabase_url=url, service_role_key=key, bucket=bucket)


def get_storage(settings: Settings = Depends(get_settings)) -> StorageBackend:
    if settings.storage_backend == "supabase" and settings.supabase_service_role_key:
        return _supabase_storage_for(
            settings.supabase_url,
            settings.supabase_service_role_key,
            settings.supabase_bucket,
        )
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

