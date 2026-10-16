"""Runtime staffing projection: truthful status at a run's simulated time."""
from simulation.community_runtime_staffing import staffing_projection


def _view(absolute_minute: int) -> dict:
    day_index, minute = divmod(absolute_minute, 1440)
    return {"status": "loaded", "simulated_time": {
        "absolute_minute": absolute_minute, "day_index": day_index, "minute": minute,
    }}


def test_overnight_projection_names_on_site_and_on_call_staff_separately():
    staffing = staffing_projection({}, _view(1440 + 2 * 60))
    coverage = staffing["coverage"]
    assert coverage["nursing"]["status"] == "on_duty" and coverage["nursing"]["on_shift"] == 3
    assert coverage["maintenance"]["status"] == "on_call"
    assert coverage["maintenance"]["on_shift"] == 0
    assert len(coverage["maintenance"]["on_call_actor_ids"]) == 1
    assert coverage["kitchen"]["status"] == "closed"
    assert staffing["gaps"] == []
    assert {row["department"] for row in staffing["workers"]} == {"nursing"}
    assert {row["department"] for row in staffing["on_call_workers"]} == {"nursing", "maintenance"}
    present = {row["actor_id"] for row in staffing["workers"]}
    assert present.isdisjoint(row["actor_id"] for row in staffing["on_call_workers"])


def test_completed_run_reports_no_staff_and_no_false_gaps():
    staffing = staffing_projection({}, _view(90 * 1440))
    assert staffing["workers"] == [] and staffing["on_call_workers"] == []
    assert staffing["gaps"] == []
    assert {item["status"] for item in staffing["coverage"].values()} == {"simulation_complete"}


def test_unloaded_run_stays_unknown():
    staffing = staffing_projection({}, {"status": "error"})
    assert staffing["status"] == "error" and staffing["coverage"] is None and staffing["gaps"] is None
