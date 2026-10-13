"""Coverage-aware, planning-only routine dispatch tests."""

import inspect

import pytest

from simulation import community_dispatch
from simulation.community_dispatch import (
    QUEUED_UNASSIGNED,
    READY_UNASSIGNED,
    plan_routine_dispatch,
)
from simulation.community_routines import plan_first_24_hours


def test_only_uncovered_family_call_events_queue_until_admin_returns():
    dispatches = plan_routine_dispatch()
    queued = [row for row in dispatches if row.dispatch_state == QUEUED_UNASSIGNED]

    assert len(dispatches) == 153
    assert len(queued) == 5
    assert {row.routine for row in queued} == {"family_call_coordination"}
    assert {row.department for row in queued} == {"administration"}
    assert {row.resident_key for row in queued} == {
        "resident-002", "resident-004", "resident-006", "resident-008", "resident-010",
    }
    assert all(row.planned_minute > 16 * 60 for row in queued)
    assert all((row.ready_day_index, row.ready_minute) == (1, 8 * 60) for row in queued)
    assert all(row.assigned_actor_id is None for row in queued)
    assert all("queued and unassigned" in row.truth.lower() for row in queued)
    assert all("no work has been completed" in row.truth.lower() for row in queued)


def test_covered_events_are_ready_but_remain_unassigned_and_unexecuted():
    first = plan_routine_dispatch()
    second = plan_routine_dispatch()
    ready = [row for row in first if row.dispatch_state == READY_UNASSIGNED]

    assert first == second
    assert len(ready) == 148
    assert all(row.ready_day_index == row.planned_day_index for row in ready)
    assert all(row.ready_minute == row.planned_minute for row in ready)
    assert all(row.assigned_actor_id is None for row in ready)
    assert all("no work has been completed" in row.truth.lower() for row in ready)


def test_queue_uses_event_day_and_next_canonical_coverage_window():
    events = plan_first_24_hours(day_index=3)
    queued = [
        row for row in plan_routine_dispatch(events)
        if row.dispatch_state == QUEUED_UNASSIGNED
    ]

    assert queued
    assert all(row.planned_day_index == 3 for row in queued)
    assert all((row.ready_day_index, row.ready_minute) == (4, 8 * 60) for row in queued)
    assert all(row.ready_time_hhmm == "08:00" for row in queued)


def test_dispatch_planner_is_pure_and_validates_queue_horizon():
    source = inspect.getsource(community_dispatch)
    assert "from deps import" not in source and "import db" not in source
    assert "insert_one" not in source and "update_one" not in source
    assert "httpx" not in source and "requests" not in source

    with pytest.raises(ValueError, match="positive"):
        plan_routine_dispatch(max_queue_days=0)
