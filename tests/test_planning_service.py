"""Service-level tests for app/planning/service.py.

Exercises the real DB query helpers (load_units, load_windows,
previous_assignment) against a FakeSession with canned rows, verifying
that the planning service correctly reads from and writes to the session
during orchestration.
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
    ScheduledUnit,
    ScheduledUnitStatus,
    TeachingUnit,
)
from app.planning.service import (
    PlanningService,
    _load_units,
    _load_windows,
    _previous_assignment,
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


def _unit(node, minutes=60, priority=0.5):
    return TeachingUnit(
        id=uuid.uuid4(),
        node_id=node.id,
        duration_minutes=minutes,
        splittable=False,
        priority=priority,
    )


def _calendar():
    return AcademicCalendar(
        id=uuid.uuid4(),
        school_id="test-school",
        term_start=date(2026, 1, 5),
        term_end=date(2026, 2, 28),
    )


def _day(cal, dt, day_type=DayType.SCHOOL_DAY):
    return CalendarDay(
        id=uuid.uuid4(),
        calendar_id=cal.id,
        date=dt,
        day_type=day_type,
    )


def _window(day, subject="Data Structures", class_id="CS-4A"):
    return InstructionWindow(
        id=uuid.uuid4(),
        calendar_day_id=day.id,
        subject=subject,
        class_id=class_id,
        start_time=time(9, 0),
        end_time=time(10, 0),
        available_minutes=60,
        is_available=True,
    )


# ── _load_units ───────────────────────────────────────────────────────


async def test_load_units_returns_matching_teaching_units():
    node1 = _node("Arrays")
    node2 = _node("Stacks")
    u1 = _unit(node1)
    u2 = _unit(node2)
    u3 = _unit(_node("Trees"))  # not requested

    session = FakeSession({TeachingUnit: [u1, u2, u3]})
    result = await _load_units(session, [node1.id, node2.id])

    ids = {u.id for u in result}
    assert u1.id in ids
    assert u2.id in ids
    assert u3.id not in ids


async def test_load_units_returns_empty_for_no_match():
    session = FakeSession({TeachingUnit: []})
    result = await _load_units(session, [uuid.uuid4()])
    assert result == []


# ── _load_windows ─────────────────────────────────────────────────────


async def test_load_windows_returns_matching_windows():
    cal = _calendar()
    day1 = _day(cal, date(2026, 1, 5))
    day2 = _day(cal, date(2026, 1, 7))
    win1 = _window(day1, subject="Data Structures", class_id="CS-4A")
    win2 = _window(day2, subject="Physics", class_id="CS-4A")  # different subject
    win3 = _window(day1, subject="Data Structures", class_id="CS-5B")  # different class

    session = FakeSession({
        InstructionWindow: [win1, win2, win3],
        CalendarDay: [day1, day2],
    })
    result = await _load_windows(session, cal.id, "Data Structures", "CS-4A")

    # Should only match win1 (same calendar, subject, and class)
    assert len(result) == 1
    assert result[0][0].id == win1.id


async def test_load_windows_returns_empty_for_no_match():
    cal = _calendar()
    session = FakeSession({InstructionWindow: [], CalendarDay: []})
    result = await _load_windows(session, cal.id, "Data Structures", "CS-4A")
    assert result == []


# ── _previous_assignment ──────────────────────────────────────────────


async def test_previous_assignment_returns_empty_for_none_version():
    session = FakeSession({})
    result = await _previous_assignment(session, None)
    assert result == {}


async def test_previous_assignment_returns_unit_to_window_mapping():
    parent_id = uuid.uuid4()
    unit1 = uuid.uuid4()
    unit2 = uuid.uuid4()
    win1 = uuid.uuid4()
    win2 = uuid.uuid4()

    su1 = ScheduledUnit(
        id=uuid.uuid4(), unit_id=unit1, instruction_window_id=win1,
        scheduled_minutes=60, status=ScheduledUnitStatus.PLANNED,
        plan_version=parent_id,
    )
    su2 = ScheduledUnit(
        id=uuid.uuid4(), unit_id=unit2, instruction_window_id=win2,
        scheduled_minutes=60, status=ScheduledUnitStatus.PLANNED,
        plan_version=parent_id,
    )

    session = FakeSession({ScheduledUnit: [su1, su2]})
    result = await _previous_assignment(session, parent_id)

    assert result[unit1] == win1
    assert result[unit2] == win2


# ── build_plan full orchestration ─────────────────────────────────────


async def test_build_plan_persists_plan_version_and_scheduled_units():
    node1 = _node("Arrays")
    node2 = _node("Stacks")
    u1 = _unit(node1)
    u2 = _unit(node2)
    cal = _calendar()
    day1 = _day(cal, date(2026, 1, 5))
    day2 = _day(cal, date(2026, 1, 7))
    win1 = _window(day1)
    win2 = _window(day2)

    session = FakeSession({
        TeachingUnit: [u1, u2],
        CalendarDay: [day1, day2],
        InstructionWindow: [win1, win2],
    })

    service = PlanningService(session)
    plan_version, result = await service.build_plan(
        calendar_id=cal.id,
        subject="Data Structures",
        class_id="CS-4A",
        node_ids=[node1.id, node2.id],
        trigger_reason="initial_plan",
    )

    assert plan_version is not None
    assert plan_version.trigger_reason == "initial_plan"
    assert plan_version.calendar_id == cal.id
    assert result.status in ("optimal", "feasible")
    assert len(result.assignments) == 2
    assert session.committed

    # Verify scheduled units were persisted
    scheduled = [obj for obj in session.added if isinstance(obj, ScheduledUnit)]
    assert len(scheduled) == 2
    for su in scheduled:
        assert su.status == ScheduledUnitStatus.PLANNED
        assert su.plan_version == plan_version.id


async def test_build_plan_replan_links_parent_version():
    node = _node("Arrays")
    u = _unit(node)
    cal = _calendar()
    day = _day(cal, date(2026, 1, 5))
    win = _window(day)
    parent_id = uuid.uuid4()

    session = FakeSession({
        TeachingUnit: [u],
        CalendarDay: [day],
        InstructionWindow: [win],
    })

    service = PlanningService(session)
    plan_version, _ = await service.build_plan(
        calendar_id=cal.id,
        subject="Data Structures",
        class_id="CS-4A",
        node_ids=[node.id],
        trigger_reason="calendar_disruption",
        parent_version_id=parent_id,
    )

    assert plan_version.parent_version_id == parent_id
    assert plan_version.trigger_reason == "calendar_disruption"
