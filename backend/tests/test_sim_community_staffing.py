"""Pure tests for the 50-worker living-community simulation load."""
from collections import defaultdict
from datetime import date

import pytest

from simulation.community_staffing import (
    DEPARTMENT_LABELS,
    MAX_SCHEDULED_DAYS_PER_ROLLING_WEEK,
    SIMULATION_LOAD_DISCLAIMER,
    WORKERS,
    active_assignments,
    assignments_for_day,
    coverage_summary,
    minute_in_shift,
    planned_coverage_gaps,
    project_schedule,
)


EXPECTED_HEADCOUNT = {
    "nursing": 22,
    "kitchen": 4,
    "housekeeping": 4,
    "maintenance": 4,
    "transportation": 4,
    "activities": 4,
    "front_desk": 4,
    "administration": 4,
}


def test_roster_has_50_stable_explicit_simulated_identities():
    assert len(WORKERS) == 50
    assert len({worker["actor_id"] for worker in WORKERS}) == 50
    assert {department: sum(w["department"] == department for w in WORKERS)
            for department in EXPECTED_HEADCOUNT} == EXPECTED_HEADCOUNT
    assert all(worker["actor_id"].startswith("sim:staff:") for worker in WORKERS)
    assert all(worker["actor_type"] == "simulated-agent" for worker in WORKERS)
    assert all(worker["identity_basis"] == "synthetic" and worker["simulated"] for worker in WORKERS)
    assert all("user_id" not in worker for worker in WORKERS)
    assert set(DEPARTMENT_LABELS) == set(EXPECTED_HEADCOUNT)


def test_daily_assignment_is_deterministic_rotating_and_one_shift_per_worker():
    day_zero = assignments_for_day(0)
    assert day_zero == assignments_for_day(0)
    assert len(day_zero) == 38
    assert len({row["actor_id"] for row in day_zero}) == len(day_zero)
    assert {row["actor_id"] for row in day_zero if row["job_role"] == "care_aide"} != {
        row["actor_id"] for row in assignments_for_day(1) if row["job_role"] == "care_aide"
    }


def test_overnight_windows_wrap_and_prior_day_workers_remain_active():
    assert minute_in_shift(23 * 60 + 30, 22 * 60, 6 * 60)
    assert minute_in_shift(2 * 60, 22 * 60, 6 * 60)
    assert not minute_in_shift(12 * 60, 22 * 60, 6 * 60)
    with pytest.raises(ValueError):
        minute_in_shift(1440, 0, 60)

    at_two_am = active_assignments(1, 2 * 60)
    assert {row["department"] for row in at_two_am} == set(DEPARTMENT_LABELS)
    assert {row["shift"] for row in at_two_am} == {"night"}
    assert all(row["day_index"] == 0 for row in at_two_am)
    assert {row["department"] for row in active_assignments(0, 2 * 60)} == set(DEPARTMENT_LABELS)


def test_default_projection_is_exactly_90_repeatable_local_days():
    first = project_schedule(date(2026, 10, 13))
    second = project_schedule("2026-10-13", days=90)
    assert first == second
    assert len(first) == 90 * 38
    assert first[0]["date"] == "2026-10-13"
    assert {row["date"] for row in first} == {
        (date(2026, 10, 13).fromordinal(date(2026, 10, 13).toordinal() + day)).isoformat()
        for day in range(90)
    }
    overnight = next(row for row in first if row["shift_key"] == "front_desk:night")
    assert overnight["spans_midnight"] is True
    assert overnight["starts_at"] == "2026-10-13T22:00:00"
    assert overnight["ends_at"] == "2026-10-14T06:00:00"


def test_coverage_summary_reports_proven_zero_gaps_without_invented_execution():
    overnight = coverage_summary(1, 2 * 60)
    assert overnight["coverage"]["nursing"]["on_shift"] == 4
    assert overnight["coverage"]["maintenance"]["on_shift"] == 1
    assert overnight["coverage"]["front_desk"]["on_shift"] == 1
    assert overnight["gaps"] == []
    assert overnight["disclaimer"] == SIMULATION_LOAD_DISCLAIMER
    assert "not real-world staffing" in overnight["disclaimer"]
    assert overnight["coverage_tradeoffs"] == []
    assert overnight["planned_rota_gaps"] == planned_coverage_gaps(1) == []

    midday = coverage_summary(1, 12 * 60)
    assert midday["gaps"] == []
    assert all(item["on_shift"] > 0 for item in midday["coverage"].values())


def test_every_worker_gets_rest_in_each_rolling_week():
    scheduled_days = defaultdict(set)
    for day_index in range(90):
        for assignment in assignments_for_day(day_index):
            scheduled_days[assignment["actor_id"]].add(day_index)

    assert set(scheduled_days) == {worker["actor_id"] for worker in WORKERS}
    for worker in WORKERS:
        days = scheduled_days[worker["actor_id"]]
        assert len(days) < 90
        assert all(
            sum(day in days for day in range(start, start + 7))
            <= MAX_SCHEDULED_DAYS_PER_ROLLING_WEEK
            for start in range(90 - 7 + 1)
        )



def test_all_shifts_are_exactly_eight_hours_with_continuous_handoffs():
    for day_index in range(90):
        assignments = assignments_for_day(day_index)
        for assignment in assignments:
            duration = (assignment["end_minute"] - assignment["start_minute"]) % 1440
            assert duration == 8 * 60

        by_department = defaultdict(list)
        for assignment in assignments:
            by_department[assignment["department"]].append(assignment)
        assert set(by_department) == set(DEPARTMENT_LABELS)
        for department, rows in by_department.items():
            windows = {(row["start"], row["end"]) for row in rows}
            assert windows >= {
                ("06:00", "14:00"), ("14:00", "22:00"), ("22:00", "06:00")
            }, department


def test_all_departments_are_covered_every_minute_for_full_90_days():
    expected = set(DEPARTMENT_LABELS)
    for day_index in range(90):
        assert planned_coverage_gaps(day_index) == []
        for minute in range(1440):
            active = active_assignments(day_index, minute)
            assert len(active) == len({row["actor_id"] for row in active})
            covered = {row["department"] for row in active}
            assert covered == expected, (day_index, minute, expected - covered)


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
