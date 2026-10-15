"""Pure tests for 90-day synthetic worker attendance planning."""
from collections import Counter

import pytest

from simulation.community_attendance import (
    MILESTONE_TYPES,
    PLANNING_TRUTH,
    attendance_summary,
    project_worker_attendance,
    session_plan,
    worker_states_for_day,
)
from simulation.community_staffing import assignments_for_day
from simulation.community_shift_events import PLANNED_ONLY, planned_shift_milestones


def test_every_worker_has_exactly_one_truthful_daily_state():
    states = worker_states_for_day(0)
    assert len(states) == 66
    assert len({state["actor_id"] for state in states}) == 66
    assert Counter(state["attendance_state"] for state in states) == {
        "scheduled": 37, "on_call": 2, "off_duty": 27,
    }
    assert all(state["status"] == "planned" for state in states)
    assert all(state["execution_state"] == "not_executed" for state in states)
    assert all(state["receipt_ids"] == [] and state["truth"] == PLANNING_TRUTH for state in states)
    assert all(state["actor_type"] == "simulated-agent" and state["actor_simulated"] for state in states)


def test_scheduled_worker_has_five_ordered_unexecuted_milestones():
    state = next(state for state in worker_states_for_day(2)
                 if state["attendance_state"] == "scheduled")
    events = state["milestones"]
    assert tuple(event["event_type"] for event in events) == MILESTONE_TYPES
    assert [event["day_index"] * 1440 + event["minute"] for event in events] == sorted(
        event["day_index"] * 1440 + event["minute"] for event in events
    )
    assert all(event["status"] == "planned" and event["receipt_id"] is None for event in events)
    assert all(event["executed_at"] is None for event in events)
    assert all(
        event["truth"] == (
            PLANNING_TRUTH if event["stream_kind"] == "attendance_session_intent"
            else PLANNED_ONLY
        )
        for event in events
    )

    login = events[0]
    assert login["login_kind"] == "simulation_session_marker"
    assert login["authentication_performed"] is False
    assert login["creates_user_or_token"] is False
    acceptance = events[2]
    assert acceptance["assignment_scope"] == "shift_only"
    assert acceptance["task_ids"] == [] and acceptance["accepts_canonical_task"] is False


def test_attendance_embeds_canonical_shift_events_instead_of_minting_duplicates():
    assignment = assignments_for_day(2)[0]
    state = session_plan(assignment)
    embedded = [
        event for event in state["milestones"]
        if event["stream_kind"] == "canonical_shift_milestone"
    ]

    assert embedded == planned_shift_milestones(assignment)
    assert [event["event_type"] for event in embedded] == [
        "clock_in", "handoff", "clock_out",
    ]
    assert all(event["event_id"].startswith("sim:shift-event:") for event in embedded)
    assert not any(
        event["event_id"].startswith("sim:attendance-event:")
        for event in embedded
    )
    assert state["shift_milestones_source"] == "simulation.community_shift_events"


def test_off_duty_worker_has_no_invented_session_or_activity():
    state = next(state for state in worker_states_for_day(0)
                 if state["attendance_state"] == "off_duty")
    assert state["session_id"] is None and state["shift_assignment_id"] is None
    assert state["milestones"] == []
    assert state["rest_reason"] == "not_scheduled"
    assert "user_id" not in state and "token" not in state


def test_on_call_worker_is_reachable_but_never_present_or_clocked_in():
    states = [state for state in worker_states_for_day(0) if state["attendance_state"] == "on_call"]
    assert {(state["department"], state["shift"]) for state in states} == {
        ("maintenance", "after_hours_on_call"), ("nursing", "night_on_call"),
    }
    for state in states:
        assert state["milestones"] == [] and state["session_id"] is None
        assert state["physically_present"] is False
        assert state["shift_assignment_id"].startswith("sim:shift:0:")
    assignment = next(row for row in assignments_for_day(0) if row["duty"] == "on_call")
    with pytest.raises(ValueError, match="on-call duty has no clock-in"):
        planned_shift_milestones(assignment)


def test_default_projection_covers_all_57_workers_for_90_days_deterministically():
    first = project_worker_attendance("2026-10-13")
    second = project_worker_attendance("2026-10-13", days=90)
    assert first == second
    assert len(first) == 66 * 90
    assert set(Counter(state["actor_id"] for state in first).values()) == {90}
    assert len({state["date"] for state in first}) == 90
    summary = attendance_summary(first)
    assert summary == {
        "workers": 66,
        "states": {"off_duty": 27 * 90, "on_call": 2 * 90, "scheduled": 37 * 90},
        "session_milestones": {
            event_type: 37 * 90 for event_type in ("assignment_acceptance", "planned_login")
        },
        "canonical_shift_milestone_references": {
            event_type: 37 * 90 for event_type in ("clock_in", "clock_out", "handoff")
        },
        "milestones": {event_type: 37 * 90 for event_type in sorted(MILESTONE_TYPES)},
        "truth": PLANNING_TRUTH,
    }


def test_every_department_attendance_has_regular_planned_rest_days():
    projection = project_worker_attendance("2026-10-13", days=90)
    by_worker = {
        actor_id: [state for state in projection if state["actor_id"] == actor_id]
        for actor_id in {state["actor_id"] for state in projection}
    }

    assert len(by_worker) == 66
    for states in by_worker.values():
        assert Counter(state["attendance_state"] for state in states)["off_duty"] > 0
        assert all(
            sum(state["attendance_state"] in {"scheduled", "on_call"}
                for state in states[start:start + 7]) <= 6
            for start in range(90 - 7 + 1)
        )


def test_overnight_session_handoff_and_clock_out_land_next_day():
    assignment = next(row for row in assignments_for_day(0)
                      if row["department"] == "nursing" and row["shift"] == "night")
    state = session_plan(assignment)
    by_type = {event["event_type"]: event for event in state["milestones"]}
    assert by_type["planned_login"]["day_index"] == 0
    assert by_type["planned_login"]["time"] == "21:50"
    assert by_type["handoff"]["day_index"] == 1
    assert by_type["handoff"]["time"] == "05:45"
    assert by_type["clock_out"]["day_index"] == 1
    assert by_type["clock_out"]["time"] == "06:00"

    dated = next(state for state in project_worker_attendance("2026-10-13", days=1)
                 if state["attendance_state"] == "scheduled"
                 and state["actor_id"] == assignment["actor_id"])
    assert dated["milestones"][-1]["planned_at"] == "2026-10-14T06:00:00"


def test_no_projection_creates_a_real_login_user_or_execution_claim():
    projection = project_worker_attendance("2026-10-13", days=2)
    events = [event for state in projection for event in state["milestones"]]
    assert events
    assert all("user_id" not in event and "auth_token" not in event for event in events)
    assert all(event["execution_state"] == "not_executed" for event in events)
    assert all(event["receipt_id"] is None for event in events)


def test_invalid_projection_and_session_timing_are_rejected():
    with pytest.raises(ValueError):
        worker_states_for_day(-1)
    with pytest.raises(ValueError):
        project_worker_attendance("2026-10-13", days=0)
    assignment = assignments_for_day(0)[0]
    with pytest.raises(ValueError):
        session_plan(assignment, login_lead_minutes=-1)
    with pytest.raises(ValueError):
        session_plan(assignment, acceptance_delay_minutes=600)
