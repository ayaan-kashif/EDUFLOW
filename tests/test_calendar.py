from datetime import time

from app.api.calendar import slot_duration_minutes


def test_slot_duration_minutes_counts_same_day_minutes():
    assert slot_duration_minutes(time(9, 15), time(10, 45)) == 90


def test_slot_duration_minutes_returns_zero_for_equal_times():
    assert slot_duration_minutes(time(9, 0), time(9, 0)) == 0


def test_slot_duration_minutes_keeps_inverted_times_negative():
    assert slot_duration_minutes(time(11, 0), time(10, 30)) == -30
