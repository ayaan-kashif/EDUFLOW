"""Create all tables in a SQLite database without needing Alembic or Docker.

Usage:
    DATABASE_URL=sqlite+aiosqlite:///curriculumos.db python scripts/setup_sqlite.py

Or use the default curriculumos.db and run:
    python scripts/setup_sqlite.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text

# Ensure the project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def main():
    # Set DATABASE_URL before importing app modules
    db_url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///curriculumos.db")
    if "sqlite" not in db_url:
        print(f"ERROR: DATABASE_URL must be a sqlite URL, got: {db_url}")
        print("Set it like: DATABASE_URL=sqlite+aiosqlite:///curriculumos.db")
        sys.exit(1)

    # Use the requested URL without overwriting provider keys or .env.

    # Now import the app (which will use the new DATABASE_URL)
    import aiosqlite  # noqa: F401 — registers the async driver
    from sqlalchemy.ext.asyncio import create_async_engine

    # Import all models so they register with Base.metadata
    from app.domain import models  # noqa: F401
    from app.domain.base import Base

    engine = create_async_engine(db_url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # SQLite create_all does not alter existing tables. Keep local portal
        # databases usable when a new nullable source field is introduced.
        tables = await conn.run_sync(lambda sync_conn: sa_inspect(sync_conn).get_table_names())
        if "class_outlines" in tables:
            columns = await conn.run_sync(
                lambda sync_conn: {c["name"] for c in sa_inspect(sync_conn).get_columns("class_outlines")}
            )
            if "source_text" not in columns:
                await conn.execute(text("ALTER TABLE class_outlines ADD COLUMN source_text TEXT"))
                await conn.execute(text(
                    "UPDATE class_outlines SET notes = NULL, study_plan = NULL, generated_by = NULL"
                ))

    async with engine.connect() as connection:
        tables = await connection.run_sync(lambda conn: sa_inspect(conn).get_table_names())
    await engine.dispose()
    db_path = db_url.split("///")[-1] if "///" in db_url else "curriculumos.db"

    print(f"\nCreated {len(tables)} tables in {db_path}:")
    for t in sorted(tables):
        print(f"   {t}")
    print("\nReady to run: uvicorn app.main:app")


if __name__ == "__main__":
    asyncio.run(main())
