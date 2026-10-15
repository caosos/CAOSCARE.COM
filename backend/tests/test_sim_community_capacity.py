"""SIM-006: one active ticket per on-site worker; excess work waits truthfully."""
import pytest

from simulation import community_capacity_schedule as capacity
from simulation.community_day_queue import cohort_schedule
from simulation.community_staffing import ON_SITE, _day_rota


def _schedule(*tickets, horizon=capacity.HORIZON_MINUTES):
    return capacity.schedule_tickets(tickets, horizon)


def _on_site_through(row) -> bool:
    for day in (row.claim_at // 1440 - 1, row.claim_at // 1440):
        for duty in _day_rota(day):
            if duty["actor_id"] != row.worker["actor_id"] or duty["duty"] != ON_SITE:
                continue
            start = day * 1440 + duty["start_minute"]
            end = day * 1440 + duty["end_minute"] + (1440 if duty["spans_midnight"] else 0)
            if start <= row.claim_at and row.complete_at <= end:
                return True
    return False


@pytest.mark.parametrize("cohort", ["burn_in_10", "community_75"])
def test_peak_active_tickets_per_worker_is_exactly_one(cohort):
    _routines, scheduled = cohort_schedule(cohort)
    rows = list(scheduled.values())
    assert set(capacity.peak_active_tickets(rows).values()) == {1}
    claimed = [row for row in rows if row.claim_at is not None]
    assert all(row.complete_at < capacity.HORIZON_MINUTES for row in claimed)
    assert all(_on_site_through(row) for row in claimed[:3000])


def test_full_community_backlog_waits_and_drains_truthfully():
    _routines, scheduled = cohort_schedule("community_75")
    rows = list(scheduled.values())
    reasons = {row.wait_reason for row in rows}
    # Room delivery staffing (v11) serves every meal in its window, so "not served" may be absent.
    assert reasons | {"not_served_service_window_closed"} == {capacity.NO_WAIT, capacity.STAFF_BUSY, capacity.DEPARTMENT_CLOSED,
                       capacity.ON_CALL_ONLY, capacity.ON_CALL_RESPONSE, capacity.UNCLAIMED_AT_END,
                       "not_served_service_window_closed",
                       # service model: an overnight snack/tray call while only the cook is on site
                       "waiting_for_qualified_staff"}
    # Queues drain: with resident calls and staff reports added (2026-10-14),
    # a non-urgent maintenance call can wait through closed hours until the
    # next on-site shift, but aged priority means nothing waits two days.
    # Owner (2026-10-15): one maintenance person, on site on business days and on call otherwise,
    # cannot keep up with the routine maintenance load. That shortage stays visible (no staff
    # are added to hide it); every other department, housekeeping included, drains.
    SHORT = {"maintenance"}
    assert max(row.waited_minutes or 0 for row in rows if row.department not in SHORT) < 2 * 1440
    for department in SHORT:
        assert max(row.waited_minutes or 0 for row in rows if row.department == department) > 2 * 1440
    unclaimed = [row for row in rows if row.wait_reason == capacity.UNCLAIMED_AT_END]
    assert unclaimed and all(row.requested_at >= 89 * 1440 for row in unclaimed if row.department not in SHORT)
    assert all(row.claim_at is None and row.worker is None for row in unclaimed)


def test_busy_staff_make_later_requests_wait_in_priority_order():
    at = 2 * 1440 + 8 * 60  # one maintenance technician is on site at 08:00
    rows = _schedule(("b", "maintenance", "normal", at, 3, "resident_call_light_out"),
                     ("a", "maintenance", "normal", at, 3, "resident_call_light_out"),
                     ("u", "maintenance", "urgent", at + 1, 3, "resident_call_light_out"))
    assert rows["a"].claim_at == at + 5 and rows["a"].wait_reason == capacity.NO_WAIT
    assert rows["u"].claim_at == at + 8 and rows["u"].wait_reason == capacity.STAFF_BUSY
    assert rows["b"].claim_at == at + 11 and rows["b"].waited_minutes == 6
    assert len({rows[key].worker["actor_id"] for key in "abu"}) == 1


def test_after_hours_maintenance_waits_for_on_site_staff_not_on_call():
    at = 1440 + 15 * 60 + 25  # eligible 15:30, when the technician leaves
    row = _schedule(("m", "maintenance", "normal", at, 10, "resident_call_light_out"))["m"]
    assert row.claim_at == 2 * 1440 + 7 * 60
    assert row.wait_reason == capacity.ON_CALL_ONLY


def test_closed_department_waits_for_opening_and_never_runs_past_close():
    at = 1440 + 19 * 60 + 52  # eligible 19:57; ten minutes would run past 20:00
    row = _schedule(("act", "activities", "normal", at, 10, "activity_follow_up"))["act"]
    assert row.claim_at == 2 * 1440 + 9 * 60
    assert row.wait_reason == capacity.DEPARTMENT_CLOSED


def test_requests_and_work_past_the_horizon_are_not_planned():
    horizon = 3 * 1440
    rows = _schedule(("late", "nursing", "normal", horizon - 6, 3, "night_room_check"),
                     ("after", "nursing", "normal", horizon, 3, "night_room_check"), horizon=horizon)
    assert "after" not in rows
    assert rows["late"].wait_reason == capacity.UNCLAIMED_AT_END


def test_schedule_is_deterministic():
    tickets = [(f"t{n}", "nursing", "normal", 1440 + 9 * 60, 8, "resident_call_help_up")
               for n in range(30)]
    assert _schedule(*tickets) == _schedule(*reversed(tickets))


@pytest.mark.parametrize("cohort", ["burn_in_10", "community_75"])
def test_execution_order_never_claims_for_a_worker_still_holding_a_ticket(cohort):
    """Replays the plan cursor by cursor as the persisted guard sees it."""
    from simulation.community_timeline import build_90_day_timeline

    holding = {}
    for event in build_90_day_timeline(cohort).events:
        if event.task_phase == "claim":
            assert event.actor_id not in holding, (event.event_id, holding.get(event.actor_id))
            holding[event.actor_id] = event.workflow_event_id
        elif event.task_phase == "complete":
            assert holding.pop(event.actor_id) == event.workflow_event_id
