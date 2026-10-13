"""Pure tests for the 50-worker living-community simulation load."""
from datetime import date

import pytest

from simulation.community_staffing import (
    DEPARTMENT_LABELS,
    SIMULATION_LOAD_DISCLAIMER,
    WORKERS,
    active_assignments,
    assignments_for_day,
    coverage_summary,
    minute_in_shift,
    project_schedule,
)


EXPECTED_HEADCOUNT = {
    "nursing": 26,
    "kitchen": 6,
    "housekeeping": 4,
    "maintenance": 3,
    "transportation": 2,
    "activities": 2,
    "front_desk": 5,
    "administration": 2,
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
    assert len(day_zero) == 32
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
    assert {(row["department"], row["shift"]) for row in at_two_am} == {
        ("nursing", "night"), ("maintenance", "night"), ("front_desk", "night")
    }
    assert all(row["day_index"] == 0 for row in at_two_am)
    assert {row["department"] for row in active_assignments(0, 2 * 60)} == {
        "nursing", "maintenance", "front_desk"
    }


def test_default_projection_is_exactly_90_repeatable_local_days():
    first = project_schedule(date(2026, 10, 13))
    second = project_schedule("2026-10-13", days=90)
    assert first == second
    assert len(first) == 90 * 32
    assert first[0]["date"] == "2026-10-13"
    assert {row["date"] for row in first} == {
        (date(2026, 10, 13).fromordinal(date(2026, 10, 13).toordinal() + day)).isoformat()
        for day in range(90)
    }
    overnight = next(row for row in first if row["shift_key"] == "front_desk:night")
    assert overnight["spans_midnight"] is True
    assert overnight["starts_at"] == "2026-10-13T22:00:00"
    assert overnight["ends_at"] == "2026-10-14T06:00:00"


def test_coverage_summary_reports_real_gaps_not_invented_coverage():
    overnight = coverage_summary(1, 2 * 60)
    assert overnight["coverage"]["nursing"]["on_shift"] == 3
    assert overnight["coverage"]["maintenance"]["on_shift"] == 1
    assert overnight["coverage"]["front_desk"]["on_shift"] == 1
    assert overnight["gaps"] == [
        "kitchen", "housekeeping", "transportation", "activities", "administration"
    ]
    assert overnight["disclaimer"] == SIMULATION_LOAD_DISCLAIMER
    assert "not real-world staffing" in overnight["disclaimer"]

    midday = coverage_summary(1, 12 * 60)
    assert midday["gaps"] == []
    assert all(item["on_shift"] > 0 for item in midday["coverage"].values())


def test_invalid_projection_and_coverage_inputs_are_rejected():
    with pytest.raises(ValueError):
        project_schedule("2026-10-13", days=0)
    with pytest.raises(ValueError):
        assignments_for_day(-1)
    with pytest.raises(ValueError):
        active_assignments(0, -1)
    with pytest.raises(ValueError, match="unknown departments"):
        coverage_summary(0, 0, departments=("nursing", "ghost"))
