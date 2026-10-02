"""Term-plan build/replan endpoint. Thin wrapper over
app/planning/service.py — see that module and app/planning/scheduler.py
for the actual solve logic.
"""

import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.domain.models import (
    AcademicCalendar,
    CalendarDay,
    CurriculumNode,
    InstructionWindow,
    PlanVersion,
    ScheduledUnit,
    ScheduledUnitStatus,
    TeachingUnit,
)
from app.planning.service import PlanningService, ScheduledUnitSnapshot, diff_schedules

router = APIRouter(prefix="/planning", tags=["planning"])


class BuildPlanRequest(BaseModel):
    calendar_id: UUID
    subject: str = Field(min_length=1, max_length=120)
    class_id: str = Field(min_length=1, max_length=120)
    node_ids: list[UUID] = Field(min_length=1, max_length=100)
    trigger_reason: str = Field(default="initial_plan", max_length=1000)
    parent_version_id: UUID | None = None
    coverage_preference: float = Field(default=0.5, ge=0, le=1)
    minimum_duration_ratio: float = Field(default=1.0, ge=0.5, le=1)


class AssignmentOut(BaseModel):
    unit_id: UUID
    window_id: UUID
    date: datetime.date
    scheduled_minutes: int | None = None


class PlanOut(BaseModel):
    plan_version_id: UUID
    status: str
    assignments: list[AssignmentOut]
    unscheduled_unit_ids: list[UUID]
    unchanged_count: int
    moved_count: int
    shortened_count: int = 0
    solve_time_ms: float = 0
    weighted_coverage: float = 0
    explanations: dict[str, str] = {}
    conflict_unit_ids: list[UUID] = []


@router.post("/plans", response_model=PlanOut)
async def build_plan(
    body: BuildPlanRequest, session: AsyncSession = Depends(get_session)
) -> PlanOut:
    calendar = await session.get(AcademicCalendar, body.calendar_id)
    if calendar is None:
        raise HTTPException(404, 'Calendar not found')
    if body.parent_version_id:
        parent = await session.get(PlanVersion,body.parent_version_id)
        if parent is None or parent.calendar_id != body.calendar_id:
            raise HTTPException(422,'Parent plan must belong to the selected calendar')
    plan_version, result = await PlanningService(session).build_plan(
        calendar_id=body.calendar_id,
        subject=body.subject,
        class_id=body.class_id,
        node_ids=body.node_ids,
        trigger_reason=body.trigger_reason,
        parent_version_id=body.parent_version_id,
        coverage_preference=body.coverage_preference,
        minimum_duration_ratio=body.minimum_duration_ratio,
    )
    return PlanOut(
        plan_version_id=plan_version.id,
        status=result.status,
        assignments=[
            AssignmentOut(unit_id=a.unit_id, window_id=a.window_id, date=a.date,
                          scheduled_minutes=a.scheduled_minutes)
            for a in result.assignments
        ],
        unscheduled_unit_ids=result.unscheduled_unit_ids,
        unchanged_count=result.unchanged_count,
        moved_count=result.moved_count,
        shortened_count=result.shortened_count,
        solve_time_ms=result.solve_time_ms,
        weighted_coverage=result.weighted_coverage,
        explanations=result.explanations,
        conflict_unit_ids=result.conflict_unit_ids,
    )


@router.post('/plans/{plan_id}/sessions/{session_id}/taught')
async def mark_taught(plan_id: UUID,session_id: UUID,session: AsyncSession=Depends(get_session)):
    row = await session.get(ScheduledUnit,session_id)
    if row is None or row.plan_version != plan_id:
        raise HTTPException(404,'Scheduled session not found in this plan')
    row.status = ScheduledUnitStatus.TAUGHT
    await session.commit()
    return {'id':row.id,'status':'taught'}


class PlanVersionOut(BaseModel):
    id: UUID
    created_at: datetime.datetime
    calendar_id: UUID
    parent_version_id: UUID | None
    trigger_reason: str
    scheduled_count: int


@router.get("/plans", response_model=list[PlanVersionOut])
async def list_plans(session: AsyncSession = Depends(get_session)) -> list[PlanVersionOut]:
    """Newest first. The workspace remembers the plan it built in browser
    storage, but a fresh browser has none — this is how it finds the plans
    that already exist rather than making the user rebuild one.
    """
    raw_counts = (
        await session.execute(
            select(ScheduledUnit.plan_version, func.count()).group_by(ScheduledUnit.plan_version)
        )
    ).all()
    counts: dict[UUID, int] = {row[0]: row[1] for row in raw_counts}
    versions = (
        (await session.execute(select(PlanVersion).order_by(PlanVersion.created_at.desc())))
        .scalars()
        .all()
    )
    return [
        PlanVersionOut(
            id=v.id, created_at=v.created_at, calendar_id=v.calendar_id, parent_version_id=v.parent_version_id,
            trigger_reason=v.trigger_reason, scheduled_count=counts.get(v.id, 0),
        )
        for v in versions
    ]


class ScheduledUnitOut(BaseModel):
    id: UUID
    node_label: str
    date: datetime.date
    scheduled_minutes: int
    status: str
    teaching_unit_id: UUID | None = None
    node_id: UUID | None = None
    priority: float = 0
    start_time: datetime.time | None = None


async def _scheduled_snapshots(
    session: AsyncSession, plan_version_id: UUID
) -> list[ScheduledUnitSnapshot]:
    rows = (
        await session.execute(
            select(ScheduledUnit, TeachingUnit, CurriculumNode, InstructionWindow, CalendarDay)
            .join(TeachingUnit, TeachingUnit.id == ScheduledUnit.unit_id)
            .join(CurriculumNode, CurriculumNode.id == TeachingUnit.node_id)
            .join(InstructionWindow, InstructionWindow.id == ScheduledUnit.instruction_window_id)
            .join(CalendarDay, CalendarDay.id == InstructionWindow.calendar_day_id)
            .where(ScheduledUnit.plan_version == plan_version_id)
            .order_by(CalendarDay.date)
        )
    ).all()
    return [
        ScheduledUnitSnapshot(
            unit_id=su.unit_id,
            node_label=node.label,
            date=day.date,
            scheduled_minutes=su.scheduled_minutes,
            status=su.status.value,
            window_id=su.instruction_window_id,
        )
        for su, _, node, _, day in rows
    ]


@router.get("/plans/{plan_version_id}", response_model=list[ScheduledUnitOut])
async def get_plan(
    plan_version_id: UUID, session: AsyncSession = Depends(get_session)
) -> list[ScheduledUnitOut]:
    """The scheduled units for one plan version, for the "click a lesson,
    see why it's there" workspace view (06_MVP_SCOPE_AND_DEMO.md) — this
    endpoint gives the date/status; app/generation/ supplies the
    citations/justification once a lesson is generated for a unit.
    """
    rows = (
        await session.execute(
            select(ScheduledUnit, TeachingUnit, CurriculumNode, InstructionWindow, CalendarDay)
            .join(TeachingUnit, TeachingUnit.id == ScheduledUnit.unit_id)
            .join(CurriculumNode, CurriculumNode.id == TeachingUnit.node_id)
            .join(InstructionWindow, InstructionWindow.id == ScheduledUnit.instruction_window_id)
            .join(CalendarDay, CalendarDay.id == InstructionWindow.calendar_day_id)
            .where(ScheduledUnit.plan_version == plan_version_id)
            .order_by(CalendarDay.date)
        )
    ).all()
    if not rows and await session.get(PlanVersion,plan_version_id) is None:
        raise HTTPException(status_code=404, detail="plan_version not found")
    return [
        ScheduledUnitOut(id=su.id, node_label=node.label, date=day.date,
                         scheduled_minutes=su.scheduled_minutes, status=su.status.value,
                         teaching_unit_id=tu.id, node_id=node.id, priority=tu.priority,
                         start_time=win.start_time)
        for su, tu, node, win, day in rows
    ]


class PlanDiffOut(BaseModel):
    unit_id: UUID
    node_label: str
    previous_date: datetime.date | None
    current_date: datetime.date | None
    previous_minutes: int | None
    current_minutes: int | None
    change_type: str


@router.get("/plans/{plan_version_id}/diff", response_model=list[PlanDiffOut])
async def get_plan_diff(
    plan_version_id: UUID,
    base_plan_version_id: UUID | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[PlanDiffOut]:
    plan = await session.get(PlanVersion, plan_version_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="plan_version not found")

    base_id = base_plan_version_id or plan.parent_version_id
    if base_id is None:
        raise HTTPException(
            status_code=400,
            detail="base_plan_version_id required: plan has no parent_version_id",
        )

    base = await session.get(PlanVersion, base_id)
    if base is None:
        raise HTTPException(status_code=404, detail="base plan_version not found")

    return [
        PlanDiffOut(**item.__dict__)
        for item in diff_schedules(
            await _scheduled_snapshots(session, base_id),
            await _scheduled_snapshots(session, plan_version_id),
        )
    ]


# ── Justification ─────────────────────────────────────────────────────


class SourcePageOut(BaseModel):
    document_title: str
    doc_type: str
    page: int
    excerpt: str


class PrerequisiteOut(BaseModel):
    node_id: UUID
    node_label: str


class JustificationOut(BaseModel):
    unit_id: UUID
    node_id: UUID
    node_label: str
    node_description: str | None
    syllabus_ref: str | None
    date: datetime.date
    scheduled_minutes: int
    # Prerequisites that must come before this lesson
    prerequisites: list[PrerequisiteOut]
    # Assessment emphasis breakdown
    emphasis_score: float | None
    emphasis_frequency: float | None
    emphasis_recency: float | None
    emphasis_marks: float | None
    emphasis_syllabus: float | None
    emphasis_structural: float | None
    # Source pages: where the objective's content comes from
    source_pages: list[SourcePageOut]
    # Time context
    days_to_term_end: int | None
    total_days_in_term: int | None
    # Churn context (replan only)
    was_moved: bool
    previous_date: datetime.date | None


@router.get(
    "/plans/{plan_version_id}/units/{unit_id}/justification",
    response_model=JustificationOut,
)
async def get_unit_justification(
    plan_version_id: UUID,
    unit_id: UUID,
    scheduled_session_id: UUID | None = None,
    session: AsyncSession = Depends(get_session),
) -> JustificationOut:
    """Why is this lesson scheduled here? Full provenance: prerequisite
    dependency, objective, source pages, emphasis weight, and time-to-exam.
    """

    from app.domain.models import (
        AcademicCalendar,
        CurriculumEdge,
        EdgeType,
        ExamQuestion,
        QuestionNodeMapping,
        QuestionSpan,
        SourceDocument,
        SourceSpan,
        TeachingUnit,
    )

    # 1. Load the scheduled unit with its teaching unit, node, window, and day
    row = (
        await session.execute(
            select(ScheduledUnit, TeachingUnit, CurriculumNode, InstructionWindow, CalendarDay)
            .join(TeachingUnit, TeachingUnit.id == ScheduledUnit.unit_id)
            .join(CurriculumNode, CurriculumNode.id == TeachingUnit.node_id)
            .join(InstructionWindow, InstructionWindow.id == ScheduledUnit.instruction_window_id)
            .join(CalendarDay, CalendarDay.id == InstructionWindow.calendar_day_id)
            .where(
                ScheduledUnit.plan_version == plan_version_id,
                ScheduledUnit.unit_id == unit_id,
                ScheduledUnit.id == scheduled_session_id if scheduled_session_id else ScheduledUnit.id.is_not(None),
            )
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="scheduled unit not found")
    su, tu, node, _win, day = row

    # 2. Load the calendar for term_end
    cal = await session.get(AcademicCalendar, day.calendar_id)
    days_to_term_end = (cal.term_end - day.date).days if cal else None
    total_days = (cal.term_end - cal.term_start).days if cal else None

    # 3. Prerequisites: resolve prerequisite_unit_ids to node labels
    prereqs: list[PrerequisiteOut] = []
    if tu.prerequisite_unit_ids:
        prereq_tu_rows = (
            await session.execute(
                select(TeachingUnit, CurriculumNode)
                .join(CurriculumNode, CurriculumNode.id == TeachingUnit.node_id)
                .where(TeachingUnit.id.in_(tu.prerequisite_unit_ids))
            )
        ).all()
        prereqs = [
            PrerequisiteOut(node_id=p_tu.node_id, node_label=p_node.label)
            for p_tu, p_node in prereq_tu_rows
        ]
    # Also check curriculum edges for prerequisite edges targeting this node
    edge_rows = (
        await session.execute(
            select(CurriculumEdge, CurriculumNode)
            .join(CurriculumNode, CurriculumNode.id == CurriculumEdge.source_node_id)
            .where(
                CurriculumEdge.target_node_id == node.id,
                CurriculumEdge.edge_type == EdgeType.PREREQUISITE,
            )
        )
    ).all()
    existing_prereq_ids = {p.node_id for p in prereqs}
    for edge, prereq_node in edge_rows:
        if prereq_node.id not in existing_prereq_ids:
            prereqs.append(PrerequisiteOut(node_id=prereq_node.id, node_label=prereq_node.label))

    # 4. Use the same normalized scoring service as the solver.
    emphasis_score: float | None = None
    emph_freq = emph_rec = emph_marks = emph_syll = emph_struct = None
    from app.emphasis.service import HistoricalAssessmentEmphasisService
    emphasis = next((r for r in await HistoricalAssessmentEmphasisService(session).calculate()
                     if r.node_id == node.id), None)
    if emphasis:
        emphasis_score = emphasis.score
        emph_freq, emph_rec = emphasis.components.frequency, emphasis.components.recency
        emph_marks = emphasis.components.marks
        emph_syll, emph_struct = emphasis.components.syllabus, emphasis.components.structural

    # 5. Source pages: find spans that cite this objective's content
    source_pages: list[SourcePageOut] = []
    mapping_rows = (
        await session.execute(
            select(QuestionNodeMapping.question_id).where(
                QuestionNodeMapping.node_id == node.id
            ).distinct()
        )
    ).scalars().all()
    if mapping_rows:
        span_rows = (
            await session.execute(
                select(SourceSpan, SourceDocument)
                .join(SourceDocument, SourceDocument.id == SourceSpan.document_id)
                .join(QuestionSpan, QuestionSpan.source_span_id == SourceSpan.id)
                .join(ExamQuestion, ExamQuestion.id == QuestionSpan.question_id)
                .where(ExamQuestion.id.in_(mapping_rows))
                .distinct()
            )
        ).all()
        seen: set[tuple[str, int]] = set()
        for sp, doc in span_rows:
            key = (doc.title, sp.page)
            if key not in seen:
                seen.add(key)
                source_pages.append(
                    SourcePageOut(
                        document_title=doc.title,
                        doc_type=doc.doc_type.value,
                        page=sp.page,
                        excerpt=sp.text[:200],
                    )
                )
    source_pages.sort(key=lambda s: (s.document_title, s.page))

    # 6. Churn context: was this unit moved from a previous plan?
    was_moved = False
    previous_date_val: datetime.date | None = None
    if su.plan_version:
        pv = await session.get(PlanVersion, su.plan_version)
        if pv and pv.parent_version_id:
            prev_su = (
                await session.execute(
                    select(ScheduledUnit, CalendarDay)
                    .join(InstructionWindow, InstructionWindow.id == ScheduledUnit.instruction_window_id)
                    .join(CalendarDay, CalendarDay.id == InstructionWindow.calendar_day_id)
                    .where(
                        ScheduledUnit.plan_version == pv.parent_version_id,
                        ScheduledUnit.unit_id == unit_id,
                    )
                )
            ).first()
            if prev_su:
                _, prev_day = prev_su
                previous_date_val = prev_day.date
                was_moved = prev_day.date != day.date

    return JustificationOut(
        unit_id=su.unit_id,
        node_id=node.id,
        node_label=node.label,
        node_description=node.description,
        syllabus_ref=node.syllabus_ref,
        date=day.date,
        scheduled_minutes=su.scheduled_minutes,
        prerequisites=prereqs,
        emphasis_score=emphasis_score,
        emphasis_frequency=emph_freq,
        emphasis_recency=emph_rec,
        emphasis_marks=emph_marks,
        emphasis_syllabus=emph_syll,
        emphasis_structural=emph_struct,
        source_pages=source_pages,
        days_to_term_end=days_to_term_end,
        total_days_in_term=total_days,
        was_moved=was_moved,
        previous_date=previous_date_val,
    )
