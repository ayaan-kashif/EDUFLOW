from datetime import date

import pytest
from fastapi.encoders import jsonable_encoder
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.studio import fold_ics, parse_disruption_dates
from app.db import get_session
from app.domain.base import Base
from app.domain.models import PlanVersion, TeachingUnit
from app.main import app


async def seed_test_demo(factory):
    """Synthetic fixtures stay in the test suite, outside public routes."""
    from tests.demo_fixture import seed_demo

    async with factory() as session:
        return jsonable_encoder(await seed_demo(session, reset_calendar=True))


def test_disruption_dates_are_explicit_and_deduplicated():
    assert parse_disruption_dates("Snow day Thursday + next Tuesday", date(2026, 10, 5)) == [
        date(2026, 10, 8),
        date(2026, 10, 13),
    ]
    assert parse_disruption_dates("2026-10-08 + 2026-10-08", date(2026, 10, 5)) == [
        date(2026, 10, 8)
    ]
    with pytest.raises(ValueError):
        parse_disruption_dates("close sometime later", date(2026, 10, 5))


def test_calendar_line_folding_counts_utf8_octets():
    folded = fold_ics("SUMMARY:" + "é" * 100)
    assert all(len(line.encode()) <= 75 for line in folded.split("\r\n"))
    assert folded.replace("\r\n ", "") == "SUMMARY:" + "é" * 100


@pytest.fixture
async def studio_client(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'studio.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    from app.workers import ingestion as jobs

    jobs.JOBS.clear()
    monkeypatch.setattr(jobs, "_get_session_factory", lambda: factory)
    monkeypatch.setattr(jobs, "UPLOAD_DIR", tmp_path / "uploads")

    async def sessions():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = sessions
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, factory
    app.dependency_overrides.clear()
    if jobs.TASKS:
        import asyncio

        await asyncio.gather(*jobs.TASKS)
    jobs.JOBS.clear()
    await engine.dispose()


async def test_demo_plan_replan_audit_forecast_and_export_on_real_sqlite(studio_client):
    client, factory = studio_client
    demo = await seed_test_demo(factory)
    repeat = await seed_test_demo(factory)
    assert repeat["document_id"] == demo["document_id"]
    spans = await client.get(f"/documents/{demo['document_id']}/spans")
    assert len(spans.json()) == 10
    assert all(s["content_hash"].startswith("sha256:") for s in spans.json())
    request = {k: demo[k] for k in ["calendar_id", "node_ids", "subject", "class_id"]}
    request["minimum_duration_ratio"] = 0.66
    initial = await client.post("/planning/plans", json=request)
    assert initial.status_code == 200, initial.text
    initial = initial.json()
    assert not initial["unscheduled_unit_ids"]
    assert initial["weighted_coverage"] == 1
    rows = (await client.get(f"/planning/plans/{initial['plan_version_id']}")).json()
    assert len(rows) >= 10
    why = await client.get(
        f"/planning/plans/{initial['plan_version_id']}/units/{rows[0]['teaching_unit_id']}/justification"
    )
    assert why.status_code == 200, why.text
    taught = await client.post(
        f"/planning/plans/{initial['plan_version_id']}/sessions/{rows[0]['id']}/taught"
    )
    assert taught.status_code == 200
    preview = await client.post(
        f"/calendars/{demo['calendar_id']}/disruptions/preview",
        json={
            "text": "snow day Thursday + sports day next Tuesday",
            "reference_date": demo["reference_date"],
        },
    )
    assert preview.status_code == 200
    dates = preview.json()["dates"]
    assert dates == ["2026-10-08", "2026-10-13"]
    apply = await client.post(
        f"/calendars/{demo['calendar_id']}/disruptions", json={"dates": dates}
    )
    assert apply.json()["windows_disrupted"] == 2
    request["parent_version_id"] = initial["plan_version_id"]
    new = await client.post("/planning/plans", json=request)
    assert new.status_code == 200, new.text
    plan = new.json()
    assert not plan["unscheduled_unit_ids"]
    assert plan["shortened_count"] >= 1
    saved = (await client.get(f"/planning/plans/{plan['plan_version_id']}")).json()
    assert any(r["status"] == "taught" and r["date"] == rows[0]["date"] for r in saved)
    diff = await client.get(f"/planning/plans/{plan['plan_version_id']}/diff")
    assert len(diff.json()) == 10  # aggregated by unit, never discard split sessions
    assert any(item["change_type"] == "compressed" for item in diff.json())
    export = await client.get(f"/planning/plans/{plan['plan_version_id']}/export.ics")
    assert export.status_code == 200
    assert export.text.startswith("BEGIN:VCALENDAR\r\n")
    assert export.text.count("BEGIN:VEVENT") == len(plan["assignments"])
    pdf = await client.get(f"/planning/plans/{plan['plan_version_id']}/export.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    from io import BytesIO

    from pypdf import PdfReader

    assert "EduFlow" in PdfReader(BytesIO(pdf.content)).pages[0].extract_text()
    audit = await client.post(
        "/evidence/audit",
        json={"text": "Enzymes are biological catalysts.\nBIO.FAKE.99 is an official code."},
    )
    assert audit.status_code == 200
    assert audit.json()["claims"][0]["status"] == "exact_source_match"
    assert audit.json()["claims"][1]["status"] == "unknown_code"
    forecast = await client.post(
        "/planning/resilience", json={**request, "samples": 10, "disruption_rate": 0}
    )
    assert forecast.status_code == 200, forecast.text
    assert forecast.json()["high_emphasis_coverage_probability"] == 1
    before = None
    async with factory() as session:
        before = len((await session.execute(select(PlanVersion))).scalars().all())
    preview = await client.post("/planning/preview", json=request)
    assert preview.status_code == 200, preview.text
    async with factory() as session:
        assert len((await session.execute(select(PlanVersion))).scalars().all()) == before
        units = (await session.execute(select(TeachingUnit))).scalars().all()
        assert len(units) == 10


async def test_unknown_document_and_out_of_term_closure_are_rejected(studio_client):
    from uuid import uuid4

    client, factory = studio_client
    missing = await client.get(f"/documents/{uuid4()}/file")
    assert missing.status_code == 404
    demo = await seed_test_demo(factory)
    invalid = await client.post(
        f"/calendars/{demo['calendar_id']}/disruptions/preview",
        json={"text": "2027-01-01", "reference_date": "2026-10-05"},
    )
    assert invalid.status_code == 422
    await client.get("/")


async def test_ingestion_job_persists_pdf_and_emits_terminal_sse(studio_client, monkeypatch):
    import asyncio
    from pathlib import Path

    from app.providers import parsing
    from app.providers.parsing.pypdf_provider import PyPdfParserProvider
    from app.workers import ingestion as jobs

    class LocalRouter:
        async def call(self, fn):
            return await fn(PyPdfParserProvider())

    monkeypatch.setattr(parsing, "get_parser_chain", lambda: LocalRouter())
    client, factory = studio_client
    pdf = Path("tests/fixtures/demo-biology.pdf").read_bytes()
    response = await client.post(
        "/ingestion/jobs",
        data={"title": "Streamed source", "doc_type": "syllabus"},
        files={"file": ("../../biology.pdf", pdf, "application/pdf")},
    )
    assert response.status_code == 202, response.text
    job = response.json()
    await asyncio.gather(*jobs.TASKS)
    result = (await client.get(f"/ingestion/jobs/{job['id']}")).json()
    assert result["status"] == "completed"
    assert result["result"]["span_count"] >= 10
    stream = await client.get(job["events_url"])
    assert stream.headers["content-type"].startswith("text/event-stream")
    assert '"status": "completed"' in stream.text
    from uuid import UUID

    from app.domain.models import SourceDocument

    async with factory() as session:
        doc = await session.get(SourceDocument, UUID(result["result"]["id"]))
        assert Path(doc.file_path).parent == jobs.UPLOAD_DIR


async def test_failed_ingestion_emits_failure_and_capacity_is_bounded(studio_client, monkeypatch):
    import asyncio

    from app.providers import parsing
    from app.workers import ingestion as jobs

    class FailingRouter:
        async def call(self, fn):
            raise RuntimeError("private parser details")

    monkeypatch.setattr(parsing, "get_parser_chain", lambda: FailingRouter())
    client, _ = studio_client
    response = await client.post(
        "/ingestion/jobs",
        data={"title": "Broken source", "doc_type": "syllabus"},
        files={"file": ("broken.pdf", b"broken", "application/pdf")},
    )
    await asyncio.gather(*jobs.TASKS)
    stream = await client.get(response.json()["events_url"])
    assert '"status": "failed"' in stream.text
    assert "private parser details" not in stream.text
    jobs.JOBS["active1"] = jobs.Job("active1", status="uploading")
    jobs.JOBS["active2"] = jobs.Job("active2", status="parsing")
    blocked = await client.post(
        "/ingestion/jobs",
        data={"title": "Busy", "doc_type": "syllabus"},
        files={"file": ("busy.pdf", b"data", "application/pdf")},
    )
    assert blocked.status_code == 429


async def test_empty_and_oversized_uploads_release_their_slot(studio_client, monkeypatch):
    from app.workers import ingestion as jobs

    client, _ = studio_client
    monkeypatch.setattr(jobs, "MAX_UPLOAD_BYTES", 4)
    for data, status in [(b"", 422), (b"12345", 413)]:
        response = await client.post(
            "/ingestion/jobs",
            data={"title": "Invalid", "doc_type": "syllabus"},
            files={"file": ("source.pdf", data, "application/pdf")},
        )
        assert response.status_code == status
        assert not jobs.JOBS
        assert not list(jobs.UPLOAD_DIR.iterdir())
