from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}}
    elif ":6543/" in url:
        # Supabase transaction pooler (PgBouncer): server-side prepared statements must be off, and a
        # small client pool is enough because the pooler multiplexes connections.
        kwargs = {"pool_pre_ping": True, "pool_size": 5, "max_overflow": 5, "connect_args": {"prepare_threshold": None}}
    elif "pooler.supabase.com:5432" in url:
        # Supabase session pooler allows only ~15 clients in total (shared by every deployment using
        # this database), so keep this process's share small and recycle idle connections.
        kwargs = {"pool_pre_ping": True, "pool_size": 3, "max_overflow": 3, "pool_recycle": 300}
    return create_engine(url, **kwargs)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request; routes/services commit explicitly."""
    db = get_session_factory()()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

