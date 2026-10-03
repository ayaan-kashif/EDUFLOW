import os
from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings


@lru_cache
def _get_session_factory():
    url = get_settings().database_url
    # SQLite needs aiosqlite as the async driver
    if url.startswith("sqlite"):
        import aiosqlite  # noqa: F401  — registers the async driver
        connect_args = {"check_same_thread": False}
    else:
        connect_args = {}
    options = {"poolclass": NullPool} if os.environ.get("VERCEL") and not url.startswith("sqlite") else {}
    engine = create_async_engine(
        url, pool_pre_ping=True, connect_args=connect_args, **options,
    )
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with _get_session_factory()() as session:
        yield session
