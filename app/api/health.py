from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/health/providers")
async def provider_health() -> dict:
    from app.providers.router import PROVIDER_EVENTS
    return {"events": list(PROVIDER_EVENTS), "scope": "Current server process; last 100 calls"}


@router.get("/health/db")
async def health_db(session: AsyncSession = Depends(get_session)) -> dict:
    try:
        for table in ("portal_users", "portal_sessions", "teacher_enrollments", "class_outlines"):
            await session.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Database or portal schema unavailable") from exc
    return {"status": "ok"}
