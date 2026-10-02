"""Fully self-contained demo seeding script.

Generates all input documents (syllabus, past paper, mark scheme) in memory
as minimal valid PDFs, then drives the entire EduFlow pipeline over HTTP:
upload → extract → embed → parse questions → map → corrections → mastery →
emphasis → teaching units → calendar → plan → disrupt → replan → generation.

No external PDF files required. Start the server first:

    uvicorn app.main:app

Then run:

    python scripts/demo_seed.py

Every step prints what actually landed. A step that silently does nothing
shows up as a zero rather than a green check.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import tempfile
import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path
from typing import Any

BASE = "http://127.0.0.1:8000"

# ── Minimal PDF generator ────────────────────────────────────────────
# Generates a valid PDF that pypdf can extract text from. No external
# dependencies — raw PDF byte construction only.


def _escape_pdf_text(text: str) -> str:
    """Escape special characters for a PDF text string (Tj operator)."""
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _make_pdf(lines: list[str], title: str = "") -> bytes:
    """Build a minimal single-page PDF from a list of text lines."""
    obj_offsets: list[int] = []
    buf = BytesIO()

    def _w(s: str) -> None:
        buf.write(s.encode("latin-1"))

    # Header
    _w("%PDF-1.4\n")
    xref_start = buf.tell()

    def _obj(num: int, content: str) -> None:
        obj_offsets.append((num, buf.tell()))
        _w(f"{num} 0 obj\n{content}\nendobj\n")

    # Stream content: one line per text block, spaced 16pt apart
    stream_lines: list[str] = []
    y = 750
    for line in lines:
        escaped = _escape_pdf_text(line)
        stream_lines.append(f"1 0 0 1 50 {y} Tm ({escaped}) Tj")
        y -= 16
    stream = "\n".join(stream_lines)

    _obj(1, f"<</Type /Catalog /Pages 2 0 R>>")
    _obj(2, "<</Type /Pages /Kids [3 0 R] /Count 1>>")
    _obj(
        3,
        "<</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]"
        " /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    )
    _obj(4, f"<</Length {len(stream)}>>\nstream\n{stream}\nendstream")
    _obj(5, "<</Type /Font /Subtype /Type1 /BaseFont /Helvetica>>")

    # Cross-reference table
    xref_pos = buf.tell()
    _w("xref\n")
    _w(f"0 {len(obj_offsets) + 1}\n")
    _w("0000000000 65535 f \n")
    for _, offset in sorted(obj_offsets):
        _w(f"{offset:010d} 00000 n \n")

    # Trailer
    _w("trailer\n")
    _w(f"<</Size {len(obj_offsets) + 1} /Root 1 0 R>>\n")
    _w("startxref\n")
    _w(f"{xref_pos}\n")
    _w("%%EOF\n")

    return buf.getvalue()


# ── Sample content ────────────────────────────────────────────────────

SYLLABUS_LINES = [
    "CS-201 DATA STRUCTURES AND ALGORITHMS",
    "Course Syllabus - Semester Outline",
    "",
    "TOPIC 1: FOUNDATIONS OF DATA STRUCTURES",
    "1.1 Complexity Analysis",
    "  CS201.1.1 Analyse the time complexity of an algorithm using Big-O notation.",
    "  CS201.1.2 Compare best-case, average-case and worst-case complexity.",
    "1.2 Arrays and Linked Lists",
    "  CS201.2.1 Implement singly and doubly linked list operations.",
    "  CS201.2.2 Contrast array and linked-list performance for insertion and deletion.",
    "",
    "TOPIC 2: LINEAR STRUCTURES",
    "2.1 Stacks and Queues",
    "  CS201.3.1 Implement a stack using arrays and linked lists.",
    "  CS201.3.2 Apply stacks to expression evaluation and recursion unwinding.",
    "  CS201.3.3 Implement circular and priority queues.",
    "  Prerequisite: CS201.2.1",
    "",
    "TOPIC 3: TREES",
    "3.1 Binary Trees and Binary Search Trees",
    "  CS201.4.1 Perform inorder, preorder and postorder traversal of a binary tree.",
    "  CS201.4.2 Insert, search and delete nodes in a binary search tree.",
    "  Prerequisite: CS201.2.1",
    "3.2 Balanced Trees",
    "  CS201.5.1 Construct an AVL tree and apply rotations to restore balance.",
    "  CS201.5.2 Construct a B-tree of a given order and perform insertion.",
    "  CS201.5.3 Delete a key from a B-tree and explain the rebalancing process.",
    "  Prerequisite: CS201.4.2",
    "",
    "TOPIC 4: HASHING",
    "4.1 Hash Tables",
    "  CS201.6.1 Design a hash function and evaluate its distribution quality.",
    "  CS201.6.2 Resolve collisions using linear probing and quadratic probing.",
    "  CS201.6.3 Resolve collisions using separate chaining.",
    "  CS201.6.4 Implement hard deletion of keys from an open-addressed hash table.",
    "  Prerequisite: CS201.1.1",
    "",
    "TOPIC 5: GRAPHS",
    "5.1 Graph Representation and Traversal",
    "  CS201.7.1 Represent a graph using adjacency matrix and adjacency list.",
    "  CS201.7.2 Traverse a graph using breadth-first and depth-first search.",
    "  Prerequisite: CS201.3.3",
    "5.2 Shortest Path and Spanning Trees",
    "  CS201.8.1 Compute single-source shortest paths using Dijkstra's algorithm.",
    "  CS201.8.2 Construct a minimum spanning tree using Kruskal's algorithm.",
    "  Prerequisite: CS201.7.2",
    "",
    "TOPIC 6: SORTING ALGORITHMS",
    "6.1 Comparison Sorts",
    "  CS201.9.1 Implement merge sort and analyse its complexity.",
    "  CS201.9.2 Implement quick sort and discuss pivot selection strategies.",
    "  CS201.9.3 Implement heap sort using a binary heap.",
    "  Prerequisite: CS201.1.1",
]

PAST_PAPER_LINES = [
    "CS-201 Data Structures and Algorithms - Final Exam 2024",
    "Duration: 2 hours  Total Marks: 60",
    "",
    "Question 1: Explain Big-O notation and analyse the time complexity of bubble sort. [8 marks]",
    "",
    "Question 2: Write pseudocode for inserting a node at the head of a singly linked list. Compare the time complexity of head insertion versus tail insertion. [10 marks]",
    "",
    "Question 3: Describe the differences between a stack and a queue. Give one real-world application of each data structure. [6 marks]",
    "",
    "Question 4: Perform an inorder traversal of the following binary search tree and list the output sequence. [8 marks]",
    "",
    "Question 5: Explain the concept of hash collisions. Describe two collision resolution strategies and discuss their trade-offs. [10 marks]",
]

MARK_SCHEME_LINES = [
    "CS-201 Mark Scheme - Final Exam 2024",
    "",
    "Question 1: Big-O notation and bubble sort analysis",
    "  Big-O describes the upper bound of an algorithm's growth rate / worst-case complexity",
    "  Bubble sort: O(n^2) in worst and average case / O(n) best case when already sorted",
    "  [2 marks for Big-O definition, 3 marks for bubble sort analysis, 3 marks for examples]",
    "",
    "Question 2: Singly linked list head insertion",
    "  Create new node / set next pointer to current head / update head to new node",
    "  Head insertion is O(1) / tail insertion is O(n) without a tail pointer",
    "  [3 marks for correct pseudocode, 4 marks for complexity, 3 marks for comparison]",
    "",
    "Question 3: Stack vs Queue",
    "  Stack: LIFO / last-in first-out / push and pop operations",
    "  Queue: FIFO / first-in first-out / enqueue and dequeue operations",
    "  Stack application: function call stack / undo mechanism / expression evaluation",
    "  Queue application: print queue / BFS traversal / task scheduling",
    "  [2 marks for stack description, 2 marks for queue description, 2 marks for applications]",
    "",
    "Question 4: Inorder traversal",
    "  Inorder: visit left subtree / visit root / visit right subtree",
    "  For a BST this produces a sorted sequence in ascending order",
    "  [3 marks for correct traversal order, 3 marks for BST property, 2 marks for output]",
    "",
    "Question 5: Hash collisions",
    "  Collision: two keys hash to the same index / same bucket",
    "  Linear probing: check next slot sequentially / suffers from clustering",
    "  Separate chaining: each bucket holds a linked list / easier to implement / uses more memory",
    "  Trade-offs: probing has better cache performance / chaining handles high load factors better",
    "  [2 marks for collision definition, 4 marks for two strategies, 4 marks for trade-offs]",
]

# ── HTTP helpers ──────────────────────────────────────────────────────


def _request(method: str, path: str, payload: Any = None) -> Any:
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            return json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise SystemExit(f"{method} {path} -> HTTP {exc.code}: {body}") from exc


def _upload(pdf_bytes: bytes, filename: str, title: str, doc_type: str) -> dict:
    """Multipart upload using only stdlib."""
    boundary = "----curriculumosdemo"
    parts: list[bytes] = []
    for name, value in (("title", title), ("doc_type", doc_type)):
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode()
        )
    parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/pdf\r\n\r\n".encode()
    )
    parts.append(pdf_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode())

    body = b"".join(parts)
    req = urllib.request.Request(f"{BASE}/ingestion/documents", data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise SystemExit(
            f"upload {filename} failed: {exc.read().decode(errors='replace')}"
        ) from exc


def step(n: int, title: str) -> None:
    print(f"\n{'=' * 68}\n{n}. {title}\n{'=' * 68}")


# ── Main pipeline ─────────────────────────────────────────────────────


def main() -> int:
    # Health check
    try:
        health = _request("GET", "/health")
        if health["status"] != "ok":
            raise SystemExit("server is not healthy — start it with `uvicorn app.main:app`")
    except SystemExit:
        raise
    except Exception:
        raise SystemExit("cannot reach server — start it with `uvicorn app.main:app`")

    print("Server healthy. Starting self-contained demo seed.\n")

    # ── Stage 1: Upload and parse source documents ────────────────────
    step(1, "Upload and parse source documents")

    syllabus_bytes = _make_pdf(SYLLABUS_LINES)
    syllabus = _upload(syllabus_bytes, "CS201_Syllabus.pdf", "CS-201 DSA Syllabus", "syllabus")
    print(f"  syllabus  {syllabus['parser_used'] or 'pypdf':15} {syllabus['span_count']:4} spans  {syllabus['title']}")

    paper_bytes = _make_pdf(PAST_PAPER_LINES)
    paper = _upload(paper_bytes, "Final_2024.pdf", "CS-201 Final Exam 2024", "past_paper")
    print(f"  paper     {paper['parser_used'] or 'pypdf':15} {paper['span_count']:4} spans  {paper['title']}")

    ms_bytes = _make_pdf(MARK_SCHEME_LINES)
    mark_scheme = _upload(ms_bytes, "MS_Final_2024.pdf", "CS-201 Mark Scheme 2024", "mark_scheme")
    print(f"  marksch.  {mark_scheme['parser_used'] or 'pypdf':15} {mark_scheme['span_count']:4} spans  {mark_scheme['title']}")

    # ── Stage 2: Extract curriculum structure ──────────────────────────
    step(2, "Extract curriculum structure from the syllabus")
    nodes = _request("POST", f"/ingestion/documents/{syllabus['id']}/curriculum")
    edges = _request("GET", "/curriculum-edges")
    kinds: dict[str, int] = {}
    for n in nodes:
        kinds[n["node_type"]] = kinds.get(n["node_type"], 0) + 1
    print(f"  {len(nodes)} nodes {kinds}, {len(edges)} edges")
    emb = _request("POST", "/ingestion/curriculum/embeddings")
    print(f"  embedded: {emb['nodes_embedded']}")

    # ── Stage 3: Parse exam questions ─────────────────────────────────
    step(3, "Parse exam questions")
    report = _request(
        "POST",
        f"/ingestion/documents/{paper['id']}/questions",
        {"mark_scheme_document_id": mark_scheme["id"], "year": 2024, "paper_ref": "final"},
    )
    print(f"  {report['questions_created']} questions, {report['mark_scheme_entries_created']} mark scheme entries")
    if report["questions_without_mark_scheme"]:
        print(f"  unmatched questions: {report['questions_without_mark_scheme']}")
    if report["mark_scheme_entries_without_question"]:
        print(f"  orphan entries: {report['mark_scheme_entries_without_question']}")
    questions = _request("GET", "/questions")
    with_marks = sum(1 for q in questions if q["marks"] is not None)
    print(f"  total {len(questions)} questions, {with_marks} with a mark allocation")

    # ── Stage 4: Map questions to objectives (ensemble) ───────────────
    step(4, "Map questions to objectives (ensemble)")
    min_conf = 0.15
    total_mappings = 0
    for q in questions:
        mapped = _request(
            "POST", f"/mappings/questions/{q['id']}", {"min_confidence": min_conf}
        )
        total_mappings += len(mapped)
        print(f"  {q['question_ref']:18} {len(mapped):2} objective(s)")
    print(f"  {total_mappings} mappings total")

    # ── Stage 5a: Teacher corrections ─────────────────────────────────
    step(5, "Teacher corrections + class mastery")
    # Find the first mapping to correct
    mappings = _request("GET", f"/questions/{questions[0]['id']}/mappings")
    if mappings:
        m = mappings[0]
        corrected_weight = min(m["weight"] + 0.1, 1.0)
        _request(
            "POST",
            "/corrections/",
            {
                "entity_type": "question_node_mapping",
                "entity_id": m["id"],
                "before_value": {"weight": m["weight"]},
                "after_value": {"weight": corrected_weight},
                "teacher_id": "demo-teacher",
            },
        )
        print(f"  correction: {m.get('node_label', m['node_id'])} weight {m['weight']:.2f} -> {corrected_weight:.2f}")

    # ── Stage 5b: Class mastery signals ───────────────────────────────
    objectives = [n["id"] for n in nodes if n["node_type"] == "objective"]
    class_id = "CS-4A"
    mastery_statuses = ["mastered", "needs_reinforcement", "reteach", "mastered", "needs_reinforcement"]
    for i, node_id in enumerate(objectives[:5]):
        status = mastery_statuses[i % len(mastery_statuses)]
        _request(
            "POST",
            "/mastery/",
            {
                "class_id": class_id,
                "node_id": node_id,
                "status": status,
                "teacher_id": "demo-teacher",
            },
        )
    summary = _request("GET", f"/mastery/summary?class_id={class_id}")
    print(f"  mastery [{class_id}]: {summary['mastered']} mastered, "
          f"{summary['needs_reinforcement']} reinforce, {summary['reteach']} reteach, "
          f"{summary['unmarked']} unmarked")

    # ── Stage 6: Historical assessment emphasis ───────────────────────
    step(6, "Historical assessment emphasis")
    emphasis = _request("GET", "/emphasis/")
    labels = {n["id"]: n["label"] for n in nodes}
    emphasis.sort(key=lambda r: -r["score"])
    for r in emphasis[:8]:
        print(f"  {r['score']:.3f}  {labels.get(r['node_id'], '?')[:58]}")

    # ── Stage 7: Academic calendar and timetable ──────────────────────
    step(7, "Academic calendar and timetable")
    start = dt.date.today().replace(day=1)
    end = start + dt.timedelta(days=90)
    calendar = _request(
        "POST",
        "/calendars/",
        {
            "school_id": "pilot-school",
            "term_start": start.isoformat(),
            "term_end": end.isoformat(),
        },
    )
    print(f"  calendar {start} -> {end}, {calendar['day_count']} days modelled")

    subject = "Data Structures"
    class_id_plan = "CS-4A"
    windows = _request(
        "POST",
        f"/calendars/{calendar['id']}/instruction-windows",
        {
            "slots": [
                {
                    "subject": subject,
                    "class_id": class_id_plan,
                    "weekday": wd,
                    "start_time": "09:00",
                    "end_time": "10:00",
                }
                for wd in (0, 2, 4)  # Mon / Wed / Fri
            ]
        },
    )
    print(f"  {windows['windows_created']} instruction windows (Mon/Wed/Fri 09:00-10:00)")

    # ── Stage 8: Solve the term plan ──────────────────────────────────
    step(8, "Solve the term plan")
    emphasis_map = {r["node_id"]: r["score"] for r in emphasis}
    units = _request(
        "POST",
        "/ingestion/teaching-units",
        {
            "node_ids": objectives,
            "default_duration_minutes": 60,
            "priorities": emphasis_map,
        },
    )
    print(f"  {len(units)} teaching units created, priority seeded from emphasis")

    plan = _request(
        "POST",
        "/planning/plans",
        {
            "calendar_id": calendar["id"],
            "subject": subject,
            "class_id": class_id_plan,
            "node_ids": objectives,
            "trigger_reason": "initial_plan",
        },
    )
    print(f"  solver: {plan['status']}")
    print(f"  {len(plan['assignments'])} units scheduled, {len(plan['unscheduled_unit_ids'])} unscheduled")
    scheduled = _request("GET", f"/planning/plans/{plan['plan_version_id']}")
    for row in scheduled[:6]:
        print(f"    {row['date']}  {row['node_label'][:52]}")

    # ── Stage 9: Disruption and replan ────────────────────────────────
    step(9, "Disruption and replan with plan-diff")
    if not scheduled:
        print("  nothing scheduled — skipping")
        return 0

    closed = scheduled[0]["date"]
    disrupted = _request(
        "POST",
        f"/calendars/{calendar['id']}/disrupt",
        {"date": closed, "reason": "school closed"},
    )
    print(f"  school closed {closed}: {disrupted['windows_disrupted']} window(s) withdrawn")

    replan = _request(
        "POST",
        "/planning/plans",
        {
            "calendar_id": calendar["id"],
            "subject": subject,
            "class_id": class_id_plan,
            "node_ids": objectives,
            "trigger_reason": "calendar_disruption",
            "parent_version_id": plan["plan_version_id"],
        },
    )
    print(f"  replan: {replan['status']}")
    print(f"  {replan['unchanged_count']} unchanged, {replan['moved_count']} moved, "
          f"{len(replan['unscheduled_unit_ids'])} dropped")

    # Plan diff
    diff = _request("GET", f"/planning/plans/{replan['plan_version_id']}/diff")
    if diff:
        print(f"\n  Plan diff ({len(diff)} units):")
        for d in diff:
            arrow = f"{d['previous_date'] or '—'} -> {d['current_date'] or '—'}"
            print(f"    {d['change_type']:12}  {arrow:24}  {d['node_label'][:40]}")
    print("\n  A good replan is measured by how little it disturbs.")

    # ── Stage 10: Grounded generation ─────────────────────────────────
    step(10, "Grounded generation (lesson + assessment)")
    if replan["assignments"]:
        unit_id = replan["assignments"][0]["unit_id"]
        try:
            claims = _request("POST", f"/generation/lessons/{unit_id}")
            verified = sum(1 for c in claims if c["verification_status"] == "verified")
            print(f"  lesson claims: {len(claims)} generated, {verified} verified")
            for c in claims[:3]:
                print(f"    [{c['verification_status']}] {c['text'][:72]}")
        except SystemExit as e:
            print(f"  lesson generation skipped (LLM not configured): {e}")
    else:
        print("  no scheduled units — skipping lesson generation")

    if objectives:
        try:
            assess = _request(
                "POST",
                f"/generation/assessments/{objectives[0]}",
                {"count": 3},
            )
            print(f"  assessment questions: {len(assess)} generated")
            for c in assess[:3]:
                print(f"    [{c['verification_status']}] {c['text'][:72]}")
        except SystemExit as e:
            print(f"  assessment generation skipped (LLM not configured): {e}")

    # ── Summary ───────────────────────────────────────────────────────
    stats = _request("GET", "/stats")
    print(f"\n{'=' * 68}")
    print("Demo seed complete. Pipeline state:")
    for key in ["documents", "spans", "objectives", "questions", "mappings", "units", "scheduled", "claims"]:
        print(f"  {key:14} {stats.get(key, 0)}")
    print(f"\nOpen {BASE} to explore the workspace.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
