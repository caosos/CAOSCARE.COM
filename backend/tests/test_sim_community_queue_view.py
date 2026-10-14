"""SIM-006 Live Operations queue: waits, worker availability and backlog."""
import asyncio

from simulation import community_queue_view as view
from simulation.community_runtime_staffing import staffing_at
from simulation.community_timeline import PLAN_REVISIONS


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, _limit):
        return list(self.rows)


class Tasks:
    def __init__(self, rows, fail=False):
        self.rows, self.fail = rows, fail

    def find(self, query, _projection):
        if self.fail:
            raise RuntimeError("database address hidden")
        return Cursor([row for row in self.rows if row["status"] == query["status"]
                       and row["simulation_run_id"] == query["simulation_run_id"]])


class Runs:
    async def find_one(self, _query, _projection):
        return {"plan_revision": PLAN_REVISIONS["burn_in_10"]}


class Store:
    def __init__(self, rows, fail=False):
        self.staff_tasks, self.sim_runs = Tasks(rows, fail), Runs()


MINUTE = 8 * 60 + 10 + 90           # breakfast for resident-001 was requested at 08:10
ON_SITE = staffing_at(MINUTE)["workers"]
AIDE = next(row for row in ON_SITE if row["job_role"] == "care_aide")
COOK = next(row for row in ON_SITE if row["department"] == "kitchen")


def _task(task_id, status, workflow, category, assigned_to=None, run="run-1"):
    return {"task_id": task_id, "status": status, "category": category, "priority": "normal",
            "summary": "s", "resident_id": "sim:resident:001", "assigned_to": assigned_to,
            "simulation_run_id": run, "conversation_session_id": f"simulator:event:{workflow}"}


def _snapshot(rows, minute, fail=False, next_event=None):
    return asyncio.run(view.queue_snapshot(run_id="run-1", clock_minute=minute,
                                           next_event_minute=next_event, store=Store(rows, fail)))


def test_queued_tickets_show_simulated_wait_and_worker_availability():
    breakfast = "day-000:resident-001:breakfast"   # requested 08:10
    rows = [_task("t-wait", "pending", breakfast, "kitchen"),
            _task("t-work", "in_progress", "day-000:resident-001:morning_room_check",
                  "nursing", AIDE["actor_id"]),
            _task("t-other-run", "pending", breakfast, "kitchen", run="run-0")]
    out = _snapshot(rows, MINUTE)
    (queued,) = out["queued"]
    assert queued["task_id"] == "t-wait" and queued["requested_at_minute"] == 490
    assert queued["waiting_minutes"] == 90 and queued["overdue"] is True
    assert out["departments"]["kitchen"]["queued"] == 1
    assert out["departments"]["kitchen"]["longest_wait_minutes"] == 90
    nursing = out["departments"]["nursing"]
    assert (nursing["busy"], nursing["in_progress"]) == (1, 1)
    assert nursing["free"] == nursing["on_site"] - 1
    by_id = {row["actor_id"]: row for row in out["workers"]}
    assert by_id[AIDE["actor_id"]]["availability"] == "busy"
    assert by_id[AIDE["actor_id"]]["task_id"] == "t-work"
    assert by_id[COOK["actor_id"]]["availability"] == "free"
    assert out["anomalies"] == [] and out["executor_behind_clock_minutes"] == 0


def test_a_second_active_ticket_or_off_site_holder_is_shown_as_an_anomaly():
    rows = [_task("a", "in_progress", "w1", "nursing", AIDE["actor_id"]),
            _task("b", "in_progress", "w2", "nursing", AIDE["actor_id"]),
            _task("c", "in_progress", "w3", "kitchen", "sim:staff:kitchen:gone")]
    kinds = {row["kind"] for row in _snapshot(rows, MINUTE)["anomalies"]}
    assert kinds == {"worker_holds_multiple_active_tickets", "active_ticket_held_by_off_site_worker"}


def test_failed_reads_stay_unknown_not_zero():
    out = _snapshot([], 600, fail=True)
    assert out["status"] == "error" and out["queued"] is None and out["workers"] is None
    assert "address" not in str(out)


def test_executor_lag_is_reported_not_shown_as_longer_waits():
    rows = [_task("t-wait", "pending", "day-000:resident-001:breakfast", "kitchen")]
    out = _snapshot(rows, MINUTE + 600, next_event=MINUTE)
    assert out["as_of_minute"] == MINUTE and out["executor_behind_clock_minutes"] == 600
    assert out["queued"][0]["waiting_minutes"] == 90
