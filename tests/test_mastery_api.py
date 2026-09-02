"""Endpoint-level tests for app/api/mastery.py.

Exercises the real DB queries (list, create, summary) against a FakeSession
with canned CurriculumNode and ClassMasterySignal rows.
"""

import uuid
from datetime import datetime, timezone

from app.api.mastery import (
    _latest_per_node,
    create_mastery_signal,
    list_mastery_signals,
    mastery_summary,
)
from app.domain.models import (
    ClassMasterySignal,
    CurriculumNode,
    MasteryStatus,
    NodeType,
    Origin,
)
from tests.conftest import FakeSession


def _node(label="Arrays"):
    return CurriculumNode(
        id=uuid.uuid4(),
        node_type=NodeType.OBJECTIVE,
        label=label,
        origin=Origin.OFFICIAL,
        confidence=0.9,
    )


def _signal(class_id, node_id, status, teacher="demo-teacher"):
    s = ClassMasterySignal(
        id=uuid.uuid4(),
        class_id=class_id,
        node_id=node_id,
        status=status,
        marked_by=teacher,
    )
    s.created_at = datetime.now(timezone.utc)
    return s


# ── Pure logic: _latest_per_node ──────────────────────────────────────


def test_latest_per_node_returns_most_recent():
    node = uuid.uuid4()
    old = _signal("CS-4A", node, MasteryStatus.RETEACH)
    old.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    new = _signal("CS-4A", node, MasteryStatus.MASTERED)
    new.created_at = datetime(2026, 1, 5, tzinfo=timezone.utc)

    result = _latest_per_node([old, new])
    assert len(result) == 1
    assert result[0].status == MasteryStatus.MASTERED


def test_latest_per_node_separates_classes():
    node = uuid.uuid4()
    s1 = _signal("CS-4A", node, MasteryStatus.RETEACH)
    s2 = _signal("CS-5B", node, MasteryStatus.MASTERED)

    result = _latest_per_node([s1, s2])
    assert len(result) == 2


# ── Endpoint: list_mastery_signals ────────────────────────────────────


async def test_list_mastery_signals_returns_latest_per_node():
    node = _node("Arrays")
    old = _signal("CS-4A", node.id, MasteryStatus.RETEACH)
    old.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    new = _signal("CS-4A", node.id, MasteryStatus.MASTERED)
    new.created_at = datetime(2026, 1, 5, tzinfo=timezone.utc)

    session = FakeSession({
        ClassMasterySignal: [old, new],
        CurriculumNode: [node],
    })

    from fastapi import Query
    from starlette.testclient import TestClient
    from fastapi import FastAPI
    from app.api.mastery import router

    app = FastAPI()
    app.include_router(router)

    # Override the session dependency
    async def _get_session():
        yield session

    from app.db import get_session
    app.dependency_overrides[get_session] = _get_session

    client = TestClient(app)
    resp = client.get("/mastery/", params={"class_id": "CS-4A"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["status"] == "mastered"
    assert data[0]["node_label"] == "Arrays"


async def test_list_mastery_signals_empty_class():
    session = FakeSession({})

    from fastapi import FastAPI
    from starlette.testclient import TestClient
    from app.api.mastery import router
    from app.db import get_session

    app = FastAPI()
    app.include_router(router)
    async def _get_session():
        yield session
    app.dependency_overrides[get_session] = _get_session

    client = TestClient(app)
    resp = client.get("/mastery/", params={"class_id": "CS-4A"})
    assert resp.status_code == 200
    assert resp.json() == []


# ── Endpoint: create_mastery_signal ───────────────────────────────────


async def test_create_mastery_signal_persists_and_returns():
    node = _node("Arrays")
    session = FakeSession({CurriculumNode: [node]})

    from fastapi import FastAPI
    from starlette.testclient import TestClient
    from app.api.mastery import router
    from app.db import get_session

    app = FastAPI()
    app.include_router(router)
    async def _get_session():
        yield session
    app.dependency_overrides[get_session] = _get_session

    client = TestClient(app)
    resp = client.post("/mastery/", json={
        "class_id": "CS-4A",
        "node_id": str(node.id),
        "status": "mastered",
        "teacher_id": "demo-teacher",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "mastered"
    assert data["node_label"] == "Arrays"
    assert data["class_id"] == "CS-4A"
    assert session.committed


async def test_create_mastery_signal_unknown_node_returns_404():
    session = FakeSession({CurriculumNode: []})

    from fastapi import FastAPI
    from starlette.testclient import TestClient
    from app.api.mastery import router
    from app.db import get_session

    app = FastAPI()
    app.include_router(router)
    async def _get_session():
        yield session
    app.dependency_overrides[get_session] = _get_session

    client = TestClient(app)
    resp = client.post("/mastery/", json={
        "class_id": "CS-4A",
        "node_id": str(uuid.uuid4()),
        "status": "mastered",
        "teacher_id": "demo-teacher",
    })
    assert resp.status_code == 404


# ── Endpoint: mastery_summary ─────────────────────────────────────────


async def test_mastery_summary_counts_by_status():
    n1, n2, n3, n4 = _node("Arrays"), _node("Stacks"), _node("Trees"), _node("Graphs")
    signals = [
        _signal("CS-4A", n1.id, MasteryStatus.MASTERED),
        _signal("CS-4A", n2.id, MasteryStatus.NEEDS_REINFORCEMENT),
        _signal("CS-4A", n3.id, MasteryStatus.RETEACH),
    ]

    session = FakeSession({
        ClassMasterySignal: signals,
        CurriculumNode: [n1, n2, n3, n4],
    })

    from fastapi import FastAPI
    from starlette.testclient import TestClient
    from app.api.mastery import router
    from app.db import get_session

    app = FastAPI()
    app.include_router(router)
    async def _get_session():
        yield session
    app.dependency_overrides[get_session] = _get_session

    client = TestClient(app)
    resp = client.get("/mastery/summary", params={"class_id": "CS-4A"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_objectives"] == 4
    assert data["mastered"] == 1
    assert data["needs_reinforcement"] == 1
    assert data["reteach"] == 1
    assert data["unmarked"] == 1
