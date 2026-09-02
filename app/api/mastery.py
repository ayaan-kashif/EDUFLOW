"""Class-level mastery signal endpoints.

V1 is class-level only — see 09_RISKS_AND_OPEN_QUESTIONS.md. No
student_id anywhere in this table or any other; do not add one in P2/P3 work.

A teacher marks an objective as mastered / needs_reinforcement / reteach.
When multiple signals exist for the same (class_id, node_id) pair, the
latest one wins — the list endpoint returns only the most recent per node.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.domain.models import (
    ClassMasterySignal,
    CurriculumNode,
    MasteryStatus,
)

router = APIRouter(prefix="/mastery", tags=["mastery"])


class MasterySignalIn(BaseModel):
    class_id: str
    node_id: UUID
    status: MasteryStatus
    teacher_id: str


class MasterySignalOut(BaseModel):
    id: UUID
    class_id: str
    node_id: UUID
    node_label: str
    status: MasteryStatus
    marked_by: str


class MasterySummaryOut(BaseModel):
    class_id: str
    total_objectives: int
    mastered: int
    needs_reinforcement: int
    reteach: int
    unmarked: int


def _latest_per_node(rows):
    """Return only the most recent signal per (class_id, node_id)."""
    seen: dict[tuple[str, UUID], ClassMasterySignal] = {}
    for row in rows:
        key = (row.class_id, row.node_id)
        if key not in seen or row.created_at > seen[key].created_at:
            seen[key] = row
    return list(seen.values())


@router.get("/", response_model=list[MasterySignalOut])
async def list_mastery_signals(
    class_id: str = Query(..., description="Class identifier"),
    session: AsyncSession = Depends(get_session),
) -> list[MasterySignalOut]:
    """All mastery signals for a class, latest per objective."""
    result = await session.execute(
        select(ClassMasterySignal)
        .where(ClassMasterySignal.class_id == class_id)
        .order_by(ClassMasterySignal.created_at.desc())
    )
    rows = list(result.scalars().all())
    latest = _latest_per_node(rows)

    # Resolve node labels
    node_ids = [r.node_id for r in latest]
    node_rows = (
        await session.execute(
            select(CurriculumNode).where(CurriculumNode.id.in_(node_ids))
        )
    ).scalars().all()
    label_map = {n.id: n.label for n in node_rows}

    return [
        MasterySignalOut(
            id=r.id,
            class_id=r.class_id,
            node_id=r.node_id,
            node_label=label_map.get(r.node_id, str(r.node_id)),
            status=r.status,
            marked_by=r.marked_by,
        )
        for r in latest
    ]


@router.post("/", response_model=MasterySignalOut)
async def create_mastery_signal(
    body: MasterySignalIn,
    session: AsyncSession = Depends(get_session),
) -> MasterySignalOut:
    """Record or update a mastery signal. Creates a new row every time;
    the list endpoint returns only the latest per objective.
    """
    node = await session.get(CurriculumNode, body.node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="curriculum_node not found")

    signal = ClassMasterySignal(
        class_id=body.class_id,
        node_id=body.node_id,
        status=body.status,
        marked_by=body.teacher_id,
    )
    session.add(signal)
    await session.commit()
    await session.refresh(signal)

    return MasterySignalOut(
        id=signal.id,
        class_id=signal.class_id,
        node_id=signal.node_id,
        node_label=node.label,
        status=signal.status,
        marked_by=signal.marked_by,
    )


@router.get("/summary", response_model=MasterySummaryOut)
async def mastery_summary(
    class_id: str = Query(..., description="Class identifier"),
    session: AsyncSession = Depends(get_session),
) -> MasterySummaryOut:
    """Summary counts: how many objectives are mastered, need reinforcement,
    reteach, or have no signal yet.
    """
    # Total objectives in the curriculum
    total_result = await session.execute(select(func.count(CurriculumNode.id)))
    total_objectives = total_result.scalar() or 0

    # Latest signals for this class
    result = await session.execute(
        select(ClassMasterySignal)
        .where(ClassMasterySignal.class_id == class_id)
        .order_by(ClassMasterySignal.created_at.desc())
    )
    rows = list(result.scalars().all())
    latest = _latest_per_node(rows)

    counts = {MasteryStatus.MASTERED: 0, MasteryStatus.NEEDS_REINFORCEMENT: 0, MasteryStatus.RETEACH: 0}
    for sig in latest:
        counts[sig.status] = counts.get(sig.status, 0) + 1

    marked = sum(counts.values())
    return MasterySummaryOut(
        class_id=class_id,
        total_objectives=total_objectives,
        mastered=counts[MasteryStatus.MASTERED],
        needs_reinforcement=counts[MasteryStatus.NEEDS_REINFORCEMENT],
        reteach=counts[MasteryStatus.RETEACH],
        unmarked=total_objectives - marked,
    )
