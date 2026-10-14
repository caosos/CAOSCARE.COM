"""Pure tests for the 50-worker living-community staffing model.

Owner direction (Michael, 2026-10-13): 80-apartment, budget-constrained
assisted living.  Overnight 2-3 care staff on site; maintenance normal hours
plus after-hours ON-CALL (never on site 24 h); other departments keep
realistic hours and are CLOSED otherwise; statuses must be truthful.
"""
from collections import Counter, defaultdict
from datetime import date

import pytest

from simulation.community_coverage import (
    AFTER_HOURS_ON_CALL,
    CLOSED,
    DEPARTMENT_STATUSES,
    ON_CALL,
    ON_DUTY,
    OPERATING_HOURS,
    UNCOVERED,
    coverage_summary,
    department_status,
    is_open,
    planned_coverage_gaps,
)
from simulation.community_staffing import (
    DEPARTMENT_LABELS,
    MAX_SCHEDULED_DAYS_PER_ROLLING_WEEK,
    MIN_REST_BETWEEN_DUTIES_MINUTES,
    SIMULATION_LOAD_DISCLAIMER,
    WORKERS,
    active_assignments,
    assignments_for_day,
    minute_in_shift,
    on_call_assignments,
    project_schedule,
    worker_statuses,
)


EXPECTED_HEADCOUNT = {
    "nursing": 22, "kitchen": 4, "housekeeping": 4, "maintenance": 4,
    "transportation": 4, "activities": 4, "front_desk": 4, "administration": 4,
}
OVERNIGHT_MINUTES = list(range(22 * 60, 1440, 15)) + list(range(0, 6 * 60, 15))
CARE_ROLES = {"care_aide", "medication_reminder_support"}


def _windows(row):
    start = row["day_index"] * 1440 + row["start_minute"]
    end = row["day_index"] * 1440 + row["end_minute"] + (1440 if row["spans_midnight"] else 0)
    return start, end


def test_roster_keeps_50_stable_explicit_simulated_identities():
    assert len(WORKERS) == 50
    assert len({worker["actor_id"] for worker in WORKERS}) == 50
    assert {d: sum(w["department"] == d for w in WORKERS) for d in EXPECTED_HEADCOUNT} == EXPECTED_HEADCOUNT
    assert all(worker["actor_id"].startswith("sim:staff:") for worker in WORKERS)
    assert all(worker["actor_type"] == "simulated-agent" for worker in WORKERS)
    assert all(worker["identity_basis"] == "synthetic" and worker["simulated"] for worker in WORKERS)
    assert all("user_id" not in worker for worker in WORKERS)
    assert set(DEPARTMENT_LABELS) == set(EXPECTED_HEADCOUNT) == set(OPERATING_HOURS)


def test_every_worker_is_accounted_for_with_exactly_one_truthful_status():
    roster = {worker["actor_id"] for worker in WORKERS}
    scheduled = {row["actor_id"] for day in range(90) for row in assignments_for_day(day)}
    assert scheduled == roster  # nobody invented, nobody left out of the rota
    for day_index in (0, 1, 45, 89):
        for minute in range(0, 1440, 30):
            rows = worker_statuses(day_index, minute)
            assert [row["actor_id"] for row in rows] == [w["actor_id"] for w in WORKERS]
            assert {row["status"] for row in rows} <= {"on_duty", "on_call", "off_duty"}
            on_site = {row["actor_id"] for row in active_assignments(day_index, minute)}
            assert {row["actor_id"] for row in rows if row["physically_present"]} == on_site
            assert all(row["status"] == "on_duty" for row in rows if row["physically_present"])
            assert not any(row["physically_present"] for row in rows if row["status"] == "on_call")


def test_two_to_three_care_workers_are_on_site_every_overnight_minute():
    for day_index in range(90):
        for minute in OVERNIGHT_MINUTES:
            nursing = [row for row in active_assignments(day_index, minute)
                       if row["department"] == "nursing"]
            assert 2 <= len(nursing) <= 3, (day_index, minute)
            assert {row["job_role"] for row in nursing} <= CARE_ROLES
            assert coverage_summary(day_index, minute)["coverage"]["nursing"]["status"] == ON_DUTY
    # The overnight RN is reachable on call, not counted as present.
    on_call = [row for row in on_call_assignments(1, 3 * 60) if row["department"] == "nursing"]
    assert [row["job_role"] for row in on_call] == ["registered_nurse"]


def test_maintenance_works_normal_hours_with_truthful_after_hours_on_call():
    assert AFTER_HOURS_ON_CALL == {"maintenance"}
    for day_index in range(90):
        for minute in range(0, 1440, 15):
            here = [r for r in active_assignments(day_index, minute) if r["department"] == "maintenance"]
            reachable = [r for r in on_call_assignments(day_index, minute) if r["department"] == "maintenance"]
            status = coverage_summary(day_index, minute)["coverage"]["maintenance"]["status"]
            if 7 * 60 <= minute < 15 * 60 + 30:
                assert len(here) == 1 and not reachable and status == ON_DUTY
            else:
                assert not here, "maintenance is never on site after hours"
                assert len(reachable) == 1 and status == ON_CALL
                assert {r["actor_id"] for r in reachable}.isdisjoint(
                    {r["actor_id"] for r in active_assignments(day_index, minute)})


def test_closed_departments_never_show_on_site_staff():
    for day_index in (0, 1, 30, 89):
        for minute in range(0, 1440, 10):
            summary = coverage_summary(day_index, minute)
            for department, item in summary["coverage"].items():
                assert item["status"] in DEPARTMENT_STATUSES
                if item["status"] == CLOSED:
                    assert item["on_shift"] == 0 and item["actor_ids"] == []
                    assert item["on_call"] == 0
                    assert not is_open(department, minute)
                assert (item["status"] == ON_DUTY) == (item["on_shift"] > 0)
    overnight = coverage_summary(1, 2 * 60)["coverage"]
    assert {d for d, item in overnight.items() if item["status"] == CLOSED} == {
        "kitchen", "housekeeping", "transportation", "activities", "front_desk", "administration",
    }


def test_uncovered_is_reported_only_for_genuine_gaps():
    # Real rota: zero uncovered windows in 90 days.
    assert all(planned_coverage_gaps(day) == [] for day in range(90))
    assert coverage_summary(1, 2 * 60)["gaps"] == []
    # The classifier flags a real gap: an open department, or a missing on-call.
    assert department_status("nursing", 3 * 60, on_site=0, on_call=1) == UNCOVERED
    assert department_status("kitchen", 12 * 60, on_site=0, on_call=0) == UNCOVERED
    assert department_status("maintenance", 2 * 60, on_site=0, on_call=0) == UNCOVERED
    assert department_status("maintenance", 2 * 60, on_site=0, on_call=1) == ON_CALL
    assert department_status("kitchen", 23 * 60, on_site=0, on_call=0) == CLOSED
    with pytest.raises(ValueError, match="unknown department"):
        department_status("ghost", 0, 0, 0)


def test_rest_days_and_rest_between_duties_are_honored():
    duties = defaultdict(list)
    for day_index in range(90):
        for row in assignments_for_day(day_index):
            duties[row["actor_id"]].append((*_windows(row), day_index))
    for actor_id, rows in duties.items():
        days = {row[2] for row in rows}
        assert len(days) < 90
        assert all(sum(day in days for day in range(start, start + 7))
                   <= MAX_SCHEDULED_DAYS_PER_ROLLING_WEEK for start in range(84)), actor_id
        ordered = sorted(rows)
        assert all(nxt[0] - cur[1] >= MIN_REST_BETWEEN_DUTIES_MINUTES
                   for cur, nxt in zip(ordered, ordered[1:])), actor_id


def test_daily_rota_is_deterministic_one_duty_per_worker_and_rotates():
    day_zero = assignments_for_day(0)
    assert day_zero == assignments_for_day(0)
    assert Counter(row["duty"] for row in day_zero) == {"on_site": 27, "on_call": 2}
    assert len({row["actor_id"] for row in day_zero}) == len(day_zero)
    aides = lambda day: {r["actor_id"] for r in assignments_for_day(day) if r["job_role"] == "care_aide"}
    assert aides(0) != aides(1)


def test_overnight_windows_wrap_and_prior_day_staff_remain_present():
    assert minute_in_shift(23 * 60 + 30, 22 * 60, 6 * 60)
    assert minute_in_shift(2 * 60, 22 * 60, 6 * 60)
    assert not minute_in_shift(12 * 60, 22 * 60, 6 * 60)
    with pytest.raises(ValueError):
        minute_in_shift(1440, 0, 60)
    at_two_am = active_assignments(1, 2 * 60)
    assert {row["department"] for row in at_two_am} == {"nursing"}
    assert all(row["day_index"] == 0 and row["shift"] == "night" for row in at_two_am)
    assert len(active_assignments(0, 2 * 60)) == 3  # carry-in night staff on day 0


def test_default_projection_is_exactly_90_repeatable_local_days():
    first = project_schedule(date(2026, 10, 13))
    assert first == project_schedule("2026-10-13", days=90)
    assert len(first) == 90 * 29
    assert first[0]["date"] == "2026-10-13"
    overnight = next(row for row in first if row["shift_key"] == "nursing:night")
    assert overnight["spans_midnight"] is True
    assert overnight["starts_at"] == "2026-10-13T22:00:00"
    assert overnight["ends_at"] == "2026-10-14T06:00:00"
    assert coverage_summary(1, 2 * 60)["disclaimer"] == SIMULATION_LOAD_DISCLAIMER


def test_invalid_projection_and_coverage_inputs_are_rejected():
    with pytest.raises(ValueError):
        project_schedule("2026-10-13", days=0)
    with pytest.raises(ValueError):
        assignments_for_day(-1)
    with pytest.raises(ValueError):
        planned_coverage_gaps(-1)
    with pytest.raises(ValueError):
        active_assignments(0, -1)
    with pytest.raises(ValueError, match="unknown departments"):
        coverage_summary(0, 0, departments=("nursing", "ghost"))
