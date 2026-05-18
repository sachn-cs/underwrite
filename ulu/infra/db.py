"""Async database engine and session management with read replica support.

Item 9 from production roadmap.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from ulu.infra.config import settings

Base = declarative_base()


class DatabaseConnectionError(Exception):
    """Raised when the database is unreachable after retries."""


def _create_engine_with_retry(url: str, retries: int = 3, backoff: float = 1.0):
    if not url:
        raise ValueError("DATABASE_URL is not configured")
    engine_kwargs: dict = dict(
        echo=settings.app_env == "development",
        future=True,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    if url.startswith("postgresql"):
        engine_kwargs["pool_size"] = 10
        engine_kwargs["max_overflow"] = 20
    last_exc = None
    for attempt in range(retries):
        try:
            return create_async_engine(url, **engine_kwargs)
        except (ConnectionError, TimeoutError) as exc:
            last_exc = exc
            if attempt < retries - 1:
                import time

                time.sleep(backoff * (2 ** attempt))
    raise DatabaseConnectionError(f"database unreachable after {retries} attempts: {last_exc}") from last_exc


def _get_engine():
    return _create_engine_with_retry(settings.database_url)


def _get_read_engine():
    read_url = getattr(settings, "read_database_url", None) or settings.database_url
    return _create_engine_with_retry(read_url)


def _get_session_maker(engine):
    return async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yields an async database session for dependency injection."""
    AsyncSessionLocal = _get_session_maker(_get_engine())
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_db_read_session() -> AsyncGenerator[AsyncSession, None]:
    """Yields a read-only async session routed to replica when configured."""
    AsyncSessionLocal = _get_session_maker(_get_read_engine())
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
