import uuid
from datetime import date

from app.planning.service import ScheduledUnitSnapshot, diff_schedules


def test_same_day_timetable_move_is_visible():
    uid = uuid.uuid4()
    previous = ScheduledUnitSnapshot(uid, "Biology", date(2026, 10, 5), 60, "planned", uuid.uuid4())
    current = ScheduledUnitSnapshot(uid, "Biology", date(2026, 10, 5), 60, "planned", uuid.uuid4())
    assert diff_schedules([previous], [current])[0].change_type == "moved"


def _snapshot(
    unit_id,
    label,
    day,
    minutes=60,
    status="planned",
):
    return ScheduledUnitSnapshot(
        unit_id=unit_id,
        node_label=label,
        date=day,
        scheduled_minutes=minutes,
        status=status,
    )


def test_diff_schedules_reports_unchanged_and_moved_units():
    unchanged = uuid.uuid4()
    moved = uuid.uuid4()

    diff = diff_schedules(
        [
            _snapshot(unchanged, "Arrays", date(2026, 1, 5)),
            _snapshot(moved, "Stacks", date(2026, 1, 6)),
        ],
        [
            _snapshot(unchanged, "Arrays", date(2026, 1, 5)),
            _snapshot(moved, "Stacks", date(2026, 1, 9)),
        ],
    )

    by_unit = {item.unit_id: item for item in diff}
    assert by_unit[unchanged].change_type == "unchanged"
    assert by_unit[moved].change_type == "moved"
    assert by_unit[moved].previous_date == date(2026, 1, 6)
    assert by_unit[moved].current_date == date(2026, 1, 9)


def test_diff_schedules_reports_added_removed_and_compressed_units():
    removed = uuid.uuid4()
    added = uuid.uuid4()
    compressed = uuid.uuid4()

    diff = diff_schedules(
        [
            _snapshot(removed, "Trees", date(2026, 1, 5)),
            _snapshot(compressed, "Graphs", date(2026, 1, 6), minutes=90),
        ],
        [
            _snapshot(added, "Hashing", date(2026, 1, 7)),
            _snapshot(compressed, "Graphs", date(2026, 1, 6), minutes=45),
        ],
    )

    by_unit = {item.unit_id: item for item in diff}
    assert by_unit[removed].change_type == "removed"
    assert by_unit[added].change_type == "added"
    assert by_unit[compressed].change_type == "compressed"
