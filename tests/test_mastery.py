"""Tests for mastery signal logic.

Following the same pattern as test_planning_diff.py: pure-function tests
that don't need a database session.
"""

import uuid
from datetime import UTC, datetime

from app.api.mastery import _latest_per_node


class _FakeSignal:
    """Minimal stand-in for ClassMasterySignal in pure tests."""

    def __init__(self, class_id, node_id, status, created_at):
        self.id = uuid.uuid4()
        self.class_id = class_id
        self.node_id = node_id
        self.status = status
        self.created_at = created_at


def _ts(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def test_latest_per_node_returns_most_recent():
    node = uuid.uuid4()
    signals = [
        _FakeSignal("CS-4A", node, "reteach", _ts(2026, 1, 1)),
        _FakeSignal("CS-4A", node, "mastered", _ts(2026, 1, 5)),
    ]
    result = _latest_per_node(signals)
    assert len(result) == 1
    assert result[0].status == "mastered"


def test_latest_per_node_preserves_earlier_for_different_nodes():
    n1, n2 = uuid.uuid4(), uuid.uuid4()
    signals = [
        _FakeSignal("CS-4A", n1, "reteach", _ts(2026, 1, 1)),
        _FakeSignal("CS-4A", n2, "mastered", _ts(2026, 1, 5)),
    ]
    result = _latest_per_node(signals)
    assert len(result) == 2
    statuses = {r.node_id: r.status for r in result}
    assert statuses[n1] == "reteach"
    assert statuses[n2] == "mastered"


def test_latest_per_node_separates_classes():
    node = uuid.uuid4()
    signals = [
        _FakeSignal("CS-4A", node, "reteach", _ts(2026, 1, 1)),
        _FakeSignal("CS-5B", node, "mastered", _ts(2026, 1, 5)),
    ]
    result = _latest_per_node(signals)
    assert len(result) == 2
    classes = {r.class_id for r in result}
    assert classes == {"CS-4A", "CS-5B"}


def test_latest_per_node_empty_list():
    assert _latest_per_node([]) == []
