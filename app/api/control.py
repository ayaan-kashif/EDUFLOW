"""Source-to-plan setup, coverage ledger, and review-before-apply recovery."""

import asyncio
import json
import math
from collections import defaultdict
from dataclasses import asdict, replace
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select, update

from app.db import get_session
from app.domain.models import (
    AcademicCalendar,
    CalendarDay,
    Claim,
    CurriculumEdge,
    CurriculumNode,
    DayType,
    InstructionWindow,
    NodeType,
    PlanVersion,
    RecoveryScenario,
    ScheduledUnit,
    ScheduledUnitStatus,
    SourceCurriculum,
    SourceDocument,
    SourceSpan,
    TeachingUnit,
    VerificationStatus,
)
from app.ingestion.curriculum_extraction import source_fingerprint
from app.planning.control import (
    document_nodes,
    encode,
    plan_context,
    previous_sessions,
    recovery_inputs,
)
from app.planning.scheduler import Assignment, solve_schedule, validate_schedule
from app.planning.service import PlanningService, preserve_taught_sessions

router = APIRouter(prefix="/studio", tags=["teacher control room"])


async def require_plan(session, plan_id):
    plan = await session.get(PlanVersion, plan_id)
    if plan is None:
        raise HTTPException(404, "Plan not found")
    return plan


@router.get("/documents/{document_id}/curriculum")
async def curriculum(document_id: UUID, session=Depends(get_session)):
    if await session.get(SourceDocument, document_id) is None:
        raise HTTPException(404, "Source not found")
    nodes, cached = await document_nodes(session, document_id)
    spans = list(
        (
            await session.execute(
                select(SourceSpan)
                .where(SourceSpan.document_id == document_id)
                .order_by(SourceSpan.page, SourceSpan.block_id)
            )
        )
        .scalars()
        .all()
    )
    return {
        "nodes": [
            {
                "id": n.id,
                "label": n.label,
                "node_type": n.node_type.value,
                "syllabus_ref": n.syllabus_ref,
                "confidence": n.confidence,
                "origin": n.origin.value,
            }
            for n in nodes
        ],
        "extraction": cached.metadata_json if cached else {"method": "existing source attribution"},
        "stale": bool(cached and cached.fingerprint != source_fingerprint(spans)),
    }


class SetupRequest(BaseModel):
    document_id: UUID
    node_ids: list[UUID] = Field(min_length=1, max_length=60)
    subject: str = Field(min_length=1, max_length=120)
    class_id: str = Field(min_length=1, max_length=120)
    term_start: date
    term_end: date
    weekdays: list[int] = Field(default=[0, 1, 2, 3, 4], min_length=1, max_length=7)
    start_time: time = time(9)
    session_minutes: int = Field(default=60, ge=20, le=180)
    objective_minutes: int = Field(default=60, ge=20, le=360)
    minimum_duration_ratio: float = Field(default=1, ge=0.5, le=1)

    @model_validator(mode="after")
    def validate_term(self):
        if not 0 <= (self.term_end - self.term_start).days <= 180:
            raise ValueError("Choose a term of at most 181 days")
        if any(d < 0 or d > 6 for d in self.weekdays):
            raise ValueError("Weekdays must be between Monday (0) and Sunday (6)")
        if self.start_time.hour * 60 + self.start_time.minute + self.session_minutes >= 1440:
            raise ValueError("A lesson must finish within the same day")
        return self


@router.post("/setup")
async def setup(body: SetupRequest, session=Depends(get_session)):
    nodes, cached = await document_nodes(session, body.document_id)
    available = {n.id: n for n in nodes if n.node_type == NodeType.OBJECTIVE}
    selected = set(body.node_ids)
    if not selected <= available.keys():
        raise HTTPException(422, "Select learning objectives attributed to this source")
    if cached:
        spans = list(
            (
                await session.execute(
                    select(SourceSpan)
                    .where(SourceSpan.document_id == body.document_id)
                    .order_by(SourceSpan.page, SourceSpan.block_id)
                )
            )
            .scalars()
            .all()
        )
        if cached.fingerprint != source_fingerprint(spans):
            raise HTTPException(
                409, "The source changed. Extract objectives again before planning."
            )
    # Teaching-unit definitions belong to the objective and are reused, not overwritten.
    existing = set(
        (
            await session.execute(
                select(TeachingUnit.node_id).where(TeachingUnit.node_id.in_(selected))
            )
        )
        .scalars()
        .all()
    )
    cal = AcademicCalendar(
        school_id=f"{body.subject} · {body.class_id}",
        term_start=body.term_start,
        term_end=body.term_end,
    )
    session.add(cal)
    await session.flush()
    end_time = (
        datetime.combine(body.term_start, body.start_time) + timedelta(minutes=body.session_minutes)
    ).time()
    window_count = 0
    for offset in range((body.term_end - body.term_start).days + 1):
        d = body.term_start + timedelta(days=offset)
        teaching = d.weekday() in body.weekdays
        day = CalendarDay(
            calendar_id=cal.id,
            date=d,
            day_type=DayType.SCHOOL_DAY if teaching else DayType.NON_TEACHING,
        )
        session.add(day)
        await session.flush()
        if teaching:
            session.add(
                InstructionWindow(
                    calendar_day_id=day.id,
                    subject=body.subject,
                    class_id=body.class_id,
                    start_time=body.start_time,
                    end_time=end_time,
                    available_minutes=body.session_minutes,
                    is_available=True,
                )
            )
            window_count += 1
    if not window_count:
        await session.rollback()
        raise HTTPException(422, "No teaching days match this term")
    for uid in selected - existing:
        session.add(
            TeachingUnit(
                node_id=uid,
                duration_minutes=body.objective_minutes,
                splittable=body.objective_minutes > body.session_minutes,
                minimum_session_minutes=20,
                priority=0.5,
            )
        )
    await session.flush()
    try:
        plan, result = await PlanningService(session).build_plan(
            calendar_id=cal.id,
            subject=body.subject,
            class_id=body.class_id,
            node_ids=list(selected),
            minimum_duration_ratio=body.minimum_duration_ratio,
            trigger_reason="source_to_plan",
            time_limit_seconds=5,
            commit=False,
        )
        if not result.assignments:
            raise HTTPException(
                422, "No objectives fit. Include prerequisites or increase teaching capacity."
            )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return {
        "plan_id": plan.id,
        "calendar_id": cal.id,
        "node_ids": list(selected),
        "subject": body.subject,
        "class_id": body.class_id,
        "reference_date": body.term_start,
        "document_id": body.document_id,
        "windows_created": window_count,
        "reused_objectives": len(existing),
        "metrics": asdict(result),
    }


@router.get("/plans/{plan_id}/coverage")
async def coverage(plan_id: UUID, session=Depends(get_session)):
    plan = await require_plan(session, plan_id)
    context, rows = await plan_context(session, plan)
    node_ids = [UUID(n) for n in context["node_ids"]]
    units = list(
        (await session.execute(select(TeachingUnit).where(TeachingUnit.node_id.in_(node_ids))))
        .scalars()
        .all()
    )
    nodes = {
        n.id: n
        for n in (
            await session.execute(select(CurriculumNode).where(CurriculumNode.id.in_(node_ids)))
        )
        .scalars()
        .all()
    }
    by_unit = defaultdict(list)
    for r in rows:
        by_unit[r.unit_id].append(r)
    sources = defaultdict(set)
    for cache in (await session.execute(select(SourceCurriculum))).scalars().all():
        for uid in cache.node_ids:
            sources[UUID(uid)].add(str(cache.document_id))
    for nid, docid in (
        await session.execute(
            select(CurriculumEdge.source_node_id, SourceSpan.document_id)
            .join(SourceSpan, SourceSpan.id == CurriculumEdge.provenance_id)
            .where(CurriculumEdge.source_node_id.in_(node_ids))
        )
    ).all():
        sources[nid].add(str(docid))
    claims = defaultdict(list)
    for claim in (
        (
            await session.execute(
                select(Claim).where(Claim.scheduled_unit_id.in_([r.id for r in rows]))
            )
        )
        .scalars()
        .all()
    ):
        claims[claim.scheduled_unit_id].append(claim)
    ledger = []
    for unit in units:
        sessions = by_unit[unit.id]
        minutes = sum(r.scheduled_minutes for r in sessions)
        taught = sum(
            r.scheduled_minutes for r in sessions if r.status == ScheduledUnitStatus.TAUGHT
        )
        status = (
            "taught"
            if minutes and taught == minutes
            else "in_progress"
            if taught
            else "planned"
            if minutes
            else "unscheduled"
        )
        verified = sum(
            c.verification_status == VerificationStatus.VERIFIED
            for r in sessions
            for c in claims[r.id]
        )
        ledger.append(
            {
                "node_id": unit.node_id,
                "unit_id": unit.id,
                "label": nodes[unit.node_id].label,
                "reference": nodes[unit.node_id].syllabus_ref,
                "status": status,
                "priority": unit.priority,
                "preferred_minutes": unit.duration_minutes,
                "scheduled_minutes": minutes,
                "taught_minutes": taught,
                "source_ids": sorted(sources[unit.node_id]),
                "verified_claims": verified,
                "session_id": sessions[0].id if sessions else None,
            }
        )
    ledger.sort(
        key=lambda r: (
            {"unscheduled": 0, "in_progress": 1, "planned": 2, "taught": 3}[r["status"]],
            -r["priority"],
            r["label"],
        )
    )
    return {
        "plan_id": plan_id,
        "context": context,
        "objectives": ledger,
        "totals": {
            "objectives": len(ledger),
            "scheduled": sum(r["scheduled_minutes"] > 0 for r in ledger),
            "taught": sum(r["status"] == "taught" for r in ledger),
            "without_sources": sum(not r["source_ids"] for r in ledger),
            "without_verified_claims": sum(r["verified_claims"] == 0 for r in ledger),
            "scheduled_minutes": sum(r["scheduled_minutes"] for r in ledger),
        },
        "note": "Source attribution and verified claims are separate signals; scheduled coverage does not prove learning.",
    }


class CompareRequest(BaseModel):
    dates: list[date] = Field(min_length=1, max_length=20)
    minimum_duration_ratio: float = Field(default=0.75, ge=0.5, le=1)


def strategy_units(units, ratio):
    return [
        replace(u, minimum_duration_minutes=max(1, math.ceil(u.duration_minutes * ratio)))
        for u in units
    ]


@router.post("/plans/{plan_id}/recovery")
async def compare(plan_id: UUID, body: CompareRequest, session=Depends(get_session)):
    plan = await require_plan(session, plan_id)
    _context, rows, units, windows, fingerprint = await recovery_inputs(session, plan)
    closed = set(body.dates)
    available_dates = {w.date for w in windows if w.is_available}
    if not closed <= available_dates:
        raise HTTPException(422, "Every closure must match an available teaching day in this plan")
    dates_by_id = {w.window_id: w.date for w in windows}
    if any(
        r.status == ScheduledUnitStatus.TAUGHT
        and dates_by_id.get(r.instruction_window_id) in closed
        for r in rows
    ):
        raise HTTPException(
            409, "A closure overlaps a taught session. Historical teaching cannot be removed."
        )
    disrupted = [replace(w, is_available=w.is_available and w.date not in closed) for w in windows]
    previous = previous_sessions(rows)
    old_minutes = {(r.unit_id, r.instruction_window_id): r.scheduled_minutes for r in rows}
    labels = {
        u.id: n.label
        for u, n in (
            await session.execute(
                select(TeachingUnit, CurriculumNode)
                .join(CurriculumNode, CurriculumNode.id == TeachingUnit.node_id)
                .where(TeachingUnit.id.in_([u.unit_id for u in units]))
            )
        ).all()
    }
    policies = [
        ("depth", "Protect lesson depth", 1, 0.2),
        ("balanced", "Balance the tradeoffs", max(0.85, body.minimum_duration_ratio), 0.5),
        ("coverage", "Protect curriculum coverage", body.minimum_duration_ratio, 1),
    ]
    options = []
    for key, label, ratio, preference in policies:
        candidate, slots, locked = preserve_taught_sessions(
            strategy_units(units, ratio), disrupted, rows
        )
        result = await asyncio.to_thread(
            solve_schedule,
            candidate,
            slots,
            previous_sessions=previous,
            previous_minutes=old_minutes,
            locked_assignments=locked,
            coverage_preference=preference,
            time_limit_seconds=2,
        )
        current = {(a.unit_id, a.window_id): a.scheduled_minutes for a in result.assignments}
        moved = sum((a.unit_id, a.window_id) not in old_minutes for a in result.assignments)
        omitted = [labels.get(uid, str(uid)) for uid in result.unscheduled_unit_ids]
        options.append(
            {
                "key": key,
                "label": label,
                "ratio": ratio,
                "preference": preference,
                "result": asdict(result),
                "minutes_lost": max(
                    0, sum(r.scheduled_minutes for r in rows) - sum(value or 0 for value in current.values())
                ),
                "moved_sessions": moved,
                "omitted": omitted,
            }
        )
    scenario = RecoveryScenario(
        plan_id=plan.id,
        fingerprint=fingerprint,
        payload=encode({"dates": sorted(closed), "options": options}),
        applied_plan_id=None,
    )
    session.add(scenario)
    await session.commit()
    return {
        "scenario_id": scenario.id,
        "baseline_sessions": len(rows),
        "dates": sorted(closed),
        "options": options,
    }


class ApplyRequest(BaseModel):
    option: str = Field(pattern="^(depth|balanced|coverage)$")


@router.post("/recovery/{scenario_id}/apply")
async def apply_recovery(scenario_id: UUID, body: ApplyRequest, session=Depends(get_session)):
    # Row locks serialize application on PostgreSQL. SQLite serializes the final
    # write transaction; the optimistic fingerprint catches intervening changes.
    scenario = (
        await session.execute(
            select(RecoveryScenario).where(RecoveryScenario.id == scenario_id).with_for_update()
        )
    ).scalar_one_or_none()
    if scenario is None:
        raise HTTPException(404, "Recovery comparison not found")
    if scenario.applied_plan_id:
        if scenario.applied_option != body.option:
            raise HTTPException(409, "This comparison already applied a different strategy")
        return {"plan_id": scenario.applied_plan_id, "reused": True}
    claimed = await session.execute(
        update(RecoveryScenario)
        .where(RecoveryScenario.id == scenario_id, RecoveryScenario.applied_option.is_(None))
        .values(applied_option="pending")
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:
        await session.rollback()
        raise HTTPException(409, "This comparison is being applied. Refresh the current plan.")
    created = (
        scenario.created_at.replace(tzinfo=UTC)
        if scenario.created_at.tzinfo is None
        else scenario.created_at
    )
    if datetime.now(UTC) - created > timedelta(hours=1):
        raise HTTPException(409, "Comparison expired. Compare the current plan again.")
    plan = await require_plan(session, scenario.plan_id)
    context, rows, units, windows, fingerprint = await recovery_inputs(session, plan)
    if fingerprint != scenario.fingerprint:
        raise HTTPException(409, "The plan or timetable changed. Compare again before applying.")
    choice = next(o for o in scenario.payload["options"] if o["key"] == body.option)
    closed = {date.fromisoformat(d) for d in scenario.payload["dates"]}
    candidate, slots, locked = preserve_taught_sessions(
        strategy_units(units, choice["ratio"]),
        [replace(w, is_available=w.is_available and w.date not in closed) for w in windows],
        rows,
    )
    assignments = [
        Assignment(
            UUID(a["unit_id"]),
            UUID(a["window_id"]),
            date.fromisoformat(a["date"]),
            a["scheduled_minutes"],
        )
        for a in choice["result"]["assignments"]
    ]
    if validate_schedule(assignments, candidate, slots) or not set(locked) <= set(assignments):
        raise HTTPException(409, "The reviewed schedule no longer satisfies the constraints")
    days = list(
        (
            await session.execute(
                select(CalendarDay).where(
                    CalendarDay.calendar_id == plan.calendar_id, CalendarDay.date.in_(closed)
                )
            )
        )
        .scalars()
        .all()
    )
    window_rows = list(
        (
            await session.execute(
                select(InstructionWindow).where(
                    InstructionWindow.calendar_day_id.in_([d.id for d in days])
                )
            )
        )
        .scalars()
        .all()
    )
    # Close only this subject/class's slots, not another class sharing the calendar.
    for w in window_rows:
        if w.subject == context["subject"] and w.class_id == context["class_id"]:
            w.is_available = False
    context = {
        **context,
        "minimum_duration_ratio": choice["ratio"],
        "coverage_preference": choice["preference"],
    }
    metrics = {k: v for k, v in choice["result"].items() if k != "assignments"}
    new = PlanVersion(
        calendar_id=plan.calendar_id,
        parent_version_id=plan.id,
        trigger_reason=f"recovery:{body.option}",
        notes=json.dumps(
            {
                "context": context,
                "metrics": metrics,
                "recovery": {"scenario_id": str(scenario.id), "dates": scenario.payload["dates"]},
            }
        ),
    )
    session.add(new)
    await session.flush()
    totals: defaultdict[UUID, int] = defaultdict(int)
    for a in assignments:
        totals[a.unit_id] += a.scheduled_minutes or 0
    original = {u.unit_id: u.duration_minutes for u in units}
    old = {(r.unit_id, r.instruction_window_id): r for r in rows}
    for a in assignments:
        prior = old.get((a.unit_id, a.window_id))
        status = (
            ScheduledUnitStatus.TAUGHT
            if a in locked
            else ScheduledUnitStatus.COMPRESSED
            if totals[a.unit_id] < original[a.unit_id]
            else ScheduledUnitStatus.MOVED
            if prior is None
            else ScheduledUnitStatus.PLANNED
        )
        session.add(
            ScheduledUnit(
                unit_id=a.unit_id,
                instruction_window_id=a.window_id,
                scheduled_minutes=a.scheduled_minutes,
                status=status,
                plan_version=new.id,
            )
        )
    scenario.applied_plan_id = new.id
    scenario.applied_option = body.option
    await session.commit()
    return {"plan_id": new.id, "reused": False}
