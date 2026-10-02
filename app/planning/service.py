"""Wires the pure CP-SAT scheduler (app/planning/scheduler.py) to
teaching_units / instruction_windows / scheduled_units / plan_versions.
Same split as app/mapping/mapper.py: pure scoring/solving in one module,
DB orchestration in this one.
"""

import asyncio
import json
import math
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import (
    CalendarDay,
    CurriculumEdge,
    DayType,
    EdgeType,
    InstructionWindow,
    PlanVersion,
    ScheduledUnit,
    ScheduledUnitStatus,
    TeachingUnit,
)
from app.emphasis.service import HistoricalAssessmentEmphasisService
from app.planning.scheduler import (
    Assignment,
    ScheduleResult,
    UnitInput,
    WindowInput,
    solve_schedule,
)


@dataclass(frozen=True)
class ScheduledUnitSnapshot:
    unit_id: UUID
    node_label: str
    date: date
    scheduled_minutes: int
    status: str
    window_id: UUID | None = None


@dataclass(frozen=True)
class PlanDiffItem:
    unit_id: UUID
    node_label: str
    previous_date: date | None
    current_date: date | None
    previous_minutes: int | None
    current_minutes: int | None
    change_type: str


def diff_schedules(
    previous: list[ScheduledUnitSnapshot],
    current: list[ScheduledUnitSnapshot],
) -> list[PlanDiffItem]:
    """Compare two plan versions at teaching-unit granularity."""

    def aggregate(items):
        grouped = defaultdict(list)
        for item in items:
            grouped[item.unit_id].append(item)
        return {
            uid: ScheduledUnitSnapshot(
                uid,
                rows[0].node_label,
                min(r.date for r in rows),
                sum(r.scheduled_minutes for r in rows),
                rows[0].status,
            )
            for uid, rows in grouped.items()
        }

    previous_by_unit = aggregate(previous)
    current_by_unit = aggregate(current)
    previous_dates = {
        uid: sorted(r.date for r in previous if r.unit_id == uid) for uid in previous_by_unit
    }
    current_dates = {
        uid: sorted(r.date for r in current if r.unit_id == uid) for uid in current_by_unit
    }

    def sessions(items, uid):
        return sorted(
            (r.date, str(r.window_id or ""), r.scheduled_minutes) for r in items if r.unit_id == uid
        )

    unit_ids = set(previous_by_unit) | set(current_by_unit)

    diff: list[PlanDiffItem] = []
    for unit_id in unit_ids:
        old = previous_by_unit.get(unit_id)
        new = current_by_unit.get(unit_id)
        if old is None and new is not None:
            change_type = "added"
        elif old is not None and new is None:
            change_type = "removed"
        elif (
            old is not None
            and new is not None
            and old.date == new.date
            and previous_dates[unit_id] == current_dates[unit_id]
            and sessions(previous, unit_id) == sessions(current, unit_id)
            and old.scheduled_minutes == new.scheduled_minutes
        ):
            change_type = "unchanged"
        elif old is not None and new is not None and old.scheduled_minutes != new.scheduled_minutes:
            change_type = (
                "compressed" if new.scheduled_minutes < old.scheduled_minutes else "expanded"
            )
        else:
            change_type = "moved"

        if new is not None:
            label = new.node_label
        else:
            assert old is not None  # guaranteed by the elif chain
            label = old.node_label
        diff.append(
            PlanDiffItem(
                unit_id=unit_id,
                node_label=label,
                previous_date=None if old is None else old.date,
                current_date=None if new is None else new.date,
                previous_minutes=None if old is None else old.scheduled_minutes,
                current_minutes=None if new is None else new.scheduled_minutes,
                change_type=change_type,
            )
        )

    return sorted(
        diff,
        key=lambda item: (
            item.current_date or item.previous_date or date.max,
            item.node_label.lower(),
        ),
    )


async def _load_units(session: AsyncSession, node_ids: list[UUID]) -> list[TeachingUnit]:
    result = await session.execute(select(TeachingUnit).where(TeachingUnit.node_id.in_(node_ids)))
    return list(result.scalars().all())


async def _load_windows(
    session: AsyncSession, calendar_id: UUID, subject: str, class_id: str
) -> list[tuple[InstructionWindow, CalendarDay]]:
    result = await session.execute(
        select(InstructionWindow, CalendarDay)
        .join(CalendarDay, CalendarDay.id == InstructionWindow.calendar_day_id)
        .where(
            CalendarDay.calendar_id == calendar_id,
            InstructionWindow.subject == subject,
            InstructionWindow.class_id == class_id,
        )
    )
    return list(result.all())  # type: ignore[arg-type]  # SQLAlchemy Result.all() is a Sequence


async def _previous_assignment(
    session: AsyncSession, parent_version_id: UUID | None
) -> dict[UUID, UUID]:
    if parent_version_id is None:
        return {}
    result = await session.execute(
        select(ScheduledUnit).where(ScheduledUnit.plan_version == parent_version_id)
    )
    return {row.unit_id: row.instruction_window_id for row in result.scalars().all()}


async def load_solver_inputs(
    session, calendar_id, subject, class_id, node_ids, minimum_duration_ratio=1
):
    teaching_units = await _load_units(session, node_ids)
    window_rows = await _load_windows(session, calendar_id, subject, class_id)
    emphasis = {
        r.node_id: r.score for r in await HistoricalAssessmentEmphasisService(session).calculate()
    }
    edge_rows = (
        (
            await session.execute(
                select(CurriculumEdge).where(CurriculumEdge.edge_type == EdgeType.PREREQUISITE)
            )
        )
        .scalars()
        .all()
    )
    all_units = (await session.execute(select(TeachingUnit))).scalars().all()
    by_node = defaultdict(list)
    for unit in all_units:
        by_node[unit.node_id].append(unit.id)
    prerequisites = defaultdict(set)
    for edge in edge_rows:
        for target in by_node[edge.target_node_id]:
            prerequisites[target].update(by_node[edge.source_node_id] or [edge.source_node_id])
    exam_days = (
        (
            await session.execute(
                select(CalendarDay).where(
                    CalendarDay.calendar_id == calendar_id, CalendarDay.day_type == DayType.EXAM_DAY
                )
            )
        )
        .scalars()
        .all()
    )
    deadline = min((d.date for d in exam_days), default=None)
    if deadline:
        deadline -= timedelta(days=1)
    units = [
        UnitInput(
            u.id,
            u.duration_minutes,
            emphasis.get(u.node_id, u.priority),
            tuple({UUID(str(p)) for p in (u.prerequisite_unit_ids or ())} | prerequisites[u.id]),
            deadline=deadline,
            minimum_duration_minutes=max(1, math.ceil(u.duration_minutes * minimum_duration_ratio)),
            splittable=bool(u.splittable),
            minimum_session_minutes=u.minimum_session_minutes or 15,
        )
        for u in teaching_units
    ]
    windows = [
        WindowInput(
            w.id,
            day.date,
            w.available_minutes,
            w.is_available and day.day_type == DayType.SCHOOL_DAY,
        )
        for w, day in window_rows
    ]
    return units, windows


def preserve_taught_sessions(units, windows, prior_rows):
    """Restore historical slots and freeze completed objectives for every solve."""
    taught_rows = [row for row in prior_rows if row.status == ScheduledUnitStatus.TAUGHT]
    taught_window_ids = {row.instruction_window_id for row in taught_rows}
    windows = [
        replace(w, is_available=True) if w.window_id in taught_window_ids else w for w in windows
    ]
    window_dates = {w.window_id: w.date for w in windows}
    locked = tuple(
        Assignment(
            row.unit_id,
            row.instruction_window_id,
            window_dates[row.instruction_window_id],
            row.scheduled_minutes,
        )
        for row in taught_rows
        if row.instruction_window_id in window_dates
    )
    if len(locked) != len(taught_rows):
        from app.planning.scheduler import InfeasibleScheduleError

        raise InfeasibleScheduleError(
            "A taught session belongs to a different subject or class timetable"
        )
    # A completed, shortened objective must not acquire new sessions on replan.
    completed = {
        u.unit_id
        for u in units
        if any(r.unit_id == u.unit_id for r in prior_rows)
        and all(
            r.status == ScheduledUnitStatus.TAUGHT for r in prior_rows if r.unit_id == u.unit_id
        )
    }
    completed_minutes = {
        uid: sum(r.scheduled_minutes for r in taught_rows if r.unit_id == uid) for uid in completed
    }
    units = [
        replace(
            u,
            duration_minutes=completed_minutes[u.unit_id],
            minimum_duration_minutes=completed_minutes[u.unit_id],
        )
        if u.unit_id in completed
        else u
        for u in units
    ]
    return units, windows, locked


class PlanningService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def build_plan(
        self,
        *,
        calendar_id: UUID,
        subject: str,
        class_id: str,
        node_ids: list[UUID],
        trigger_reason: str = "initial_plan",
        parent_version_id: UUID | None = None,
        time_limit_seconds: float = 30.0,
        coverage_preference: float = 0.5,
        minimum_duration_ratio: float = 1.0,
        persist: bool = True,
        commit: bool = True,
    ) -> tuple[PlanVersion, ScheduleResult]:
        """Solve a term plan for the given teaching units and persist it as
        a new PlanVersion + its ScheduledUnit rows. `parent_version_id` set
        means this is a replan: churn is measured against whatever that
        version already had scheduled (02_ARCHITECTURE.md's "minimize plan
        instability" requirement), not against a fresh empty plan.
        """
        previous = await _previous_assignment(self._session, parent_version_id)
        previous_sessions = defaultdict(list)
        previous_minutes = {}
        taught_rows = []
        prior_rows: list[ScheduledUnit] = []
        if parent_version_id:
            rows = await self._session.execute(
                select(ScheduledUnit).where(ScheduledUnit.plan_version == parent_version_id)
            )
            prior_rows = list(rows.scalars().all())
            for row in prior_rows:
                previous_sessions[row.unit_id].append(row.instruction_window_id)
                previous_minutes[row.unit_id, row.instruction_window_id] = row.scheduled_minutes
                if row.status == ScheduledUnitStatus.TAUGHT:
                    taught_rows.append(row)
        units, windows = await load_solver_inputs(
            self._session, calendar_id, subject, class_id, node_ids, minimum_duration_ratio
        )
        units, windows, locked = preserve_taught_sessions(units, windows, prior_rows)

        result = await asyncio.to_thread(
            solve_schedule,
            units,
            windows,
            previous_assignment=previous,
            previous_sessions={uid: tuple(ids) for uid, ids in previous_sessions.items()},
            time_limit_seconds=time_limit_seconds,
            coverage_preference=coverage_preference,
            previous_minutes=previous_minutes,
            locked_assignments=locked,
        )

        plan_version = PlanVersion(
            calendar_id=calendar_id,
            parent_version_id=parent_version_id,
            trigger_reason=trigger_reason,
            notes=json.dumps(
                {
                    "metrics": {k: v for k, v in result.__dict__.items() if k != "assignments"},
                    "context": {
                        "subject": subject,
                        "class_id": class_id,
                        "minimum_duration_ratio": minimum_duration_ratio,
                        "coverage_preference": coverage_preference,
                        "node_ids": [str(n) for n in node_ids],
                    },
                },
                default=str,
            ),
        )
        if not persist:
            return plan_version, result
        self._session.add(plan_version)
        await self._session.flush()  # need plan_version.id for the rows below

        unit_duration = {u.unit_id: u.duration_minutes for u in units}
        for assignment in result.assignments:
            self._session.add(
                ScheduledUnit(
                    unit_id=assignment.unit_id,
                    instruction_window_id=assignment.window_id,
                    scheduled_minutes=assignment.scheduled_minutes
                    or unit_duration[assignment.unit_id],
                    status=(
                        ScheduledUnitStatus.TAUGHT
                        if (assignment.unit_id, assignment.window_id)
                        in {(r.unit_id, r.instruction_window_id) for r in taught_rows}
                        else ScheduledUnitStatus.COMPRESSED
                        if sum(
                            a.scheduled_minutes or 0
                            for a in result.assignments
                            if a.unit_id == assignment.unit_id
                        )
                        < unit_duration[assignment.unit_id]
                        else ScheduledUnitStatus.MOVED
                        if assignment.unit_id in previous
                        and assignment.window_id not in previous_sessions[assignment.unit_id]
                        else ScheduledUnitStatus.PLANNED
                    ),
                    plan_version=plan_version.id,
                )
            )

        if commit:
            await self._session.commit()
        else:
            await self._session.flush()
        return plan_version, result
