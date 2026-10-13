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


def test_all_routines_are_ready_under_continuous_department_coverage():
    dispatches = plan_routine_dispatch()
    queued = [row for row in dispatches if row.dispatch_state == QUEUED_UNASSIGNED]

    assert len(dispatches) == 153
    assert queued == []


def test_covered_events_are_ready_but_remain_unassigned_and_unexecuted():
    first = plan_routine_dispatch()
    second = plan_routine_dispatch()
    ready = [row for row in first if row.dispatch_state == READY_UNASSIGNED]

    assert first == second
    assert len(ready) == 153
    assert all(row.ready_day_index == row.planned_day_index for row in ready)
    assert all(row.ready_minute == row.planned_minute for row in ready)
    assert all(row.assigned_actor_id is None for row in ready)
    assert all("no work has been completed" in row.truth.lower() for row in ready)


def test_queue_uses_event_day_and_next_canonical_coverage_window(monkeypatch):
    event = plan_first_24_hours(day_index=3)[0]

    def synthetic_gap(day_index, minute, department):
        if (day_index, minute, department) == (3, event.minute, event.department):
            return ()
        return ("sim:staff:test",)

    monkeypatch.setattr(community_dispatch, "_on_shift_actor_ids", synthetic_gap)
    queued = [row for row in plan_routine_dispatch((event,))
              if row.dispatch_state == QUEUED_UNASSIGNED]

    assert len(queued) == 1
    assert queued[0].planned_day_index == 3
    assert (queued[0].ready_day_index, queued[0].ready_minute) == (3, event.minute + 1)
    assert queued[0].assigned_actor_id is None


def test_dispatch_planner_is_pure_and_validates_queue_horizon():
    source = inspect.getsource(community_dispatch)
    assert "from deps import" not in source and "import db" not in source
    assert "insert_one" not in source and "update_one" not in source
    assert "httpx" not in source and "requests" not in source

    with pytest.raises(ValueError, match="positive"):
        plan_routine_dispatch(max_queue_days=0)
