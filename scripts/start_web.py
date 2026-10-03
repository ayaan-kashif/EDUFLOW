"""Start EduFlow with the database schema ready for portal requests."""

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
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url

    if database_url.startswith("sqlite"):
        setup = [sys.executable, "scripts/setup_sqlite.py"]
    elif database_url.startswith("postgresql+asyncpg://"):
        setup = [sys.executable, "-m", "alembic", "upgrade", "head"]
    else:
        raise SystemExit("DATABASE_URL must use SQLite or PostgreSQL")

    subprocess.run(setup, cwd=root, env=env, check=True)
    server = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0",
              "--port", env.get("PORT", "8000")]
    os.chdir(root)
    if os.name == "nt":
        subprocess.run(server, env=env, check=True)
    else:
        os.execve(sys.executable, server, env)


if __name__ == "__main__":
    main()
