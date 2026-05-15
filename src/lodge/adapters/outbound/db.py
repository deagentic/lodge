from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from ...domain.config import settings


class Base(DeclarativeBase):
    pass


# Engine and session factory are initialized on first use so that:
# - Tests can import this module without asyncpg installed
# - The dependency override in tests/conftest.py prevents get_db from ever
#   calling _session_factory(), so no real connection is attempted
_engine = None
_factory = None


def _session_factory() -> async_sessionmaker:
    global _engine, _factory
    if _factory is None:
        _engine = create_async_engine(settings.database_url, echo=False)
        _factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _factory


def AsyncSessionLocal() -> AsyncSession:
    """Return a new async database session (lazy engine initialization)."""
    return _session_factory()()


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
