"""Reproducible offline regression metrics. Run: python -m eval.run."""

import asyncio
import json
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from time import perf_counter
from uuid import UUID

from app.domain.models import CurriculumNode, ExamQuestion, SourceSpan
from app.generation.claims import GeneratedClaim
from app.generation.evidence import check_evidence
from app.ingestion.service import hash_span_text
from app.mapping.mapper import EnsembleMapper
from app.planning.scheduler import UnitInput, WindowInput, solve_schedule, validate_schedule
from tests.demo_fixture import TOPICS


def precision_at_k(predicted, expected, k):
    return len(set(predicted[:k]) & set(expected)) / k


async def evaluate():
    fixture = json.loads((Path(__file__).parent / "fixtures.json").read_text())
    nodes = [
        CurriculumNode(id=UUID(int=i + 1), label=label, description=text)
        for i, (label, text, _, _) in enumerate(TOPICS)
    ]
    mapper = EnsembleMapper(None)
    predictions = []
    for i, example in enumerate(fixture["mapping"]):
        question = ExamQuestion(id=UUID(int=100 + i), text=example["question"])
        scored = await mapper.score_candidates(question, nodes, acceptable_terms=example["terms"])
        predictions.append([c.node.label for c in sorted(scored, key=lambda c: -c.weight)])
    precisions = {
        f"precision_at_{k}": round(
            sum(precision_at_k(p, e["gold"], k) for p, e in zip(predictions, fixture["mapping"]))
            / len(predictions),
            4,
        )
        for k in [1, 3]
    }
    # Mechanical checks are evaluated separately from semantic LLM verification.
    correct = 0
    false_accepts = 0
    for i, example in enumerate(fixture["claims"]):
        sid = UUID(int=1000 + i)
        span = SourceSpan(
            id=sid, text=example["source"], content_hash=hash_span_text(example["source"])
        )
        claim = GeneratedClaim(example["text"], [str(sid)], {str(sid): example["quote"]})
        valid = check_evidence(claim, [span]).valid
        correct += valid == example["expected_valid"]
        false_accepts += valid and not example["expected_valid"]
    units = [UnitInput(UUID(int=i + 1), 60, 0.5) for i in range(8)]
    start = date(2026, 10, 5)
    windows = [WindowInput(UUID(int=500 + i), start + timedelta(days=i), 60) for i in range(12)]
    initial = solve_schedule(units, windows)
    previous = {a.unit_id: a.window_id for a in initial.assignments}
    closed = replace(windows[0], is_available=False)
    disrupted = [closed] + windows[1:]
    stable = solve_schedule(units, disrupted, previous_assignment=previous)
    naive = solve_schedule(units, disrupted)
    naive_moved = sum(previous.get(a.unit_id) != a.window_id for a in naive.assignments)
    # Time the actual pure scheduling path, not a fictitious teacher time study.
    started = perf_counter()
    benchmark = solve_schedule(units, windows)
    elapsed = round((perf_counter() - started) * 1000, 2)
    return {
        "dataset": fixture["description"],
        "mapping": {
            "samples": len(predictions),
            "mode": "Actual EnsembleMapper with lexical and mark-scheme terminology signals; no live embeddings or LLM",
            **precisions,
        },
        "mechanical_grounding": {
            "samples": len(fixture["claims"]),
            "check_accuracy": correct / len(fixture["claims"]),
            "false_accepts": false_accepts,
            "note": "Citation/quotation integrity only. This does not measure semantic unsupported-claim rate.",
        },
        "replanning": {
            "solver_moved_units": stable.moved_count,
            "naive_rebuild_moved_units": naive_moved,
            "unchanged_units": stable.unchanged_count,
            "hard_constraint_violations": len(
                validate_schedule(stable.assignments, units, disrupted)
            ),
        },
        "latency": {"pure_solver_ms": elapsed, "solver_status": benchmark.status},
        "not_measured": [
            "Live plain-prompt model baseline",
            "Semantic unsupported-claim rate",
            "Held-out improvement after real teacher corrections",
            "Teacher time to a usable plan",
        ],
    }


def main():
    report = asyncio.run(evaluate())
    path = Path(__file__).parent / "report.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
