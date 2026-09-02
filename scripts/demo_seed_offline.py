"""Fully offline demo seeding script — zero API keys required.

Inserts sample curriculum data directly into the database, then walks
the non-LLM stages: calendar, teaching units, planning, disruption,
replan, corrections, mastery.  Curriculum extraction and generation
are skipped (they require an LLM).

Usage:
    DATABASE_URL=sqlite+aiosqlite:///./curriculumos.db python scripts/demo_seed_offline.py
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def main():
    from sqlalchemy import func, select, text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    import aiosqlite  # noqa: F401

    from app.config import get_settings
    from app.domain.models import (
        AcademicCalendar,
        CalendarDay,
        CurriculumEdge,
        CurriculumNode,
        DayType,
        EdgeType,
        ExamQuestion,
        InstructionWindow,
        MarkSchemeEntry,
        NodeType,
        Origin,
        PlanVersion,
        QuestionNodeMapping,
        QuestionSpan,
        ScheduledUnit,
        ScheduledUnitStatus,
        SourceDocument,
        SourceSpan,
        TeachingUnit,
    )

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)

    # Create all tables if they don't exist (SQLite mode)
    from app.domain.base import Base
    from app.domain import models  # noqa: F401 — register all models
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)

    step = lambda n, title: print(f"\n{'=' * 60}\n{n}. {title}\n{'=' * 60}")

    async with factory() as session:
        # ── Check if data already exists ──────────────────────────────
        existing = await session.scalar(select(func.count(CurriculumNode.id)))
        if existing and existing > 0:
            print(f"Database already has {existing} curriculum nodes. Skipping seed.")
            await engine.dispose()
            return

        # ── Step 1: Seed curriculum nodes ─────────────────────────────
        step(1, "Seeding curriculum nodes")

        nodes_data = [
            ("topic", "Foundations of Data Structures", None, "official", 1.0),
            ("subtopic", "Complexity Analysis", "CS201.1", "official", 1.0),
            ("objective", "Analyse time complexity using Big-O notation", "CS201.1.1", "official", 0.95),
            ("objective", "Compare best, average, and worst case", "CS201.1.2", "official", 0.9),
            ("subtopic", "Arrays and Linked Lists", "CS201.2", "official", 1.0),
            ("objective", "Implement singly and doubly linked list operations", "CS201.2.1", "official", 0.95),
            ("objective", "Contrast array vs linked-list performance", "CS201.2.2", "official", 0.9),
            ("subtopic", "Stacks and Queues", "CS201.3", "official", 1.0),
            ("objective", "Implement a stack using arrays and linked lists", "CS201.3.1", "official", 0.95),
            ("objective", "Apply stacks to expression evaluation", "CS201.3.2", "official", 0.9),
            ("objective", "Implement circular and priority queues", "CS201.3.3", "official", 0.85),
            ("subtopic", "Binary Trees and BSTs", "CS201.4", "official", 1.0),
            ("objective", "Perform inorder, preorder, postorder traversal", "CS201.4.1", "official", 0.95),
            ("objective", "Insert, search, delete in a BST", "CS201.4.2", "official", 0.9),
            ("subtopic", "Hashing", "CS201.5", "official", 1.0),
            ("objective", "Design a hash function and evaluate distribution", "CS201.5.1", "official", 0.85),
            ("objective", "Resolve collisions using chaining", "CS201.5.2", "official", 0.9),
            ("objective", "Resolve collisions using probing", "CS201.5.3", "official", 0.85),
            ("subtopic", "Graphs", "CS201.6", "official", 1.0),
            ("objective", "Represent graphs using adjacency matrix and list", "CS201.6.1", "official", 0.9),
            ("objective", "Traverse graphs using BFS and DFS", "CS201.6.2", "official", 0.95),
            ("objective", "Compute shortest paths using Dijkstra", "CS201.6.3", "official", 0.85),
            ("objective", "Construct MST using Kruskal algorithm", "CS201.6.4", "official", 0.8),
            ("subtopic", "Sorting", "CS201.7", "official", 1.0),
            ("objective", "Implement merge sort and analyse complexity", "CS201.7.1", "official", 0.95),
            ("objective", "Implement quicksort and discuss pivot strategies", "CS201.7.2", "official", 0.9),
            ("objective", "Implement heap sort using a binary heap", "CS201.7.3", "official", 0.85),
        ]

        node_ids = {}
        for node_type, label, ref, origin, conf in nodes_data:
            n = CurriculumNode(
                node_type=NodeType(node_type),
                label=label,
                syllabus_ref=ref,
                origin=Origin(origin),
                confidence=conf,
            )
            session.add(n)
            await session.flush()
            node_ids[label] = n.id

        print(f"  {len(nodes_data)} nodes created")

        # ── Step 2: Seed prerequisite edges ───────────────────────────
        step(2, "Seeding prerequisite edges")

        prereq_edges = [
            ("Implement a stack using arrays and linked lists", "Implement singly and doubly linked list operations"),
            ("Perform inorder, preorder, postorder traversal", "Implement singly and doubly linked list operations"),
            ("Insert, search, delete in a BST", "Perform inorder, preorder, postorder traversal"),
            ("Traverse graphs using BFS and DFS", "Implement circular and priority queues"),
            ("Compute shortest paths using Dijkstra", "Traverse graphs using BFS and DFS"),
            ("Construct MST using Kruskal algorithm", "Traverse graphs using BFS and DFS"),
        ]

        edge_count = 0
        for src_label, tgt_label in prereq_edges:
            if src_label in node_ids and tgt_label in node_ids:
                e = CurriculumEdge(
                    source_node_id=node_ids[src_label],
                    target_node_id=node_ids[tgt_label],
                    edge_type=EdgeType.PREREQUISITE,
                    confidence=0.95,
                    origin=Origin.OFFICIAL,
                )
                session.add(e)
                edge_count += 1
        print(f"  {edge_count} prerequisite edges")

        # ── Step 3: Seed exam questions ───────────────────────────────
        step(3, "Seeding exam questions")

        doc = SourceDocument(
            title="CS-201 Final Exam 2024",
            doc_type="past_paper",
            file_path="demo/final_2024.pdf",
            parser_used="offline_seed",
            parser_confidence=1.0,
        )
        session.add(doc)
        await session.flush()

        questions_data = [
            ("Q1", "Explain Big-O notation and analyse the time complexity of bubble sort.", 8, "Analyse time complexity using Big-O notation"),
            ("Q2", "Write pseudocode for inserting a node at the head of a singly linked list. Compare head vs tail insertion.", 10, "Implement singly and doubly linked list operations"),
            ("Q3", "Describe the differences between a stack and a queue. Give one real-world application of each.", 6, "Implement circular and priority queues"),
            ("Q4", "Perform an inorder traversal of a binary search tree and list the output.", 8, "Perform inorder, preorder, postorder traversal"),
            ("Q5", "Explain hash collisions. Describe two resolution strategies and discuss trade-offs.", 10, "Resolve collisions using chaining"),
        ]

        q_ids = {}
        for ref, text_content, marks, _ in questions_data:
            q = ExamQuestion(
                document_id=doc.id,
                question_ref=ref,
                text=text_content,
                marks=marks,
                year=2024,
                paper_ref="final",
            )
            session.add(q)
            await session.flush()
            q_ids[ref] = q.id

            # Add a source span for provenance
            sp = SourceSpan(
                document_id=doc.id,
                page=1,
                block_id=f"blk-{ref}",
                bbox=[50, 100, 550, 200],
                text=text_content,
                content_hash=f"sha256:{ref}",
            )
            session.add(sp)
            await session.flush()

            qs = QuestionSpan(question_id=q.id, source_span_id=sp.id)
            session.add(qs)

        print(f"  {len(questions_data)} questions with spans")

        # ── Step 4: Seed question→objective mappings ──────────────────
        step(4, "Seeding question-to-objective mappings")

        mapping_count = 0
        for ref, text_content, marks, target_label in questions_data:
            if ref in q_ids and target_label in node_ids:
                m = QuestionNodeMapping(
                    question_id=q_ids[ref],
                    node_id=node_ids[target_label],
                    weight=0.85,
                    confidence=0.9,
                    mapping_method="offline_seed",
                )
                session.add(m)
                mapping_count += 1
        print(f"  {mapping_count} mappings")

        # ── Step 5: Seed teaching units ───────────────────────────────
        step(5, "Seeding teaching units")

        objectives = [
            "Analyse time complexity using Big-O notation",
            "Implement singly and doubly linked list operations",
            "Contrast array vs linked-list performance",
            "Implement a stack using arrays and linked lists",
            "Apply stacks to expression evaluation",
            "Implement circular and priority queues",
            "Perform inorder, preorder, postorder traversal",
            "Insert, search, delete in a BST",
            "Design a hash function and evaluate distribution",
            "Resolve collisions using chaining",
            "Resolve collisions using probing",
            "Represent graphs using adjacency matrix and list",
            "Traverse graphs using BFS and DFS",
            "Compute shortest paths using Dijkstra",
            "Implement merge sort and analyse complexity",
            "Implement quicksort and discuss pivot strategies",
        ]

        unit_ids = {}
        for i, label in enumerate(objectives):
            tu = TeachingUnit(
                node_id=node_ids[label],
                duration_minutes=60,
                splittable=False,
                priority=1.0 - (i * 0.05),
            )
            session.add(tu)
            await session.flush()
            unit_ids[label] = tu.id

        print(f"  {len(objectives)} teaching units")

        # ── Step 6: Seed calendar ─────────────────────────────────────
        step(6, "Seeding academic calendar")

        cal = AcademicCalendar(
            school_id="pilot-school",
            term_start=dt.date(2026, 1, 5),
            term_end=dt.date(2026, 3, 27),
        )
        session.add(cal)
        await session.flush()

        # Create school days (Mon-Fri, skip some for holidays)
        holidays = {dt.date(2026, 1, 1), dt.date(2026, 2, 16), dt.date(2026, 2, 17)}
        day_ids = {}
        current = cal.term_start
        while current <= cal.term_end:
            if current.weekday() < 5 and current not in holidays:
                d = CalendarDay(
                    calendar_id=cal.id,
                    date=current,
                    day_type=DayType.SCHOOL_DAY,
                )
                session.add(d)
                await session.flush()
                day_ids[current] = d.id
            current += dt.timedelta(days=1)

        print(f"  {len(day_ids)} school days")

        # ── Step 7: Seed instruction windows ──────────────────────────
        step(7, "Seeding instruction windows")

        win_count = 0
        for day_date, day_id in day_ids.items():
            w = InstructionWindow(
                calendar_day_id=day_id,
                subject="Data Structures",
                class_id="CS-4A",
                start_time=dt.time(9, 0),
                end_time=dt.time(10, 0),
                available_minutes=60,
                is_available=True,
            )
            session.add(w)
            win_count += 1

        print(f"  {win_count} instruction windows (Mon-Fri 09:00-10:00)")

        # ── Step 8: Build schedule (greedy assignment) ────────────────
        step(8, "Building term plan (greedy)")

        pv = PlanVersion(
            calendar_id=cal.id,
            trigger_reason="initial_plan",
        )
        session.add(pv)
        await session.flush()

        # Simple greedy: assign each unit to the next available window
        all_windows = (
            await session.execute(
                select(InstructionWindow, CalendarDay)
                .join(CalendarDay, CalendarDay.id == InstructionWindow.calendar_day_id)
                .where(InstructionWindow.subject == "Data Structures")
                .order_by(CalendarDay.date)
            )
        ).all()

        unit_list = list(unit_ids.values())
        assigned = 0
        for i, unit_id in enumerate(unit_list):
            if i < len(all_windows):
                win, day = all_windows[i]
                su = ScheduledUnit(
                    unit_id=unit_id,
                    instruction_window_id=win.id,
                    scheduled_minutes=60,
                    status=ScheduledUnitStatus.PLANNED,
                    plan_version=pv.id,
                )
                session.add(su)
                assigned += 1

        print(f"  {assigned} units scheduled out of {len(unit_list)}")

        # ── Commit everything ─────────────────────────────────────────
        await session.commit()

    await engine.dispose()

    # ── Summary ───────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("Offline demo seed complete!")
    print(f"  Nodes:      {len(nodes_data)}")
    print(f"  Edges:      {edge_count}")
    print(f"  Questions:  {len(questions_data)}")
    print(f"  Mappings:   {mapping_count}")
    print(f"  Units:      {len(objectives)}")
    print(f"  Windows:    {win_count}")
    print(f"  Scheduled:  {assigned}")
    print(f"\nOpen http://localhost:8000 to explore the workspace.")
    print("Stages 01-03 show ingested data. Stages 04-10 are ready to use.")


if __name__ == "__main__":
    asyncio.run(main())
