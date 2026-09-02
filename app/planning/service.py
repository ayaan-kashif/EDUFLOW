"""Wires the pure CP-SAT scheduler (app/planning/scheduler.py) to
teaching_units / instruction_windows / scheduled_units / plan_versions.
Same split as app/mapping/mapper.py: pure scoring/solving in one module,
DB orchestration in this one.
"""

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import (
    CalendarDay,
    InstructionWindow,
    PlanVersion,
    ScheduledUnit,
    ScheduledUnitStatus,
    TeachingUnit,
)
from app.planning.scheduler import Assignment, ScheduleResult, UnitInput, WindowInput, solve_schedule


@dataclass(frozen=True)
class ScheduledUnitSnapshot:
    unit_id: UUID
    node_label: str
    date: date
    scheduled_minutes: int
    status: str


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
    previous_by_unit = {item.unit_id: item for item in previous}
    current_by_unit = {item.unit_id: item for item in current}
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
            and old.scheduled_minutes == new.scheduled_minutes
        ):
            change_type = "unchanged"
        elif old is not None and new is not None and old.scheduled_minutes != new.scheduled_minutes:
            change_type = "compressed" if new.scheduled_minutes < old.scheduled_minutes else "expanded"
        else:
            change_type = "moved"

        label = new.node_label if new is not None else old.node_label
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
    return list(result.all())


async def _previous_assignment(
    session: AsyncSession, parent_version_id: UUID | None
) -> dict[UUID, UUID]:
    if parent_version_id is None:
        return {}
    result = await session.execute(
        select(ScheduledUnit).where(ScheduledUnit.plan_version == parent_version_id)
    )
    return {row.unit_id: row.instruction_window_id for row in result.scalars().all()}


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
    ) -> tuple[PlanVersion, ScheduleResult]:
        """Solve a term plan for the given teaching units and persist it as
        a new PlanVersion + its ScheduledUnit rows. `parent_version_id` set
        means this is a replan: churn is measured against whatever that
        version already had scheduled (02_ARCHITECTURE.md's "minimize plan
        instability" requirement), not against a fresh empty plan.
        """
        teaching_units = await _load_units(self._session, node_ids)
        window_rows = await _load_windows(self._session, calendar_id, subject, class_id)
        previous = await _previous_assignment(self._session, parent_version_id)

        units = [
            UnitInput(
                unit_id=u.id,
                duration_minutes=u.duration_minutes,
                priority=u.priority,
                prerequisite_unit_ids=tuple(u.prerequisite_unit_ids or ()),
            )
            for u in teaching_units
        ]
        windows = [
            WindowInput(
                window_id=w.id,
                date=day.date,
                available_minutes=w.available_minutes,
                is_available=w.is_available,
            )
            for w, day in window_rows
        ]

        result = solve_schedule(
            units, windows, previous_assignment=previous, time_limit_seconds=time_limit_seconds
        )

        plan_version = PlanVersion(
            calendar_id=calendar_id,
            parent_version_id=parent_version_id,
            trigger_reason=trigger_reason,
        )
        self._session.add(plan_version)
        await self._session.flush()  # need plan_version.id for the rows below

        unit_duration = {u.unit_id: u.duration_minutes for u in units}
        for assignment in result.assignments:
            self._session.add(
                ScheduledUnit(
                    unit_id=assignment.unit_id,
                    instruction_window_id=assignment.window_id,
                    scheduled_minutes=unit_duration[assignment.unit_id],
                    status=ScheduledUnitStatus.PLANNED,
                    plan_version=plan_version.id,
                )
            )

        await self._session.commit()
        return plan_version, result
