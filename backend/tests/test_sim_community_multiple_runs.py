"""Several runs per community, one active at a time (owner decision 2026-10-14).

A stopped run keeps its tasks and receipts as history; a new run can then be
created, provisioned and started beside it. Creating a run while another is
RUNNING or PAUSED is refused.
"""
import asyncio

import pytest

from routes.actor_context import ActorContext
from simulation import community_run_lifecycle as lifecycle
from tests.community_realtime_harness import AUTHORITY, NOW, RealtimeAcceptanceHarness

OWNER = ActorContext(actor_id="user:michael", actor_type="real-human", identity_basis="authenticated",
                     channel="staff_ui", name="Michael", role="owner", simulated=False)


def test_new_run_after_a_stopped_run_keeps_the_old_one():
    async def scenario():
        harness = RealtimeAcceptanceHarness(OWNER)
        await harness.create_and_provision()
        await harness.resume("first-resume")
        await harness.tick_next()
        old_id = harness.run_id
        await harness.stop("first-stop")
        old_tasks = [t for t in harness.store.staff_tasks.docs if t.get("simulation_run_id") == old_id]

        second = await harness.controls.create_paused(OWNER, AUTHORITY, "second-create", now=NOW)
        new_id = second["run"]["run_id"]
        assert new_id != old_id and second["run"]["state"] == "PAUSED"
        harness.run_id = new_id
        resumed = await harness.resume("second-resume")
        assert resumed["run"]["state"] == "RUNNING"
        states = {row["run_id"]: row["state"] for row in harness.store.sim_runs.docs}
        assert states == {old_id: "STOPPED", new_id: "RUNNING"}
        # The stopped run's records are untouched history.
        assert [t for t in harness.store.staff_tasks.docs if t.get("simulation_run_id") == old_id] == old_tasks
    asyncio.run(scenario())


def test_create_is_refused_while_another_run_is_active():
    async def scenario():
        harness = RealtimeAcceptanceHarness(OWNER)
        await harness.create_and_provision()
        with pytest.raises(lifecycle.CommunityRunLifecycleError, match="still PAUSED"):
            await harness.controls.create_paused(OWNER, AUTHORITY, "while-paused", now=NOW)
    asyncio.run(scenario())
