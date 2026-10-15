"""A real staff member covers a simulated worker's shift; the run keeps going."""
import asyncio
from copy import deepcopy

import pytest

from routes.actor_context import ActorContext
from simulation import community_shift_cover as cover
from simulation.community_runtime_staffing import staffing_at
from simulation.community_ticket_plan import CLAIM, COMPLETE
from tests.test_sim_community_execution_adapter import Store, context, event, harness, task

MICHAEL = ActorContext(actor_id="user_michael", actor_type="real-human", identity_basis="authenticated",
                       channel="staff_ui", name="Michael", role="owner", simulated=False)
MINUTE = 8 * 60
AIDE = next(row for row in staffing_at(MINUTE)["workers"] if row["job_role"] == "care_aide")


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, _limit):
        return deepcopy(self.rows)


class Rows:
    def __init__(self, rows=()):
        self.rows = [dict(row) for row in rows]

    def _match(self, row, query):
        return all(row.get(key) == value for key, value in query.items())

    async def find_one(self, query, _projection=None):
        return next((deepcopy(row) for row in self.rows if self._match(row, query)), None)

    def find(self, query, _projection=None):
        return Cursor([row for row in self.rows if self._match(row, query)])

    async def insert_one(self, row):
        self.rows.append(dict(row))

    async def update_one(self, query, update):
        for row in self.rows:
            if self._match(row, query):
                row.update(update["$set"])
                return


class CoverStore:
    def __init__(self, state="RUNNING"):
        self.sim_runs = Rows([{"run_id": "run-1", "simulation_scope": "living_community",
                               "state": state, "sim_minute": MINUTE}])
        self.sim_shift_covers = Rows()
        self.staff_tasks = Rows()


def _writer(log):
    async def write(**kwargs):
        log.append(kwargs)
        return {"receipt_id": f"rcpt-cover-{len(log)}"}
    return write


def test_cover_and_hand_back_are_receipted_with_the_real_person():
    async def case():
        store, log = CoverStore(), []
        row = await cover.start_cover(store, _writer(log), run_id="run-1",
                                      worker_actor_id=AIDE["actor_id"], actor=MICHAEL)
        assert row["covered_by_name"] == "Michael" and row["start_receipt_id"] == "rcpt-cover-1"
        assert log[0]["action_type"] == "sim_shift_cover_started"
        assert log[0]["provenance"]["actor_type"] == "real-human"
        assert await cover.active_cover(store, "run-1", AIDE["actor_id"])
        with pytest.raises(cover.ShiftCoverError, match="already covered"):
            await cover.start_cover(store, _writer(log), run_id="run-1",
                                    worker_actor_id=AIDE["actor_id"], actor=MICHAEL)
        ended = await cover.end_cover(store, _writer(log), run_id="run-1",
                                      worker_actor_id=AIDE["actor_id"], actor=MICHAEL)
        assert ended["ended_at_sim_minute"] == MINUTE
        assert await cover.active_cover(store, "run-1", AIDE["actor_id"]) is None
    asyncio.run(case())


def test_only_an_on_site_worker_of_a_live_run_can_be_covered():
    async def case():
        with pytest.raises(cover.ShiftCoverError, match="not on site"):
            await cover.start_cover(CoverStore(), _writer([]), run_id="run-1",
                                    worker_actor_id="sim:staff:maintenance:ghost", actor=MICHAEL)
        with pytest.raises(cover.ShiftCoverError, match="no running or paused"):
            await cover.start_cover(CoverStore("STOPPED"), _writer([]), run_id="run-1",
                                    worker_actor_id=AIDE["actor_id"], actor=MICHAEL)
    asyncio.run(case())


def _covered_store(item, ctx, **task_changes):
    store = Store(tasks=[task(item, ctx, **task_changes)])
    store.sim_shift_covers.rows.append({
        "run_id": ctx.run_id, "worker_actor_id": item.actor_id, "ended_at_sim_minute": None,
        "covered_by_name": "Michael", "start_receipt_id": "rcpt-cover-1"})
    return store


def test_covered_worker_leaves_the_ticket_in_the_queue_then_completion_follows():
    async def case():
        claim, ctx = event(task_phase=CLAIM), context()
        store = _covered_store(claim, ctx)
        services, calls = harness(store)
        proof = await services.execute_event(event=claim, context=ctx)
        assert proof["status"] == "cancelled" and calls["start"] == []
        assert proof["next_state"] == "left_for_covering_staff"
        assert store.staff_tasks.rows[0]["status"] == "pending"
        store.sim_shift_covers.rows.clear()          # cover ended; the ticket still waits
        complete = event(task_phase=COMPLETE)
        done = await services.execute_event(event=complete, context=context(cursor=4))
        assert done["status"] == "cancelled" and done["next_state"] == "left_in_queue"
        assert calls["complete"] == [] and store.staff_tasks.rows[0]["status"] == "pending"
    asyncio.run(case())


def test_cover_uses_the_moment_work_has_reached_not_a_run_clock_far_ahead(monkeypatch):
    """CO-008: the executor lagged (clock day 19 at night, work done to day 13
    mid-morning); a worker on site at the worked moment can be covered."""
    import simulation.community_dashboard_view as view
    monkeypatch.setattr(view, "executed_position", lambda run: MINUTE)

    async def case():
        store, log = CoverStore(), []
        store.sim_runs.rows[0]["sim_minute"] = MINUTE + 6 * 1440 + 18 * 60      # 02:00 six days later
        assert not any(r["actor_id"] == AIDE["actor_id"]
                       for r in staffing_at(store.sim_runs.rows[0]["sim_minute"])["workers"])
        row = await cover.start_cover(store, _writer(log), run_id="run-1",
                                      worker_actor_id=AIDE["actor_id"], actor=MICHAEL)
        assert row["started_at_sim_minute"] == MINUTE
        ended = await cover.end_cover(store, _writer(log), run_id="run-1",
                                      worker_actor_id=AIDE["actor_id"], actor=MICHAEL)
        assert ended["ended_at_sim_minute"] == MINUTE
    asyncio.run(case())


def test_a_worker_mid_ticket_cannot_be_covered(monkeypatch):
    """CO-008: covering mid-ticket orphaned the ticket and stopped the run."""
    import simulation.community_dashboard_view as view
    monkeypatch.setattr(view, "executed_position", lambda run: MINUTE)

    async def case():
        store, log = CoverStore(), []
        store.staff_tasks.rows.append({"simulation_run_id": "run-1", "assigned_to": AIDE["actor_id"],
                                       "status": "in_progress", "task_id": "t-busy", "title": "Shower assistance"})
        with pytest.raises(cover.ShiftCoverError, match="in the middle of a ticket"):
            await cover.start_cover(store, _writer(log), run_id="run-1", worker_actor_id=AIDE["actor_id"], actor=MICHAEL)
        assert log == [] and store.sim_shift_covers.rows == []
        store.staff_tasks.rows[0]["status"] = "completed"
        row = await cover.start_cover(store, _writer(log), run_id="run-1", worker_actor_id=AIDE["actor_id"], actor=MICHAEL)
        assert row["covered_by_name"] == "Michael"
    asyncio.run(case())
