"""Bounded-duration, multi-session CP-SAT planner with independently checked output."""

import math
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import date as date_
from time import perf_counter
from uuid import UUID

from ortools.sat.python import cp_model


@dataclass(frozen=True)
class UnitInput:
    unit_id: UUID
    duration_minutes: int
    priority: float = 0.0
    prerequisite_unit_ids: tuple[UUID, ...] = ()
    deadline: date_ | None = None
    minimum_duration_minutes: int | None = None
    splittable: bool = False
    minimum_session_minutes: int = 15

    @property
    def minimum(self):
        return (
            self.minimum_duration_minutes
            if self.minimum_duration_minutes is not None
            else self.duration_minutes
        )


@dataclass(frozen=True)
class WindowInput:
    window_id: UUID
    date: date_
    available_minutes: int
    is_available: bool = True


@dataclass(frozen=True)
class Assignment:
    unit_id: UUID
    window_id: UUID
    date: date_
    scheduled_minutes: int | None = None


@dataclass(frozen=True)
class ScheduleResult:
    status: str
    assignments: list[Assignment]
    unscheduled_unit_ids: list[UUID]
    unchanged_count: int
    moved_count: int
    shortened_count: int = 0
    solve_time_ms: float = 0.0
    weighted_coverage: float = 0.0
    explanations: dict[str, str] = field(default_factory=dict)
    conflict_unit_ids: list[UUID] = field(default_factory=list)


class InfeasibleScheduleError(Exception):
    pass


def _check_inputs(units, windows):
    if len({u.unit_id for u in units}) != len(units):
        raise ValueError("Teaching unit IDs must be unique")
    if len({w.window_id for w in windows}) != len(windows):
        raise ValueError("Window IDs must be unique")
    for u in units:
        if not 0 < u.minimum <= u.duration_minutes or u.minimum_session_minutes <= 0:
            raise ValueError("Unit durations must satisfy 0 < minimum <= preferred")
        if not math.isfinite(u.priority) or u.priority < 0:
            raise ValueError("Priority must be finite and nonnegative")
    if any(w.available_minutes <= 0 for w in windows):
        raise ValueError("Window capacity must be positive")


def _candidate_windows(unit, windows):
    minimum = min(unit.minimum_session_minutes, unit.minimum) if unit.splittable else unit.minimum
    return [
        w
        for w in windows
        if w.is_available
        and w.available_minutes >= minimum
        and (unit.deadline is None or w.date <= unit.deadline)
    ]


def validate_schedule(assignments, units, windows):
    violations = []
    ub = {u.unit_id: u for u in units}
    wb = {w.window_id: w for w in windows}
    grouped = defaultdict(list)
    occupied = set()
    for a in assignments:
        u, w = ub.get(a.unit_id), wb.get(a.window_id)
        if u is None or w is None:
            violations.append(f"{a.unit_id}: references unknown unit/window")
            continue
        minutes = a.scheduled_minutes if a.scheduled_minutes is not None else u.duration_minutes
        if not w.is_available:
            violations.append(f"{a.unit_id}: assigned to unavailable window {w.window_id}")
        if a.date != w.date:
            violations.append(f"{a.unit_id}: assignment date differs from window")
        if not 0 < minutes <= w.available_minutes:
            violations.append(f"{a.unit_id}: does not fit in window {w.window_id}")
        if u.splittable and minutes < min(u.minimum_session_minutes, u.minimum):
            violations.append(f"{a.unit_id}: session below its minimum")
        if u.deadline and w.date > u.deadline:
            violations.append(f"{a.unit_id}: scheduled after its deadline {u.deadline}")
        if w.window_id in occupied:
            violations.append(f"window {w.window_id}: double-booked")
        occupied.add(w.window_id)
        grouped[u.unit_id].append((w.date, minutes))
    for uid, sessions in grouped.items():
        u = ub[uid]
        total = sum(m for _, m in sessions)
        if not u.minimum <= total <= u.duration_minutes:
            violations.append(f"{uid}: total minutes outside permitted bounds")
        if not u.splittable and len(sessions) > 1:
            violations.append(f"{uid}: indivisible unit was split")
        for pid in u.prerequisite_unit_ids:
            if pid not in grouped:
                violations.append(f"{uid}: missing prerequisite {pid}")
            elif max(d for d, _ in grouped[pid]) >= min(d for d, _ in sessions):
                violations.append(f"{uid}: scheduled on/before prerequisite {pid}")
    return violations


def _result(
    status, assignments, units, windows, previous, start, previous_minutes=None
) -> ScheduleResult:
    grouped = defaultdict(list)
    for a in assignments:
        grouped[a.unit_id].append(a)
    unchanged = sum(
        1
        for uid, rows in grouped.items()
        if uid in previous
        and {a.window_id for a in rows} == set(previous[uid])
        and all(
            (previous_minutes or {}).get((uid, a.window_id), a.scheduled_minutes)
            == a.scheduled_minutes
            for a in rows
        )
    )
    unscheduled = [u.unit_id for u in units if u.unit_id not in grouped]
    reasons = {}
    for u in units:
        if u.unit_id not in unscheduled:
            continue
        candidates = _candidate_windows(u, windows)
        if not candidates:
            reason = "No available session fits the minimum duration before the deadline."
        elif any(p not in grouped for p in u.prerequisite_unit_ids):
            reason = "A prerequisite is missing or could not be scheduled."
        else:
            reason = (
                f"Needs at least {u.minimum} minutes; {len(candidates)} candidate slots "
                "compete with higher-weight coverage or prerequisite ordering."
            )
        reasons[str(u.unit_id)] = reason
    weights = {u.unit_id: 1 + u.priority for u in units}
    total_weight = sum(weights.values())
    coverage = sum(weights[uid] for uid in grouped) / total_weight if total_weight else 1.0
    shortened = sum(
        sum(a.scheduled_minutes or 0 for a in grouped[u.unit_id]) < u.duration_minutes
        for u in units
        if u.unit_id in grouped
    )
    moved = sum(
        1
        for uid, rows in grouped.items()
        if uid not in previous or {a.window_id for a in rows} != set(previous[uid])
    )
    return ScheduleResult(
        status,
        assignments,
        unscheduled,
        unchanged,
        moved,
        shortened,
        round((perf_counter() - start) * 1000, 2),
        coverage,
        reasons,
    )


def _greedy_schedule(units, windows, previous, start) -> ScheduleResult:
    remaining = {w.window_id: w for w in windows}
    assignments = []
    end_dates: dict[UUID, date_] = {}
    pending = {u.unit_id: u for u in units}
    while pending:
        ready = [
            u for u in pending.values() if all(p in end_dates for p in u.prerequisite_unit_ids)
        ]
        if not ready:
            break
        u = min(ready, key=lambda u: (-u.priority, u.unit_id.int))
        del pending[u.unit_id]
        earliest = max((end_dates[p] for p in u.prerequisite_unit_ids), default=date_.min)
        candidates = [
            w for w in _candidate_windows(u, list(remaining.values())) if w.date > earliest
        ]
        candidates.sort(
            key=lambda w: (w.window_id not in previous.get(u.unit_id, ()), w.date, w.window_id.int)
        )
        chosen = []
        left = u.duration_minutes
        for w in candidates:
            minutes = min(w.available_minutes, left)
            floor = min(u.minimum_session_minutes, u.minimum) if u.splittable else u.minimum
            if minutes < floor:
                continue
            chosen.append(Assignment(u.unit_id, w.window_id, w.date, minutes))
            left -= minutes
            if left == 0 or not u.splittable:
                break
        if sum(a.scheduled_minutes or 0 for a in chosen) < u.minimum:
            continue
        assignments.extend(chosen)
        end_dates[u.unit_id] = max(a.date for a in chosen)
        for a in chosen:
            remaining.pop(a.window_id)
    return _result("greedy_fallback", assignments, units, windows, previous, start)


def solve_schedule(
    units: list[UnitInput],
    windows: list[WindowInput],
    *,
    previous_assignment: dict[UUID, UUID] | None = None,
    previous_sessions: dict[UUID, tuple[UUID, ...]] | None = None,
    time_limit_seconds: float = 30.0,
    churn_penalty: int = 1000,
    coverage_preference: float = 0.5,
    previous_minutes: dict[tuple[UUID, UUID], int] | None = None,
    locked_assignments: tuple[Assignment, ...] = (),
) -> ScheduleResult:
    start = perf_counter()
    _check_inputs(units, windows)
    if not 0 <= coverage_preference <= 1 or time_limit_seconds < 0 or churn_penalty < 0:
        raise ValueError("Invalid solver preferences or time limit")
    previous = previous_sessions or {k: (v,) for k, v in (previous_assignment or {}).items()}
    windows = sorted(windows, key=lambda w: (w.date, w.window_id.int))
    if not units:
        return _result("optimal", [], units, windows, previous, start)
    if time_limit_seconds == 0:
        if locked_assignments:
            raise InfeasibleScheduleError(
                "A positive solver budget is required to preserve taught lessons"
            )
        result = _greedy_schedule(units, windows, previous, start)
    else:
        model = cp_model.CpModel()
        x, minutes, covered, totals = {}, {}, {}, {}
        candidates = {u.unit_id: _candidate_windows(u, windows) for u in units}
        window_indices = {w.window_id: i for i, w in enumerate(windows)}
        terms: list[cp_model.LinearExpr | int] = []
        for u in units:
            uid = u.unit_id
            covered[uid] = model.new_bool_var(f"covered_{uid}")
            for w in candidates[uid]:
                key = uid, w.window_id
                x[key] = model.new_bool_var(f"session_{uid}_{w.window_id}")
                minutes[key] = model.new_int_var(
                    0, min(u.duration_minutes, w.available_minutes), f"minutes_{uid}_{w.window_id}"
                )
                floor = min(u.minimum_session_minutes, u.minimum) if u.splittable else u.minimum
                model.add(minutes[key] >= floor * x[key])
                model.add(minutes[key] <= min(u.duration_minutes, w.available_minutes) * x[key])
                model.add(x[key] <= covered[uid])
                if previous:
                    model.add_hint(x[key], int(w.window_id in previous.get(uid, ())))
                terms.append(-x[key] * (window_indices[w.window_id] + 1))
            rows = [x[uid, w.window_id] for w in candidates[uid]]
            model.add(sum(rows) >= covered[uid])
            if not u.splittable:
                model.add(sum(rows) == covered[uid])
            totals[uid] = sum(minutes[uid, w.window_id] for w in candidates[uid])
            model.add(totals[uid] >= u.minimum * covered[uid])
            model.add(totals[uid] <= u.duration_minutes * covered[uid])
            weight = max(1, round(100 * (1 + u.priority)))
            terms.append(weight * 10000 * covered[uid])
            terms.append(weight * 10 * totals[uid])
            penalty = round(churn_penalty * (1 - coverage_preference) * 100)
            for old in previous.get(uid, ()):
                terms.append(-penalty * (1 - x.get((uid, old), 0)))
            for w in candidates[uid]:
                if uid in previous and w.window_id not in previous[uid]:
                    terms.append(-penalty * x[uid, w.window_id])
        for w in windows:
            model.add(sum(v for (uid, wid), v in x.items() if wid == w.window_id) <= 1)
        for assignment in locked_assignments:
            key = assignment.unit_id, assignment.window_id
            if key not in x or assignment.scheduled_minutes is None:
                raise InfeasibleScheduleError(
                    "A taught session no longer fits its original timetable window"
                )
            model.add(x[key] == 1)
            model.add(minutes[key] == assignment.scheduled_minutes)
        for u in units:
            for pid in u.prerequisite_unit_ids:
                if pid not in covered:
                    model.add(covered[u.unit_id] == 0)
                    continue
                model.add(covered[u.unit_id] <= covered[pid])
                for w in candidates[u.unit_id]:
                    for p in candidates[pid]:
                        if p.date >= w.date:
                            model.add(x[u.unit_id, w.window_id] + x[pid, p.window_id] <= 1)
        model.maximize(sum(terms))
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit_seconds
        solver.parameters.num_search_workers = 1
        solver.parameters.random_seed = 0
        status = solver.solve(model)
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            dates = {w.window_id: w.date for w in windows}
            assignments = [
                Assignment(uid, wid, dates[wid], solver.value(minutes[uid, wid]))
                for (uid, wid), var in x.items()
                if solver.value(var)
            ]
            result = _result(
                "optimal" if status == cp_model.OPTIMAL else "feasible",
                assignments,
                units,
                windows,
                previous,
                start,
                previous_minutes,
            )
        else:
            if locked_assignments:
                raise InfeasibleScheduleError(
                    "Could not produce a feasible plan preserving taught sessions; review constraints"
                )
            result = _greedy_schedule(units, windows, previous, start)
        if result.unscheduled_unit_ids:
            # Diagnose the requirement to cover everything using a real CP-SAT
            # assumption core. This is a sufficient conflict set, not a minimal core.
            model.add_assumptions(list(covered.values()))
            solver.parameters.max_time_in_seconds = min(0.2, time_limit_seconds)
            diagnostic = solver.solve(model)
            if diagnostic == cp_model.INFEASIBLE:
                by_index = {flag.index: uid for uid, flag in covered.items()}
                conflict = [
                    by_index[i]
                    for i in solver.sufficient_assumptions_for_infeasibility()
                    if i in by_index
                ]
                result = replace(result, conflict_unit_ids=conflict)
    violations = validate_schedule(result.assignments, units, windows)
    if violations:
        raise InfeasibleScheduleError(
            f"scheduler produced hard-constraint violations: {violations}"
        )
    return result
