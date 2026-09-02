"""Create all tables in a SQLite database without needing Alembic or Docker.

Usage:
    DATABASE_URL=sqlite+aiosqlite:///curriculumos.db python scripts/setup_sqlite.py

Or set it in .env and just run:
    python scripts/setup_sqlite.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Ensure the project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def main():
    # Set DATABASE_URL before importing app modules
    db_url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///curriculumos.db")
    if "sqlite" not in db_url:
        print(f"ERROR: DATABASE_URL must be a sqlite URL, got: {db_url}")
        print("Set it like: DATABASE_URL=sqlite+aiosqlite:///curriculumos.db")
        sys.exit(1)

    # Write to .env if not already set
    env_path = Path(".env")
    if env_path.exists():
        content = env_path.read_text()
        if "DATABASE_URL" not in content or "sqlite" not in content:
            # Add/replace DATABASE_URL
            lines = content.split("\n")
            new_lines = []
            replaced = False
            for line in lines:
                if line.startswith("DATABASE_URL="):
                    new_lines.append(f"DATABASE_URL={db_url}")
                    replaced = True
                else:
                    new_lines.append(line)
            if not replaced:
                new_lines.insert(0, f"DATABASE_URL={db_url}")
            env_path.write_text("\n".join(new_lines))
            print(f"Updated .env with DATABASE_URL={db_url}")
    else:
        env_path.write_text(f"DATABASE_URL={db_url}\n")
        print(f"Created .env with DATABASE_URL={db_url}")

    # Now import the app (which will use the new DATABASE_URL)
    from sqlalchemy.ext.asyncio import create_async_engine

    import aiosqlite  # noqa: F401 — registers the async driver

    # Import all models so they register with Base.metadata
    from app.domain import models  # noqa: F401
    from app.domain.base import Base

    engine = create_async_engine(db_url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await engine.dispose()

    # Count tables
    from sqlalchemy import inspect as sa_inspect

    iengine = await engine.connect()
    # For SQLite, use a sync check
    import sqlite3

    db_path = db_url.split("///")[-1] if "///" in db_url else "curriculumos.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()

    print(f"\nCreated {len(tables)} tables in {db_path}:")
    for t in sorted(tables):
        print(f"   {t}")
    print(f"\nReady to run: uvicorn app.main:app")


if __name__ == "__main__":
    asyncio.run(main())
