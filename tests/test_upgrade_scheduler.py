from dataclasses import replace
from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.planning.forecast import forecast_resilience
from app.planning.scheduler import (
    Assignment,
    InfeasibleScheduleError,
    UnitInput,
    WindowInput,
    solve_schedule,
    validate_schedule,
)


def windows(n, minutes=60):
    return [WindowInput(uuid4(), date(2026, 10, 5) + timedelta(days=i), minutes) for i in range(n)]


def test_three_sessions_compress_to_two_without_violating_minimum():
    unit = UnitInput(
        uuid4(), 180, 1, minimum_duration_minutes=120, splittable=True, minimum_session_minutes=30
    )
    slots = windows(2)
    result = solve_schedule([unit], slots)
    assert len(result.assignments) == 2
    assert sum(a.scheduled_minutes for a in result.assignments) == 120
    assert result.shortened_count == 1
    assert not result.unscheduled_unit_ids
    assert validate_schedule(result.assignments, [unit], slots) == []


def test_high_emphasis_wins_when_only_one_unit_fits():
    low, high = UnitInput(uuid4(), 60, 0.1), UnitInput(uuid4(), 60, 0.95)
    result = solve_schedule([low, high], windows(1))
    assert result.assignments[0].unit_id == high.unit_id
    assert str(low.unit_id) in result.explanations


def test_unavailable_prerequisite_never_allows_dependent():
    prereq = UnitInput(uuid4(), 120)
    dependent = UnitInput(uuid4(), 60, 1, (prereq.unit_id,))
    for limit in [0, 1]:
        result = solve_schedule([dependent, prereq], windows(2), time_limit_seconds=limit)
        assert dependent.unit_id in result.unscheduled_unit_ids


def test_all_prerequisite_sessions_finish_before_dependent():
    prereq = UnitInput(uuid4(), 120, splittable=True)
    dependent = UnitInput(uuid4(), 60, 1, (prereq.unit_id,))
    slots = windows(3)
    result = solve_schedule([dependent, prereq], slots)
    before = [a.date for a in result.assignments if a.unit_id == prereq.unit_id]
    after = [a.date for a in result.assignments if a.unit_id == dependent.unit_id]
    assert max(before) < min(after)


def test_greedy_fallback_resolves_dependency_order_and_compression():
    prereq = UnitInput(uuid4(), 60, 0.1)
    dependent = UnitInput(
        uuid4(), 120, 1, (prereq.unit_id,), minimum_duration_minutes=60, splittable=True
    )
    slots = windows(2)
    result = solve_schedule([dependent, prereq], slots, time_limit_seconds=0)
    assert len(result.assignments) == 2
    assert validate_schedule(result.assignments, [dependent, prereq], slots) == []


def test_replan_keeps_both_sessions_of_an_unchanged_unit():
    u = UnitInput(uuid4(), 120, splittable=True)
    slots = windows(4)
    previous = {u.unit_id: (slots[1].window_id, slots[2].window_id)}
    result = solve_schedule([u], slots, previous_sessions=previous)
    assert result.unchanged_count == 1
    assert {a.window_id for a in result.assignments} == set(previous[u.unit_id])


def test_taught_session_is_a_hard_constraint_not_a_churn_preference():
    unit = UnitInput(uuid4(), 60)
    slots = windows(3)
    locked = Assignment(unit.unit_id, slots[2].window_id, slots[2].date, 60)
    result = solve_schedule([unit], slots, coverage_preference=1, locked_assignments=(locked,))
    assert result.assignments == [locked]
    with pytest.raises(InfeasibleScheduleError):
        solve_schedule(
            [unit], [replace(slots[2], is_available=False)], locked_assignments=(locked,)
        )


def test_duration_change_is_not_counted_as_unchanged():
    unit = UnitInput(uuid4(), 60, minimum_duration_minutes=45)
    slots = windows(1, 45)
    result = solve_schedule(
        [unit],
        slots,
        previous_assignment={unit.unit_id: slots[0].window_id},
        previous_minutes={(unit.unit_id, slots[0].window_id): 60},
    )
    assert result.shortened_count == 1
    assert result.unchanged_count == 0


def test_cycles_and_missing_dependencies_return_explanations():
    a, b = uuid4(), uuid4()
    units = [
        UnitInput(a, 60, prerequisite_unit_ids=(b,)),
        UnitInput(b, 60, prerequisite_unit_ids=(a,)),
    ]
    result = solve_schedule(units, windows(5))
    assert len(result.unscheduled_unit_ids) == 2
    assert len(result.explanations) == 2


def test_seeded_forecast_is_reproducible_and_handles_zero_closures():
    units, slots = [UnitInput(uuid4(), 60, 0.9)], windows(4)
    a = forecast_resilience(units, slots, samples=10, disruption_rate=0, seed=9)
    b = forecast_resilience(units, slots, samples=10, disruption_rate=0, seed=9)
    assert a["high_emphasis_coverage_probability"] == b["high_emphasis_coverage_probability"] == 1
    assert a["confidence_interval"][0] < 1


@pytest.mark.parametrize("seed", range(10))
def test_random_calendar_outputs_always_satisfy_constraints(seed):
    import random

    rng = random.Random(seed)
    slots = [replace(w, is_available=rng.random() > 0.25) for w in windows(8)]
    units = [
        UnitInput(
            uuid4(),
            rng.choice([60, 120]),
            rng.random(),
            minimum_duration_minutes=60,
            splittable=True,
        )
        for _ in range(5)
    ]
    for limit in [0, 0.2]:
        result = solve_schedule(units, slots, time_limit_seconds=limit)
        assert not validate_schedule(result.assignments, units, slots)
