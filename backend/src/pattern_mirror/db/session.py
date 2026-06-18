"""Engine and session factory, plus the FastAPI session dependency.

The engine is created once per process and cached. CRUD and aggregation paths
are synchronous (see ``docs/CODE_STYLE.md`` on async vs sync), so this uses the
synchronous engine and ``Session``; the async engine path is introduced only if
the analysis/streaming code needs it.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from pattern_mirror.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Return the process-wide SQLAlchemy engine, created once and cached."""
    settings = get_settings()
    return create_engine(settings.database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    """Return the process-wide session factory bound to the engine."""
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """Yield a request-scoped session, committing on success and rolling back on error.

    Used as a FastAPI dependency (``Depends(get_session)``); the session is
    closed once the request finishes regardless of outcome.
    """
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
