"""Seeded disruption simulations; estimates are conditional on the supplied model."""

import random
from dataclasses import replace
from time import perf_counter

from app.planning.scheduler import solve_schedule


def forecast_resilience(
    units, windows, *, samples=100, disruption_rate=0.1, seed=42, locked_assignments=()
):
    rng = random.Random(seed)
    taught_dates = {a.date for a in locked_assignments}
    dates = sorted({w.date for w in windows if w.is_available and w.date not in taught_dates})
    high = {u.unit_id for u in units if u.priority >= 0.7}
    if not high:
        high = {u.unit_id for u in units}
    success, coverage, dropped = 0, [], {}
    start = perf_counter()
    completed = 0
    baseline = solve_schedule(
        units,
        windows,
        time_limit_seconds=1,
        coverage_preference=1,
        locked_assignments=locked_assignments,
    )
    previous = {}
    for assignment in baseline.assignments:
        previous.setdefault(assignment.unit_id, []).append(assignment.window_id)
    previous = {uid: tuple(ids) for uid, ids in previous.items()}
    cache = {frozenset(): baseline}
    incomplete = 0
    for _ in range(samples):
        # A closure withdraws the whole day, including multiple timetable slots.
        closed = {d for d in dates if rng.random() < disruption_rate}
        scenario = [
            replace(w, is_available=w.is_available and w.date not in closed) for w in windows
        ]
        key = frozenset(closed)
        if key not in cache:
            cache[key] = solve_schedule(
                units,
                scenario,
                time_limit_seconds=0.5,
                coverage_preference=1,
                previous_sessions=previous,
                locked_assignments=locked_assignments,
            )
        result = cache[key]
        incomplete += result.status != "optimal"
        missing = set(result.unscheduled_unit_ids)
        success += not (high & missing)
        coverage.append(result.weighted_coverage)
        for uid in missing:
            dropped[str(uid)] = dropped.get(str(uid), 0) + 1
        completed += 1
        if perf_counter() - start > 15:
            break
    probability = success / completed if completed else 0
    # Wilson interval conveys sampling uncertainty rather than fake precision.
    z = 1.96
    denom = 1 + z * z / completed
    center = (probability + z * z / (2 * completed)) / denom
    margin = (
        z
        * (
            (probability * (1 - probability) / completed + z * z / (4 * completed * completed))
            ** 0.5
        )
        / denom
    )
    return {
        "samples": completed,
        "requested_samples": samples,
        "seed": seed,
        "disruption_rate": disruption_rate,
        "high_emphasis_coverage_probability": probability,
        "confidence_interval": [max(0, center - margin), min(1, center + margin)],
        "mean_weighted_coverage": sum(coverage) / completed,
        "at_risk_units": [
            {"unit_id": uid, "miss_probability": n / completed}
            for uid, n in sorted(dropped.items(), key=lambda x: -x[1])
        ],
        "elapsed_ms": round((perf_counter() - start) * 1000),
        "incomplete_solves": incomplete,
        "assumption": "Independent whole-day closures at the configured rate, excluding days with taught sessions; estimates depend on the scenario model and solver budget.",
    }
