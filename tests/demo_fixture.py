"""Original, explicitly synthetic Biology teaching fixtures; no copyrighted syllabus copy."""

import shutil
from datetime import date, time, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from app.domain.models import (
    AcademicCalendar,
    CalendarDay,
    Claim,
    ClaimEvidence,
    CurriculumEdge,
    CurriculumNode,
    DayType,
    DocType,
    EdgeType,
    ExamQuestion,
    InstructionWindow,
    MappingMethod,
    NodeType,
    Origin,
    QuestionNodeMapping,
    SourceDocument,
    SourceSpan,
    TeachingUnit,
    VerificationStatus,
)
from app.ingestion.service import hash_span_text

TOPICS = [
    (
        "Cell structure",
        "Cells contain cytoplasm and a cell membrane. Plant cells also have a cell wall.",
        60,
        0.7,
    ),
    (
        "Movement across membranes",
        "Diffusion is the net movement of particles from higher to lower concentration.",
        60,
        0.5,
    ),
    (
        "Enzymes",
        "Enzymes are biological catalysts. Temperature and pH affect enzyme activity.",
        180,
        1.0,
    ),
    (
        "Plant nutrition",
        "Photosynthesis uses light energy to convert carbon dioxide and water into glucose and oxygen.",
        60,
        0.8,
    ),
    (
        "Human nutrition",
        "Digestion breaks large food molecules into smaller molecules that can be absorbed.",
        60,
        0.6,
    ),
    (
        "Transport",
        "The circulatory system transports substances around the body in blood.",
        60,
        0.5,
    ),
    (
        "Gas exchange",
        "Alveoli provide a large surface area for gas exchange in the lungs.",
        60,
        0.6,
    ),
    ("Respiration", "Aerobic respiration releases energy from glucose using oxygen.", 60, 0.8),
    ("Inheritance", "Genes are lengths of DNA that influence inherited characteristics.", 120, 0.9),
    ("Ecology", "A food chain shows the transfer of energy between organisms.", 60, 0.4),
]


async def seed_demo(session, *, reset_calendar=False):
    title = "Biology studio demo — original synthetic teaching notes"
    fixture = Path(__file__).resolve().parent / "fixtures/demo-biology.pdf"
    upload_dir = Path(__file__).resolve().parent.parent / "uploads"
    upload_dir.mkdir(exist_ok=True)
    source_pdf = upload_dir / "original-biology-demo.pdf"
    if fixture.is_file() and not source_pdf.exists():
        shutil.copyfile(fixture, source_pdf)
    existing = (
        (await session.execute(select(SourceDocument).where(SourceDocument.title == title)))
        .scalars()
        .first()
    )
    if existing:
        existing.file_path = str(source_pdf)
        existing.parser_used = "original_demo_pdf"
        cal = (
            (
                await session.execute(
                    select(AcademicCalendar).where(AcademicCalendar.school_id == "studio-demo")
                )
            )
            .scalars()
            .first()
        )
        nodes = (
            (
                await session.execute(
                    select(CurriculumNode).where(CurriculumNode.syllabus_ref.like("DEMO.BIO.%"))
                )
            )
            .scalars()
            .all()
        )
        if reset_calendar:
            days = (
                (
                    await session.execute(
                        select(CalendarDay).where(CalendarDay.calendar_id == cal.id)
                    )
                )
                .scalars()
                .all()
            )
            for day in days:
                day.day_type = (
                    DayType.SCHOOL_DAY
                    if day.date.weekday() < 5 and (day.date - cal.term_start).days != 18
                    else DayType.NON_TEACHING
                )
            windows = (
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
            available = {d.id for d in days if d.day_type == DayType.SCHOOL_DAY}
            for window in windows:
                window.is_available = window.calendar_day_id in available
            await session.commit()
        return {
            "document_id": existing.id,
            "calendar_id": cal.id,
            "node_ids": [n.id for n in nodes],
            "subject": "Biology",
            "class_id": "BIO-10",
            "reference_date": cal.term_start,
            "synthetic": True,
        }
    doc = SourceDocument(
        id=uuid4(),
        title=title,
        doc_type=DocType.SYLLABUS,
        file_path=str(source_pdf),
        parser_used="original_demo_pdf",
        parser_confidence=1,
    )
    session.add(doc)
    nodes, units = [], []
    for i, (label, text, duration, priority) in enumerate(TOPICS):
        node = CurriculumNode(
            id=uuid4(),
            node_type=NodeType.OBJECTIVE,
            label=label,
            description=text,
            syllabus_ref=f"DEMO.BIO.{i + 1:02d}",
            origin=Origin.TEACHER_DEFINED,
            confidence=1,
        )
        span = SourceSpan(
            id=uuid4(),
            document_id=doc.id,
            page=i + 1,
            block_id=f"demo-{i}",
            bbox=[0, 0, 0, 0],
            text=text,
            content_hash=hash_span_text(text),
        )
        unit = TeachingUnit(
            id=uuid4(),
            node_id=node.id,
            duration_minutes=duration,
            splittable=duration > 60,
            minimum_session_minutes=30,
            priority=priority,
        )
        question = ExamQuestion(
            id=uuid4(),
            document_id=doc.id,
            question_ref=f"demo_q{i}",
            text=f"Explain {label.lower()}.",
            marks=round(priority * 10),
            year=2026,
        )
        claim = Claim(
            id=uuid4(),
            text=text,
            generation_model="original_fixture",
            verification_model="exact_source_fixture",
            verification_status=VerificationStatus.NOT_CHECKED,
            confidence=0,
        )
        session.add_all([node, span, unit, question, claim])
        await session.flush()
        session.add_all(
            [
                QuestionNodeMapping(
                    id=uuid4(),
                    question_id=question.id,
                    node_id=node.id,
                    weight=priority,
                    confidence=1,
                    mapping_method=MappingMethod.HUMAN_CORRECTED,
                ),
                ClaimEvidence(claim_id=claim.id, source_span_id=span.id),
                CurriculumEdge(
                    id=uuid4(),
                    source_node_id=node.id,
                    target_node_id=node.id,
                    edge_type=EdgeType.COVERED_BY,
                    confidence=1,
                    origin=Origin.TEACHER_DEFINED,
                    provenance_id=span.id,
                ),
            ]
        )
        nodes.append(node)
        units.append(unit)
    units[1].prerequisite_unit_ids = [units[0].id]
    units[8].prerequisite_unit_ids = [units[0].id]
    for a, b in [(0, 1), (0, 8)]:
        session.add(
            CurriculumEdge(
                id=uuid4(),
                source_node_id=nodes[a].id,
                target_node_id=nodes[b].id,
                edge_type=EdgeType.PREREQUISITE,
                confidence=1,
                origin=Origin.TEACHER_DEFINED,
            )
        )
    start = date(2026, 10, 5)
    cal = AcademicCalendar(
        id=uuid4(), school_id="studio-demo", term_start=start, term_end=start + timedelta(days=20)
    )
    session.add(cal)
    await session.flush()
    for i in range(21):
        d = start + timedelta(days=i)
        teaching_day = d.weekday() < 5 and i != 18  # final Friday is a staff-development day
        day = CalendarDay(
            id=uuid4(),
            calendar_id=cal.id,
            date=d,
            day_type=DayType.SCHOOL_DAY if teaching_day else DayType.NON_TEACHING,
        )
        session.add(day)
        await session.flush()
        if teaching_day:
            session.add(
                InstructionWindow(
                    id=uuid4(),
                    calendar_day_id=day.id,
                    subject="Biology",
                    class_id="BIO-10",
                    start_time=time(9),
                    end_time=time(10),
                    available_minutes=60,
                    is_available=True,
                )
            )
    await session.commit()
    return {
        "document_id": doc.id,
        "calendar_id": cal.id,
        "node_ids": [n.id for n in nodes],
        "subject": "Biology",
        "class_id": "BIO-10",
        "reference_date": start,
        "synthetic": True,
    }
