"""A process that dies mid-tick must not wedge the community (2026-10-14).

The executor was stopped while it held the run's execution lease; the lease
expired but stayed on the run, and both the clock advance and Stop refused
("stale state" / "remained leased") forever. An expired lease is not held:
its holder can no longer commit (cursor commits revalidate a live lease).
"""
import asyncio
from datetime import timedelta

import pytest

from routes.actor_context import ActorContext
from simulation import community_run_lifecycle as lifecycle
from simulation.community_control_service import CommunityControlError, runner_actor
from tests.community_realtime_harness import NOW, RealtimeAcceptanceHarness

OWNER = ActorContext(actor_id="user:michael", actor_type="real-human", identity_basis="authenticated",
                     channel="staff_ui", name="Michael", role="owner", simulated=False)


def _lease(expires):
    return {"holder_id": "community-process:dead:1", "fence": 99, "mode": "runner",
            "acquired_at": (expires - timedelta(seconds=30)).isoformat(),
            "heartbeat_at": (expires - timedelta(seconds=30)).isoformat(),
            "expires_at": expires.isoformat()}


async def _running_with_lease(expires):
    harness = RealtimeAcceptanceHarness(OWNER)
    await harness.create_and_provision()
    await harness.resume("lease-resume")
    harness.store.sim_runs.docs[0]["execution_lease"] = _lease(expires)
    return harness


def test_stop_succeeds_over_an_expired_lease_and_removes_it():
    async def scenario():
        harness = await _running_with_lease(NOW - timedelta(minutes=5))
        stopped = await harness.stop("stop-over-expired")
        assert stopped["run"]["state"] == "STOPPED"
        assert "execution_lease" not in harness.store.sim_runs.docs[0]
    asyncio.run(scenario())


def test_stop_still_refuses_a_live_lease():
    async def scenario():
        harness = await _running_with_lease(NOW + timedelta(minutes=5))
        with pytest.raises(CommunityControlError, match="remained leased"):
            await harness.stop("stop-over-live")
    asyncio.run(scenario())


def test_clock_advances_over_an_expired_lease():
    async def scenario():
        harness = await _running_with_lease(NOW - timedelta(minutes=5))
        row = await harness.run_row()
        moved = await lifecycle.advance_simulated_clock(
            runner_actor(), f"simulation_run:{harness.run_id}:clock", harness.run_id,
            row["cursor"], row["sim_minute"], row["sim_minute"] + 5, "clock-over-expired",
            harness.plan, store=harness.store, now=NOW,
        )
        assert moved["run"]["sim_minute"] == row["sim_minute"] + 5
        assert "execution_lease" not in harness.store.sim_runs.docs[0]
    asyncio.run(scenario())
