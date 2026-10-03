"""Apply persistent PostgreSQL migrations during a Vercel build."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))
    from app.config import get_settings

    database_url = get_settings().database_url
    if not database_url.startswith("postgresql+asyncpg://"):
        raise SystemExit("Vercel requires a persistent PostgreSQL DATABASE_URL; SQLite is not supported")
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                   cwd=root, env=env, check=True)


if __name__ == "__main__":
    main()
