"""Truthful composition tests for the living-community admin preview."""
from simulation.community_view import community_overview, community_preview


def test_overview_declares_scale_without_claiming_execution():
    view = community_overview(day_index=0, minute=8 * 60)
    assert view["execution_status"] == "planning_only"
    assert "not yet" in view["truth_statement"]
    assert view["residents"] == {"count": 10, "burn_in_target": 10, "target": 75}
    assert view["apartments"] == {"total": 80, "occupied": 70, "occupancy_target": 70}
    assert view["workers"] == {"count": 50, "simulated": True}
    assert view["worker_attendance"] == {
        "scheduled": 32,
        "off_duty": 18,
        "planned_login": 32,
        "assignment_acceptance": 32,
        "canonical_shift_events_reported_under": "shift_events",
        "executed": 0,
        "truth": "Planned only; not authenticated, executed, or receipted.",
    }
    assert view["shift_events"] == {
        "clock_in": 32,
        "clock_out": 32,
        "coverage_gap_ended": 5,
        "coverage_gap_present": 5,
        "coverage_gap_started": 5,
        "handoff": 32,
        "executed": 0,
    }
    assert view["routines"]["planned"] == 153
    assert view["routines"]["executed"] == 0
    assert view["routines"]["planned_refused"] > 0
    assert view["routines"]["planned_rescheduled"] > 0


def test_all_departments_and_real_coverage_gaps_are_visible():
    view = community_overview(day_index=0, minute=8 * 60)
    departments = {row["slug"]: row for row in view["departments"]}
    assert set(departments) == {
        "nursing", "kitchen", "housekeeping", "maintenance",
        "transportation", "activities", "front_desk", "administration",
    }
    assert departments["nursing"]["worker_count"] == 26
    assert departments["nursing"]["coverage_24h"] is True
    assert departments["front_desk"]["coverage_24h"] is True
    assert departments["activities"]["coverage_24h"] is False
    assert "not real-world staffing" in view["coverage_disclaimer"]


def test_preview_is_inspectable_and_keeps_provider_boundaries_blocked():
    preview = community_preview(day_index=0, minute=0)
    assert len(preview["resident_keys"]) == 10
    assert len(preview["routine_events"]) == 153
    assert len(preview["planned_outcomes"]) == 153
    assert all(not row["represents_execution"] for row in preview["planned_outcomes"])
    assert preview["shift_assignments"]
    assert len(preview["worker_attendance"]) == 50
    assert sum(row["attendance_state"] == "scheduled" for row in preview["worker_attendance"]) == 32
    assert all(row["execution_state"] == "not_executed" for row in preview["worker_attendance"])
    assert preview["planned_shift_events"]
    assert all(event["execution_state"] == "not_executed" for event in preview["planned_shift_events"])
    attendance_shift_events = {
        event["event_id"]: event
        for state in preview["worker_attendance"]
        for event in state["milestones"]
        if event["stream_kind"] == "canonical_shift_milestone"
    }
    day_shift_events = {
        event["event_id"]: event for event in preview["planned_shift_events"]
        if event["stream_kind"] == "canonical_shift_milestone"
    }
    shared_ids = attendance_shift_events.keys() & day_shift_events.keys()
    assert shared_ids
    assert all(attendance_shift_events[event_id] == day_shift_events[event_id]
               for event_id in shared_ids)
    reminders = [
        event for event in preview["routine_events"]
        if "medication_reminder" in event["routine"]
    ]
    assert len(reminders) == 20
    assert all("never medication administration" in event["truth_boundary"] for event in reminders)
    blocked = {row["id"] for row in preview["overview"]["blocked_capabilities"]}
    assert {
        "medication_kiosk", "transport_resource_booking", "outbound_family_call",
        "menu_content_publish", "activity_schedule_publish", "resident_alert",
    } <= blocked


def test_overview_rejects_out_of_projection_coordinates():
    for kwargs in ({"day_index": -1}, {"day_index": 90}, {"minute": -1}, {"minute": 1440}):
        try:
            community_overview(**kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {kwargs}")
