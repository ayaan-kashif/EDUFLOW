"""Bounded in-process ingestion jobs with SSE progress for a single-server prototype.

Job metadata is ephemeral. A multi-process deployment needs Redis-backed jobs;
the durable documents and spans remain in the database after a restart.
"""

import asyncio
import json
from dataclasses import dataclass, field
from time import monotonic
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from app.api.ingestion import UPLOAD_DIR, safe_upload_filename
from app.db import _get_session_factory
from app.domain.models import DocType, SourceSpan
from app.ingestion.service import IngestionService

router = APIRouter(prefix="/ingestion/jobs", tags=["ingestion jobs"])


@dataclass
class Job:
    id: str
    status: str = "queued"
    message: str = "Waiting for a parsing slot"
    result: dict | None = None
    created: float = field(default_factory=monotonic)

    def snapshot(self):
        return {
            "id": self.id,
            "status": self.status,
            "message": self.message,
            "result": self.result,
        }


JOBS: dict[str, Job] = {}
TASKS: set[asyncio.Task] = set()
MAX_JOBS = 40
MAX_UPLOAD_BYTES = 30 * 1024 * 1024


async def _process(job, path, title, doc_type):
    job.status, job.message = "parsing", "Parsing and persisting source passages"
    try:
        async with _get_session_factory()() as session:
            doc = await IngestionService(session).ingest_document(
                file_path=str(path), title=title, doc_type=doc_type
            )
            count = await session.scalar(
                select(func.count()).select_from(SourceSpan).where(SourceSpan.document_id == doc.id)
            )
            job.result = {"id": str(doc.id), "title": doc.title, "span_count": count}
            job.status, job.message = "completed", "Source passages are ready"
    except Exception:
        import logging

        logging.getLogger(__name__).exception("ingestion job %s failed", job.id)
        job.status, job.message = "failed", "Parsing failed; check provider health and server logs"


@router.post("", status_code=202)
async def create_job(
    title: str = Form(...), doc_type: DocType = Form(...), file: UploadFile = File(...)
):
    if sum(j.status in {"uploading", "queued", "parsing"} for j in JOBS.values()) >= 2:
        raise HTTPException(429, "Two ingestion jobs are already running; retry when one finishes")
    for jid, job in list(JOBS.items()):
        if job.status in {"completed", "failed"} and (
            monotonic() - job.created > 3600 or len(JOBS) >= MAX_JOBS
        ):
            JOBS.pop(jid)
    if len(JOBS) >= MAX_JOBS:
        raise HTTPException(429, "Job registry is full; retry later")
    jid = uuid4().hex
    job = Job(jid, status="uploading", message="Saving upload")
    JOBS[jid] = job  # reserve the slot before the first await
    UPLOAD_DIR.mkdir(exist_ok=True)
    path = UPLOAD_DIR / f"{jid}_{safe_upload_filename(file.filename)}"
    total = 0
    try:
        with path.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "Maximum document size is 30 MB")
                out.write(chunk)
        if total == 0:
            raise HTTPException(422, "Document is empty")
    except Exception:
        JOBS.pop(jid, None)
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    job.status, job.message = "queued", "Waiting for a parsing slot"
    task = asyncio.create_task(_process(job, path, title, doc_type))
    TASKS.add(task)
    task.add_done_callback(TASKS.discard)
    return {**job.snapshot(), "events_url": f"/ingestion/jobs/{jid}/events"}


@router.get("/{job_id}")
async def get_job(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(404, "Job expired or belongs to another server process")
    return JOBS[job_id].snapshot()


@router.get("/{job_id}/events")
async def job_events(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(404, "Job not found")

    async def events():
        last = None
        while job_id in JOBS:
            job = JOBS[job_id]
            payload = json.dumps(job.snapshot())
            if payload != last:
                yield f"data: {payload}\n\n"
                last = payload
            else:
                yield ": heartbeat\n\n"
            if job.status in {"completed", "failed"}:
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
