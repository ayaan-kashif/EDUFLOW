"""Enrollment must gate published material and teacher edits."""

import asyncio
import json

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import classroom
from app.db import get_session
from app.domain.base import Base
from app.main import app
from app.providers.base import LLMResponse


def test_teacher_student_flow_and_isolation(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'classroom.db').as_posix()}")

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(setup())
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def session_override():
        async with factory() as session:
            yield session

    async def fake_generate(outline):
        return "## Cell Biology\nCells have organelles.", {
            "days": [{"day": day, "focus": "Cells", "tasks": ["Review notes"], "minutes": 30}
                     for day in range(1, 8)]}, "test model"

    monkeypatch.setattr(classroom, "generate_material", fake_generate)
    app.dependency_overrides[get_session] = session_override
    try:
        with TestClient(app) as teacher, TestClient(app) as student, TestClient(app) as outsider:
            t = teacher.post("/classroom/register", json={"name": "Ms Lee", "email": "lee@example.com",
                                                        "password": "secretpass", "role": "teacher"})
            assert t.status_code == 200
            code = t.json()["enrollment_code"]
            assert teacher.post("/classroom/teacher/outlines", headers={"Origin": "https://other.example"}, json={
                "title": "Blocked", "subject": "Biology", "content": "This should be rejected by the origin guard."}).status_code == 403
            s = student.post("/classroom/register", json={"name": "Sam", "email": "sam@example.com",
                                                        "password": "secretpass", "role": "student"})
            assert s.status_code == 200
            outsider.post("/classroom/register", json={"name": "Other", "email": "other@example.com",
                                                        "password": "secretpass", "role": "student"})
            assert student.get("/classroom/teacher/outlines").status_code == 403
            outline = teacher.post("/classroom/teacher/outlines", json={
                "title": "Cell Biology", "subject": "Biology",
                "content": "Organelles and their functions; plant and animal cells."})
            assert outline.status_code == 201
            outline_id = outline.json()["id"]
            assert student.get("/classroom/student/outlines").json() == []
            assert student.post("/classroom/student/enroll", json={"code": "WRONG12"}).status_code == 404
            assert student.post("/classroom/student/enroll", json={"code": code.lower()}).status_code == 200
            assert student.get("/classroom/student/outlines").json() == []  # draft
            assert teacher.post(f"/classroom/teacher/outlines/{outline_id}/publish").status_code == 200
            assert teacher.post(f"/classroom/teacher/outlines/{outline_id}/generate").status_code == 200
            material = student.get("/classroom/student/outlines").json()
            assert len(material) == 1
            assert material[0]["study_plan"]["days"][0]["focus"] == "Cells"
            assert outsider.get("/classroom/student/outlines").json() == []
            assert student.put(f"/classroom/teacher/outlines/{outline_id}", json={
                "title": "Changed", "subject": "Biology", "content": "This is a long enough outline."}).status_code == 403
            assert teacher.put(f"/classroom/teacher/outlines/{outline_id}", json={
                "title": "Cell Biology II", "subject": "Biology",
                "content": "Updated material about organelles and cell membranes."}).status_code == 200
            assert student.get("/classroom/student/outlines").json() == []  # edits require republish
            assert teacher.post("/classroom/logout").status_code == 200
            assert teacher.get("/classroom/teacher/outlines").status_code == 401
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())


def test_ai_material_contract(monkeypatch):
    from app.providers import llm

    payload = {
        "notes_markdown": "# Cells\nA clear explanation and self-check questions.",
        "study_plan": [{"day": day, "focus": "Cells", "tasks": ["Review and quiz"], "minutes": 25}
                       for day in range(1, 8)],
    }

    class FakeProvider:
        async def complete(self, messages, **kwargs):
            assert "Organelles" in messages[1].content
            return LLMResponse(text=json.dumps(payload), model="demo", provider="fake",
                               input_tokens=10, output_tokens=100)

    class FakeChain:
        async def call(self, fn):
            return await fn(FakeProvider())

    monkeypatch.setattr(llm, "get_generation_chain", lambda: FakeChain())
    outline = classroom.ClassOutline(title="Cells", subject="Biology", content="Organelles")
    notes, plan, generated_by = asyncio.run(classroom.generate_material(outline))
    assert notes.startswith("# Cells")
    assert len(plan["days"]) == 7
    assert generated_by == "fake / demo"
