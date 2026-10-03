# ruff: noqa: F811
from uuid import UUID, uuid4

from sqlalchemy import select

from app.domain.models import InstructionWindow, PlanVersion
from tests.test_studio_api import seed_test_demo, studio_client  # noqa: F401


async def make_plan(client, factory):
    demo = await seed_test_demo(factory)
    response = await client.post(
        "/planning/plans",
        json={
            **{k: demo[k] for k in ("calendar_id", "node_ids", "subject", "class_id")},
            "minimum_duration_ratio": 0.66,
        },
    )
    assert response.status_code == 200, response.text
    return demo, response.json()["plan_version_id"]


async def test_recovery_preview_is_read_only_and_apply_matches_review(studio_client):
    client, factory = studio_client
    demo, plan = await make_plan(client, factory)
    before = (await client.get("/planning/plans")).json()
    async with factory() as session:
        available = list((await session.execute(select(InstructionWindow.is_available))).scalars())
    response = await client.post(
        f"/studio/plans/{plan}/recovery",
        json={"dates": ["2026-10-08", "2026-10-13"], "minimum_duration_ratio": 0.66},
    )
    assert response.status_code == 200, response.text
    preview = response.json()
    assert len(preview["options"]) == 3
    assert (await client.get("/planning/plans")).json() == before
    async with factory() as session:
        assert (
            list((await session.execute(select(InstructionWindow.is_available))).scalars())
            == available
        )
    choice = next(o for o in preview["options"] if o["key"] == "coverage")
    applied = await client.post(
        f"/studio/recovery/{preview['scenario_id']}/apply", json={"option": "coverage"}
    )
    assert applied.status_code == 200, applied.text
    new = applied.json()["plan_id"]
    rows = (await client.get(f"/planning/plans/{new}")).json()
    assert sorted(
        (r["teaching_unit_id"], r["date"], r["scheduled_minutes"]) for r in rows
    ) == sorted(
        (r["unit_id"], r["date"], r["scheduled_minutes"]) for r in choice["result"]["assignments"]
    )
    repeat = await client.post(
        f"/studio/recovery/{preview['scenario_id']}/apply", json={"option": "coverage"}
    )
    assert repeat.json() == {"plan_id": new, "reused": True}
    conflict = await client.post(
        f"/studio/recovery/{preview['scenario_id']}/apply", json={"option": "depth"}
    )
    assert conflict.status_code == 409
    report = (await client.get(f"/studio/plans/{new}/coverage")).json()
    assert report["totals"]["objectives"] == 10
    assert report["totals"]["without_sources"] == 0
    assert report["totals"]["without_verified_claims"] == 10
    assert set(report["context"]["node_ids"]) == set(demo["node_ids"])


async def test_recovery_rejects_changed_history(studio_client):
    client, factory = studio_client
    _, plan = await make_plan(client, factory)
    preview = (
        await client.post(f"/studio/plans/{plan}/recovery", json={"dates": ["2026-10-08"]})
    ).json()
    rows = (await client.get(f"/planning/plans/{plan}")).json()
    await client.post(f"/planning/plans/{plan}/sessions/{rows[0]['id']}/taught")
    response = await client.post(
        f"/studio/recovery/{preview['scenario_id']}/apply", json={"option": "depth"}
    )
    assert response.status_code == 409
    response = await client.post(
        f"/studio/plans/{plan}/recovery", json={"dates": [rows[0]["date"]]}
    )
    assert response.status_code == 409


async def test_source_setup_is_scoped_and_reuses_units(studio_client):
    client, factory = studio_client
    demo = await seed_test_demo(factory)
    response = await client.get(f"/studio/documents/{demo['document_id']}/curriculum")
    assert len(response.json()["nodes"]) == 10
    body = {
        "document_id": demo["document_id"],
        "node_ids": demo["node_ids"],
        "subject": "Biology",
        "class_id": "NEW-CLASS",
        "term_start": "2026-11-02",
        "term_end": "2026-11-27",
        "weekdays": [0, 1, 2, 3, 4],
    }
    invalid = await client.post("/studio/setup", json={**body, "node_ids": [str(uuid4())]})
    assert invalid.status_code == 422
    result = await client.post("/studio/setup", json=body)
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["windows_created"] == 20
    assert data["reused_objectives"] == 10
    async with factory() as session:
        assert await session.get(PlanVersion, UUID(data["plan_id"]))
    report = (await client.get(f"/studio/plans/{data['plan_id']}/coverage")).json()
    assert report["totals"]["scheduled"] == 10
    assert report["context"]["class_id"] == "NEW-CLASS"


async def test_extraction_cache_reuses_and_invalidates_source(studio_client, monkeypatch):
    from types import SimpleNamespace

    from app.domain.models import SourceSpan
    from app.ingestion.curriculum_extraction import CurriculumExtractionService

    _, factory = studio_client
    demo = await seed_test_demo(factory)
    calls = []

    class Chain:
        async def call(self, _callback):
            calls.append(True)
            return SimpleNamespace(
                model="test",
                text='{"nodes":[{"ref":"TEST.CELL","type":"objective","label":"Describe cells"}]}',
            )

    async with factory() as session:
        service = CurriculumExtractionService(session)

        async def chain():
            return Chain()

        monkeypatch.setattr(service, "_get_chain", chain)
        first = await service.extract(UUID(demo["document_id"]))
        second = await service.extract(UUID(demo["document_id"]))
        assert [n.id for n in first] == [n.id for n in second]
        assert len(calls) == 1
        span = (
            (
                await session.execute(
                    select(SourceSpan).where(SourceSpan.document_id == UUID(demo["document_id"]))
                )
            )
            .scalars()
            .first()
        )
        span.text += " Explain cell division."
        await session.commit()
        await service.extract(UUID(demo["document_id"]))
        assert len(calls) == 2
