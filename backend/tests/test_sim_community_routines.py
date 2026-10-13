"""Pure contract tests for the living-community first-day routine plan."""

import pytest

from simulation.community_routines import (
    ADAPTER_CAPABILITIES,
    BLOCKED,
    BURN_IN_RESIDENT_KEYS,
    SAFE_NOW,
    blocked_adapters,
    plan_first_24_hours,
)


def test_first_day_plan_is_deterministic_ordered_and_bounded():
    first = plan_first_24_hours()
    second = plan_first_24_hours()

    assert first == second
    assert first == tuple(sorted(first, key=lambda event: (
        event.day_index, event.minute, event.resident_key, event.routine, event.event_id,
    )))
    assert {event.resident_key for event in first} == set(BURN_IN_RESIDENT_KEYS)
    assert len({event.event_id for event in first}) == len(first)
    assert all(0 <= event.minute < 24 * 60 for event in first)
    assert all(event.time_hhmm.count(":") == 1 for event in first)


def test_all_75_residents_have_bounded_minutes_and_explicit_rollover():
    resident_keys = tuple(f"resident-{index:03d}" for index in range(1, 76))
    events = plan_first_24_hours(resident_keys, day_index=0)

    assert {event.resident_key for event in events} == set(resident_keys)
    assert len({event.event_id for event in events}) == len(events)
    assert all(0 <= event.minute < 24 * 60 for event in events)
    assert all(event.plan_day_index == 0 for event in events)
    assert {event.day_index for event in events} == {0, 1}
    assert all(event.rollover_days in (0, 1) for event in events)
    assert events == tuple(sorted(events, key=lambda event: (
        event.absolute_minute, event.resident_key, event.routine, event.event_id,
    )))

    last_night_check = next(
        event for event in events
        if event.resident_key == "resident-075" and event.routine == "night_room_check"
    )
    assert (last_night_check.day_index, last_night_check.minute) == (1, 58)
    assert last_night_check.time_hhmm == "00:58"


def test_final_projection_day_preserves_next_day_drain_without_wrapping():
    resident_keys = tuple(f"resident-{index:03d}" for index in range(1, 76))
    events = plan_first_24_hours(resident_keys, day_index=89)
    drained = [event for event in events if event.day_index == 90]

    assert drained
    assert all(event.plan_day_index == 89 for event in events)
    assert {event.day_index for event in events} == {89, 90}
    assert all(0 <= event.minute < 24 * 60 for event in events)
    assert all(event.rollover_days == 1 for event in drained)
    assert all(event.event_id.startswith("day-089:") for event in drained)
    assert not any(event.day_index > 90 for event in events)


def test_plan_covers_departments_and_resident_routines():
    events = plan_first_24_hours()
    departments = {event.department for event in events}
    routines = {event.routine for event in events}

    assert departments == {
        "nursing", "kitchen", "housekeeping", "maintenance",
        "transportation", "activities", "administration",
    }
    assert {
        "shower_assistance", "morning_medication_reminder", "evening_medication_reminder",
        "breakfast", "lunch", "dinner", "toileting_transfer_support",
        "morning_room_check", "housekeeping_room_service", "activity_offer_and_escort",
        "appointment_coordination", "transport_coordination", "preventive_maintenance_check",
        "family_call_coordination",
    } <= routines
    for resident_key in BURN_IN_RESIDENT_KEYS:
        resident_routines = {event.routine for event in events if event.resident_key == resident_key}
        assert {"shower_assistance", "breakfast", "lunch", "dinner", "night_room_check"} <= resident_routines


def test_all_planned_events_use_safe_task_adapter_and_name_blocked_edges():
    events = plan_first_24_hours()

    assert ADAPTER_CAPABILITIES["canonical_staff_task"]["status"] == SAFE_NOW
    assert all(event.adapter_status == SAFE_NOW for event in events)
    assert set(blocked_adapters()) == {
        name for name, info in ADAPTER_CAPABILITIES.items() if info["status"] == BLOCKED
    }
    expected_edges = {
        "medication_kiosk", "transport_resource_booking", "outbound_family_call",
        "activity_schedule_publish",
    }
    assert expected_edges <= {event.blocked_adapter for event in events if event.blocked_adapter}


def test_clinical_and_operational_language_never_claims_unproven_outcomes():
    events = plan_first_24_hours()
    medication = [event for event in events if "medication_reminder" in event.routine]
    meals = [event for event in events if event.routine in ("breakfast", "lunch", "dinner")]
    rides = [event for event in events if event.routine == "transport_coordination"]
    calls = [event for event in events if event.routine == "family_call_coordination"]

    assert medication and all("reminder" in event.summary.lower() for event in medication)
    assert all("never medication administration" in event.truth_boundary.lower() for event in medication)
    assert all("never claims that the resident ate" in event.truth_boundary.lower() for event in meals)
    assert all("never claims a driver" in event.truth_boundary.lower() for event in rides)
    assert all("never claims that a call was placed" in event.truth_boundary.lower() for event in calls)
    forbidden_claims = ("medication was taken", "dose administered", "ride is booked", "call connected")
    assert not any(
        claim in event.summary.lower()
        for event in events
        for claim in forbidden_claims
    )


def test_resident_choice_and_input_validation_are_explicit():
    events = plan_first_24_hours()
    choice_events = [event for event in events if event.routine in {
        "shower_assistance", "activity_offer_and_escort", "housekeeping_room_service",
    }]
    assert choice_events
    assert all("resident_refused" in event.possible_outcomes for event in choice_events)
    assert all("resident_requested_reschedule" in event.possible_outcomes for event in choice_events)

    with pytest.raises(ValueError):
        plan_first_24_hours(())
    with pytest.raises(ValueError):
        plan_first_24_hours(("resident-001", "resident-001"))
    with pytest.raises(ValueError):
        plan_first_24_hours(day_index=-1)
