"""Pure tests for planned community shift and coverage events."""
import pytest

from simulation.community_shift_events import (
    PLANNED_ONLY,
    SHIFT_MILESTONE_TYPES,
    event_counts,
    planned_events_for_day,
    planned_shift_milestones,
)
from simulation.community_staffing import assignments_for_day


def test_day_plan_is_deterministic_complete_and_only_planned():
    first = planned_events_for_day(0)
    assert first == planned_events_for_day(0)
    assert len({event["event_id"] for event in first}) == len(first)
    assert event_counts(first) == {
        "clock_in": 32,
        "clock_out": 32,
        "coverage_gap_ended": 5,
        "coverage_gap_present": 5,
        "coverage_gap_started": 5,
        "handoff": 32,
    }
    assert all(event["status"] == "planned" for event in first)
    assert all(event["execution_state"] == "not_executed" for event in first)
    assert all(event["receipt_id"] is None and event["executed_at"] is None for event in first)
    assert all(event["truth"] == PLANNED_ONLY for event in first)
    assert all(event["requires_receipt_if_executed"] is True for event in first)


def test_staff_events_keep_explicit_synthetic_identity_and_never_fake_a_login():
    staff_events = [event for event in planned_events_for_day(2)
                    if event["event_type"] in {"clock_in", "handoff", "clock_out"}]
    assert staff_events
    assert all(event["actor_id"].startswith("sim:staff:") for event in staff_events)
    assert all(event["actor_type"] == "simulated-agent" for event in staff_events)
    assert all(event["identity_basis"] == "synthetic" and event["actor_simulated"] for event in staff_events)
    assert all("user_id" not in event and "login" not in event for event in staff_events)
    assert all(event["target_type"] == "staff_shift" for event in staff_events)
    assert all(event["stream_kind"] == "canonical_shift_milestone" for event in staff_events)


def test_assignment_has_one_canonical_shift_milestone_stream():
    assignment = assignments_for_day(2)[0]
    events = planned_shift_milestones(assignment)

    assert tuple(event["event_type"] for event in events) == SHIFT_MILESTONE_TYPES
    assert len({event["event_id"] for event in events}) == 3
    assert all(event["shift_assignment_id"] == event["target_id"] for event in events)
    assert all(event["session_id"].startswith("sim:worker-session:") for event in events)


def test_prior_night_shift_handoffs_and_clock_outs_are_in_next_day_plan():
    events = planned_events_for_day(1)
    early_handoffs = [event for event in events
                      if event["event_type"] == "handoff" and event["minute"] < 7 * 60]
    early_clock_outs = [event for event in events
                        if event["event_type"] == "clock_out" and event["minute"] <= 7 * 60]
    assert len(early_handoffs) == 5
    assert len(early_clock_outs) == 5
    assert {event["department"] for event in early_clock_outs} == {
        "nursing", "maintenance", "front_desk"
    }
    assert all(event["assignment_day_index"] == 0 for event in early_clock_outs)
    assert all(event["handoff_to_actor_ids"] for event in early_handoffs)


def test_coverage_gap_events_are_system_observations_with_truthful_boundaries():
    events = planned_events_for_day(0)
    gaps = [event for event in events if event["event_type"].startswith("coverage_gap")]
    assert all(event["actor_id"] == "system:simulation_planner" for event in gaps)
    assert all(event["actor_type"] == "system" and not event["actor_simulated"] for event in gaps)

    present = {event["department"] for event in gaps if event["event_type"] == "coverage_gap_present"}
    assert present == {"kitchen", "housekeeping", "transportation", "activities", "administration"}
    assert next(event for event in gaps if event["department"] == "kitchen"
                and event["event_type"] == "coverage_gap_ended")["time"] == "05:30"
    assert next(event for event in gaps if event["department"] == "transportation"
                and event["event_type"] == "coverage_gap_started")["time"] == "15:00"
    assert not [event for event in gaps if event["department"] in {"nursing", "maintenance", "front_desk"}]


def test_handoff_lists_only_workers_covering_the_same_department_at_shift_end():
    events = planned_events_for_day(3)
    nursing = next(event for event in events
                   if event["event_type"] == "handoff"
                   and event["department"] == "nursing" and event["time"] == "13:45")
    assert nursing["handoff_to_actor_ids"]
    assert all(actor_id.startswith("sim:staff:nursing:") for actor_id in nursing["handoff_to_actor_ids"])

    transport = next(event for event in events
                     if event["event_type"] == "handoff"
                     and event["department"] == "transportation")
    assert transport["handoff_to_actor_ids"] == []


def test_invalid_day_lead_and_department_are_rejected():
    with pytest.raises(ValueError):
        planned_events_for_day(-1)
    with pytest.raises(ValueError):
        planned_events_for_day(0, handoff_lead_minutes=-1)
    with pytest.raises(ValueError):
        planned_events_for_day(0, departments=("nursing", "ghost"))
