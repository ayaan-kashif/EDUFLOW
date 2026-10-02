"""Shared read models and solver inputs for the teacher control room."""

import hashlib
import json
from collections import defaultdict
from dataclasses import asdict
from uuid import UUID

from sqlalchemy import select

from app.domain.models import (
    CurriculumEdge,
    CurriculumNode,
    InstructionWindow,
    PlanVersion,
    ScheduledUnit,
    SourceCurriculum,
    SourceSpan,
    TeachingUnit,
)
from app.planning.service import load_solver_inputs


def encode(value):
    return json.loads(json.dumps(value, default=str))


async def document_nodes(session, document_id):
    cached = await session.get(SourceCurriculum, document_id)
    if cached:
        ids = [UUID(value) for value in cached.node_ids]
    else:
        # Existing manually attributed sources (including the original demo).
        ids = list(
            (
                await session.execute(
                    select(CurriculumEdge.source_node_id)
                    .join(SourceSpan, SourceSpan.id == CurriculumEdge.provenance_id)
                    .where(SourceSpan.document_id == document_id)
                )
            )
            .scalars()
            .all()
        )
    nodes = list(
        (
            await session.execute(
                select(CurriculumNode)
                .where(CurriculumNode.id.in_(ids))
                .order_by(CurriculumNode.created_at, CurriculumNode.label)
            )
        )
        .scalars()
        .all()
    )
    return nodes, cached


async def plan_context(session, plan):
    try:
        context = json.loads(plan.notes or "{}").get("context", {})
    except (TypeError, ValueError):
        context = {}
    rows = list(
        (await session.execute(select(ScheduledUnit).where(ScheduledUnit.plan_version == plan.id)))
        .scalars()
        .all()
    )
    if not context.get("node_ids"):
        context["node_ids"] = [
            str(n)
            for n in (
                await session.execute(
                    select(TeachingUnit.node_id).where(
                        TeachingUnit.id.in_([r.unit_id for r in rows])
                    )
                )
            )
            .scalars()
            .all()
        ]
        context["legacy_scope"] = True
    context["calendar_id"] = str(plan.calendar_id)
    return context, rows


async def recovery_inputs(session, plan):
    context, rows = await plan_context(session, plan)
    units, windows = await load_solver_inputs(
        session,
        plan.calendar_id,
        context.get("subject", ""),
        context.get("class_id", ""),
        [UUID(n) for n in context["node_ids"]],
        1,
    )
    children = list(
        (
            await session.execute(
                select(PlanVersion.id).where(PlanVersion.parent_version_id == plan.id)
            )
        )
        .scalars()
        .all()
    )
    clocks = list(
        (
            await session.execute(
                select(
                    InstructionWindow.id, InstructionWindow.start_time, InstructionWindow.end_time
                ).where(InstructionWindow.id.in_([w.window_id for w in windows]))
            )
        ).all()
    )
    data = {
        "clock_times": sorted(tuple(str(value) for value in row) for row in clocks),
        "units": sorted([asdict(u) for u in units], key=lambda u: str(u["unit_id"])),
        "windows": sorted([asdict(w) for w in windows], key=lambda w: str(w["window_id"])),
        "rows": sorted(
            [
                (str(r.id), r.status.value, r.scheduled_minutes, str(r.instruction_window_id))
                for r in rows
            ]
        ),
        "children": sorted(str(n) for n in children),
        "context": context,
    }
    fingerprint = hashlib.sha256(json.dumps(data, default=str, sort_keys=True).encode()).hexdigest()
    return context, rows, units, windows, fingerprint


def previous_sessions(rows):
    result = defaultdict(list)
    for row in rows:
        result[row.unit_id].append(row.instruction_window_id)
    return {uid: tuple(windows) for uid, windows in result.items()}
