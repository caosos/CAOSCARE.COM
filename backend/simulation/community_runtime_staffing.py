"""Runtime staffing projection at a run's persisted simulated time.

Read-only and deterministic: who is on site, who is on call, and each
department's ON DUTY / ON CALL / CLOSED / UNCOVERED status.  No writes.
"""
from simulation.community_coverage import coverage_summary
from simulation.community_staffing import (
    DEPARTMENT_LABELS, active_assignments, on_call_assignments,
)


def _worker_rows(rows: list[dict]) -> list[dict]:
    keys = ("actor_id", "name", "department", "department_label", "job_role", "shift")
    return [{key: row[key] for key in keys} for row in rows]


def staffing_at(absolute_minute: int) -> dict:
    """Who is on site / on call and each department's status at one minute."""
    day_index, minute = divmod(absolute_minute, 1440)
    coverage = coverage_summary(day_index, minute)
    return {
        "status": "loaded",
        "basis": "deterministic_schedule_at_persisted_simulated_time",
        "day_index": day_index,
        "minute": minute,
        "workers": _worker_rows(active_assignments(day_index, minute)),
        "on_call_workers": _worker_rows(on_call_assignments(day_index, minute)),
        "coverage": coverage["coverage"],
        "gaps": coverage["gaps"],
    }


def staffing_projection(run: dict, run_view: dict) -> dict:
    if run_view["status"] != "loaded":
        return {"status": "error", "basis": "deterministic_schedule_at_persisted_simulated_time",
                "day_index": None, "minute": None, "workers": [], "coverage": None, "gaps": None}
    time = run_view["simulated_time"]
    if time["absolute_minute"] == 90 * 1440:
        # The 90-day run has ended: no simulated staff exist, and nothing is
        # "uncovered" because there is no community left to staff.
        coverage = {
            key: {"label": label, "status": "simulation_complete", "on_shift": 0,
                  "actor_ids": [], "job_roles": [], "on_call": 0, "on_call_actor_ids": []}
            for key, label in DEPARTMENT_LABELS.items()
        }
        return {
            "status": "loaded",
            "basis": "deterministic_schedule_at_persisted_simulated_time",
            "day_index": 90, "minute": 0, "workers": [], "on_call_workers": [],
            "coverage": coverage, "gaps": [],
        }
    return staffing_at(time["absolute_minute"])
