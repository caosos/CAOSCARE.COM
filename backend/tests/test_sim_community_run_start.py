"""A real-time run starts on the facility clock without inventing the morning.

Michael, 2026-10-14: the simulator is for working a department live, not for
racing through days. Work planned before the start is receipted as not
simulated (one cancelled receipt each, cursor intact); work after it runs.
"""
import asyncio
from datetime import datetime, timezone

from routes.actor_context import ActorContext
from simulation.community_run_start import local_minute_of_day, origin_minute
from tests.community_realtime_harness import RealtimeAcceptanceHarness

OWNER = ActorContext(actor_id="user:michael", actor_type="real-human", identity_basis="authenticated",
                     channel="staff_ui", name="Michael", role="owner", simulated=False)
START = 9 * 60  # 09:00 facility time


def test_local_minute_is_facility_time():
    # 2026-10-15 02:30 UTC is 21:30 the evening before in Chicago (CDT).
    assert local_minute_of_day(datetime(2026, 10, 15, 2, 30, tzinfo=timezone.utc)) == 21 * 60 + 30


def test_run_starts_at_the_given_minute_and_receipts_earlier_work_as_not_simulated():
    async def scenario():
        harness = RealtimeAcceptanceHarness(OWNER)
        created = await harness.create_and_provision(start_minute=START)
        assert created["run"]["sim_minute"] == START and created["run"]["started_at_minute"] == START
        await harness.resume("start-resume")
        before = [e for e in harness.plan.events if origin_minute(e) < START]
        assert before, "the plan has work before 09:00"
        for event in before[:40]:
            result = await harness.tick_next()
            assert result.event_id == event.event_id
        receipts = [r for r in harness.store.receipts.docs
                    if r.get("result_label") == "not_simulated"]
        assert receipts and all(r["status"] == "cancelled" for r in receipts)
        assert all("before this run started at 09:00" in r["result"] for r in receipts)
        # Nothing was opened for work that predates the start.
        assert not [t for t in harness.store.staff_tasks.docs
                    if t.get("simulation_run_id") == harness.run_id]
        # The clock did not move backwards to reach early events.
        assert (await harness.run_row())["sim_minute"] >= START

    asyncio.run(scenario())


def test_work_after_the_start_runs_normally():
    async def scenario():
        harness = RealtimeAcceptanceHarness(OWNER)
        await harness.create_and_provision(start_minute=START)
        await harness.resume("start-resume-2")
        first_live = next(i for i, e in enumerate(harness.plan.events)
                          if origin_minute(e) >= START and e.task_phase == "open")
        for _ in range(first_live + 1):
            await harness.tick_next()
        opened = [t for t in harness.store.staff_tasks.docs if t.get("simulation_run_id") == harness.run_id]
        assert opened, "a ticket requested after 09:00 is opened"

    asyncio.run(scenario())
