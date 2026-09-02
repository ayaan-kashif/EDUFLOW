"""Endpoint-level tests for the planning justification API.

Tests the GET /planning/plans/{id}/units/{id}/justification endpoint
against a FakeSession with canned data.
"""

import uuid
from datetime import date, time

from app.domain.models import (
    AcademicCalendar,
    CalendarDay,
    CurriculumNode,
    DayType,
    InstructionWindow,
    NodeType,
    Origin,
    PlanVersion,
    ScheduledUnit,
    ScheduledUnitStatus,
    TeachingUnit,
)
from tests.conftest import FakeSession


def _node(label="Arrays", syllabus_ref="CS201.2.1"):
    return CurriculumNode(
        id=uuid.uuid4(),
        node_type=NodeType.OBJECTIVE,
        label=label,
        syllabus_ref=syllabus_ref,
        origin=Origin.OFFICIAL,
        confidence=0.9,
    )


def _unit(node, minutes=60, priority=0.5, prereq_ids=None):
    return TeachingUnit(
        id=uuid.uuid4(),
        node_id=node.id,
        duration_minutes=minutes,
        splittable=False,
        priority=priority,
        prerequisite_unit_ids=prereq_ids,
    )


def _calendar():
    return AcademicCalendar(
        id=uuid.uuid4(),
        school_id="test-school",
        term_start=date(2026, 1, 5),
        term_end=date(2026, 2, 28),
    )


def _day(cal, dt):
    return CalendarDay(id=uuid.uuid4(), calendar_id=cal.id, date=dt, day_type=DayType.SCHOOL_DAY)


def _window(day):
    return InstructionWindow(
        id=uuid.uuid4(), calendar_day_id=day.id,
        subject="Data Structures", class_id="CS-4A",
        start_time=time(9, 0), end_time=time(10, 0),
        available_minutes=60, is_available=True,
    )


def _plan(cal, trigger="initial_plan", parent_id=None):
    return PlanVersion(
        id=uuid.uuid4(), calendar_id=cal.id,
        parent_version_id=parent_id, trigger_reason=trigger,
    )


def _scheduled(unit, window, plan_version):
    return ScheduledUnit(
        id=uuid.uuid4(), unit_id=unit.id,
        instruction_window_id=window.id,
        scheduled_minutes=unit.duration_minutes,
        status=ScheduledUnitStatus.PLANNED,
        plan_version=plan_version.id,
    )


def _test_app(session):
    """Create a minimal FastAPI app with the planning router."""
    from fastapi import FastAPI
    from app.api.planning import router
    from app.db import get_session

    app = FastAPI()
    app.include_router(router)

    async def _get_session():
        yield session

    app.dependency_overrides[get_session] = _get_session
    return app


async def test_justification_returns_node_and_prerequisites():
    from starlette.testclient import TestClient

    node1 = _node("Arrays")
    node2 = _node("Stacks")
    u1 = _unit(node1)
    u2 = _unit(node2, prereq_ids=[u1.id])  # u2 depends on u1
    cal = _calendar()
    day = _day(cal, date(2026, 1, 5))
    win = _window(day)
    pv = _plan(cal)
    su = _scheduled(u2, win, pv)

    session = FakeSession({
        CurriculumNode: [node1, node2],
        TeachingUnit: [u1, u2],
        AcademicCalendar: [cal],
        CalendarDay: [day],
        InstructionWindow: [win],
        PlanVersion: [pv],
        ScheduledUnit: [su],
    })

    client = TestClient(_test_app(session))
    resp = client.get(f"/planning/plans/{pv.id}/units/{u2.id}/justification")
    assert resp.status_code == 200
    data = resp.json()
    assert data["node_label"] == "Stacks"
    assert data["syllabus_ref"] == "CS201.2.1"
    assert data["date"] == "2026-01-05"
    assert data["scheduled_minutes"] == 60
    assert len(data["prerequisites"]) == 1
    assert data["prerequisites"][0]["node_label"] == "Arrays"


async def test_justification_calculates_days_to_term_end():
    from starlette.testclient import TestClient

    node = _node("Trees")
    u = _unit(node)
    cal = _calendar()
    day = _day(cal, date(2026, 2, 15))  # 13 days before term_end (Feb 28)
    win = _window(day)
    pv = _plan(cal)
    su = _scheduled(u, win, pv)

    session = FakeSession({
        CurriculumNode: [node],
        TeachingUnit: [u],
        AcademicCalendar: [cal],
        CalendarDay: [day],
        InstructionWindow: [win],
        PlanVersion: [pv],
        ScheduledUnit: [su],
    })

    client = TestClient(_test_app(session))
    resp = client.get(f"/planning/plans/{pv.id}/units/{u.id}/justification")
    assert resp.status_code == 200
    data = resp.json()
    assert data["days_to_term_end"] == 13
    assert data["total_days_in_term"] == 54  # Jan 5 to Feb 28


async def test_justification_404_for_unknown_unit():
    from starlette.testclient import TestClient

    session = FakeSession({})
    client = TestClient(_test_app(session))
    resp = client.get(
        f"/planning/plans/{uuid.uuid4()}/units/{uuid.uuid4()}/justification"
    )
    assert resp.status_code == 404
