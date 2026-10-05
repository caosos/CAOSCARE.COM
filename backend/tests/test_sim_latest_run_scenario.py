"""Scenario-aware latest/active run: db.sim_runs also holds runs that other
writers register (RQ-001 demo continuity, scenario "demo_continuity",
always STOPPED). The Operations Simulator's latest/active run and its
state view must only ever be one of its own scenarios; the other run's
history stays readable.

    cd backend && MONGO_URL=mongodb://localhost:27017 DB_NAME=caoscare_simlr_test \
      JWT_SECRET=x pytest tests/test_sim_latest_run_scenario.py -q
"""
import asyncio
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes sim_runs; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from simulation import scenario, scheduler  # noqa: E402

TAG = f"simlr_{uuid.uuid4().hex[:8]}"
CONTINUITY = "demo_continuity"   # backend/demo_continuity.py RUN_SCENARIO


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _run_doc(suffix, scen, state, created):
    return {"run_id": f"simrun_{TAG}_{suffix}", "scenario": scen, "state": state, "cursor": 0,
            "sim_minute": 0, "workflow": {}, "cast": {}, "origin_receipt_id": f"rcpt_{TAG}_{suffix}",
            "created_at": created, "updated_at": created}


@pytest.fixture(autouse=True)
def isolate():
    # Park every other run so this test's far-future runs decide the ordering.
    saved = run(db.sim_runs.find({"run_id": {"$not": {"$regex": f"^simrun_{TAG}"}}},
                                 {"_id": 0, "run_id": 1, "state": 1}).to_list(10000))
    run(db.sim_runs.update_many({"run_id": {"$in": [r["run_id"] for r in saved]}},
                                {"$set": {"state": scheduler.STOPPED}}))
    yield
    run(db.sim_runs.delete_many({"run_id": {"$regex": f"^simrun_{TAG}"}}))
    run(db.receipts.delete_many({"receipt_id": {"$regex": f"^rcpt_{TAG}"}}))
    for r in saved:
        run(db.sim_runs.update_one({"run_id": r["run_id"]}, {"$set": {"state": r["state"]}}))


def test_continuity_run_is_never_the_simulator_run():
    assert CONTINUITY not in scenario.SCENARIO_IDS
    ops = _run_doc("ops", scenario.SCENARIO_ID, scheduler.STOPPED, "2999-01-01T00:00:00+00:00")
    cont = _run_doc("cont", CONTINUITY, scheduler.STOPPED, "2999-06-01T00:00:00+00:00")   # newer
    run(db.sim_runs.insert_many([dict(ops), dict(cont)]))
    run(db.receipts.insert_one({"receipt_id": f"rcpt_{TAG}_cont", "correlation_id": cont["origin_receipt_id"],
                                "action_type": "demo_continuity_started", "created_at": cont["created_at"]}))

    # latest_run / view pick the Operations Simulator run, not the newer continuity run.
    assert run(scheduler.latest_run())["run_id"] == ops["run_id"]
    v = run(scheduler.view())
    assert v["run_id"] == ops["run_id"] and v["scenario"] == scenario.SCENARIO_ID
    # Handing view() the continuity run does not surface it either.
    assert run(scheduler.view(dict(cont)))["run_id"] == ops["run_id"]

    # Even a (hypothetically) active continuity run is not the active simulator run.
    run(db.sim_runs.update_one({"run_id": cont["run_id"]}, {"$set": {"state": scheduler.RUNNING}}))
    assert run(scheduler.active_run()) is None
    run(db.sim_runs.update_one({"run_id": cont["run_id"]}, {"$set": {"state": scheduler.STOPPED}}))

    # Its history is intact and still readable by run id.
    h = run(scheduler.history(cont["run_id"]))
    assert h["run"]["scenario"] == CONTINUITY
    assert [r["receipt_id"] for r in h["run_chain"]] == [f"rcpt_{TAG}_cont"]
    assert run(db.sim_runs.count_documents({"run_id": {"$regex": f"^simrun_{TAG}"}})) == 2


def test_only_a_continuity_run_means_no_simulator_run(monkeypatch):
    # Self-contained: scope the simulator to a scenario id only this test
    # uses, so runs already in the scratch DB cannot affect it.
    monkeypatch.setattr(scenario, "SCENARIO_IDS", (f"only_{TAG}",))
    run(db.sim_runs.insert_one(_run_doc("cont2", CONTINUITY, scheduler.STOPPED, "2999-06-01T00:00:00+00:00")))
    assert run(scheduler.latest_run()) is None
    v = run(scheduler.view())
    assert v["run_id"] is None and v["state"] == scheduler.STOPPED
