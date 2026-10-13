"""Focused tests for planned-only deterministic community outcomes."""

import inspect

import pytest

from simulation import community_outcomes
from simulation.community_dispatch import QUEUED_UNASSIGNED
from simulation.community_outcomes import PLANNED_ONLY, OUTCOMES, plan_routine_outcomes
from simulation.community_routines import plan_first_24_hours


def test_outcomes_are_deterministic_complete_and_planned_only():
    events = plan_first_24_hours()
    first = plan_routine_outcomes(events)
    second = plan_routine_outcomes(events)

    assert first == second
    assert len(first) == len(events)
    assert [outcome.event_id for outcome in first] == [event.event_id for event in events]
    assert {outcome.planned_disposition for outcome in first} == set(OUTCOMES)
    assert all(outcome.evidence_label == PLANNED_ONLY for outcome in first)
    assert all(outcome.represents_execution is False for outcome in first)
    assert all(0 <= outcome.planned_resolution_minute < 24 * 60 for outcome in first)


def test_uncovered_work_is_queued_unassigned_not_planned_completed():
    outcomes = plan_routine_outcomes()
    queued = [
        outcome for outcome in outcomes
        if outcome.planned_disposition == QUEUED_UNASSIGNED
    ]

    assert len(queued) == 5
    assert {outcome.routine for outcome in queued} == {"family_call_coordination"}
    assert all(outcome.dispatch_state == QUEUED_UNASSIGNED for outcome in queued)
    assert all(outcome.assigned_actor_id is None for outcome in queued)
    assert all(
        (outcome.queued_until_day_index, outcome.queued_until_minute) == (1, 8 * 60)
        for outcome in queued
    )
    assert all(outcome.planned_resolution_day_index == 1 for outcome in queued)
    assert all("queued and unassigned" in outcome.summary.lower() for outcome in queued)
    assert all("no work has been completed" in outcome.truth_boundary.lower() for outcome in queued)
    assert not {
        outcome.event_id for outcome in queued
    } & {
        outcome.event_id for outcome in outcomes
        if outcome.planned_disposition == "completed"
    }


def test_reschedules_link_to_original_and_stay_in_first_day():
    by_id = {event.event_id: event for event in plan_first_24_hours()}
    reschedules = [
        outcome for outcome in plan_routine_outcomes(by_id.values())
        if outcome.planned_disposition == "resident_requested_reschedule"
    ]

    assert reschedules
    assert len({outcome.rescheduled_event_id for outcome in reschedules}) == len(reschedules)
    for outcome in reschedules:
        original = by_id[outcome.event_id]
        assert outcome.rescheduled_event_id == f"{outcome.event_id}:rescheduled-1"
        assert original.minute < outcome.rescheduled_to_minute < 24 * 60
        assert outcome.rescheduled_to_hhmm is not None


def test_medication_results_stop_at_reminder_truth():
    medication = [
        outcome for outcome in plan_routine_outcomes()
        if "medication_reminder" in outcome.routine
    ]

    assert medication
    for outcome in medication:
        assert "medication use remains unknown" in outcome.summary.lower()
        assert "reminder outcome only" in outcome.truth_boundary.lower()
        assert "never infer medication administration" in outcome.truth_boundary.lower()
        assert "medication was taken" not in outcome.summary.lower()
        assert "dose administered" not in outcome.summary.lower()


def test_meal_results_do_not_claim_consumption():
    meals = [
        outcome for outcome in plan_routine_outcomes()
        if outcome.routine in ("breakfast", "lunch", "dinner")
    ]
    assert meals
    assert all("food intake remains unknown" in outcome.summary.lower() for outcome in meals)
    assert all("never infer what or how much" in outcome.truth_boundary.lower() for outcome in meals)


def test_module_has_no_database_or_provider_dependency_and_validates_inputs():
    source = inspect.getsource(community_outcomes)
    assert "from deps import" not in source
    assert "import db" not in source
    assert "httpx" not in source
    assert "requests" not in source

    with pytest.raises(ValueError):
        plan_routine_outcomes(seed="")
    event = plan_first_24_hours()[0]
    with pytest.raises(ValueError):
        plan_routine_outcomes((event, event))
