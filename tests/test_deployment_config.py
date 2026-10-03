"""Hosted database URLs must select an async driver."""

import asyncio
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app import db
from app.config import Settings
from app.db import get_session
from app.main import app


def test_managed_postgres_url_uses_asyncpg():
    for prefix in ("postgres://", "postgresql://"):
        settings = Settings(_env_file=None, database_url=f"{prefix}user:pass@host/db")
        assert settings.database_url == "postgresql+asyncpg://user:pass@host/db"


def test_sqlite_url_is_unchanged():
    url = "sqlite+aiosqlite:///./curriculumos.db"
    assert Settings(_env_file=None, database_url=url).database_url == url


def test_vercel_database_sessions_do_not_keep_local_connections(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setattr(db, "get_settings", lambda: SimpleNamespace(
        database_url="postgresql+asyncpg://user:pass@host/db"))
    db._get_session_factory.cache_clear()
    try:
        assert isinstance(db._get_session_factory().kw["bind"].sync_engine.pool, NullPool)
    finally:
        db._get_session_factory.cache_clear()


def test_neon_connection_url_uses_asyncpg_tls_options():
    settings = Settings(_env_file=None, database_url=(
        "postgresql://user:pass@host/db?sslmode=require&channel_binding=require"))
    assert settings.database_url == "postgresql+asyncpg://user:pass@host/db?ssl=require"


def test_readiness_rejects_missing_portal_schema(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'empty.db').as_posix()}")
    factory = async_sessionmaker(engine)

    async def empty_database():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = empty_database
    try:
        with TestClient(app) as client:
            response = client.get("/health/db")
            assert response.status_code == 503
            assert response.json()["detail"] == "Database or portal schema unavailable"
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())
