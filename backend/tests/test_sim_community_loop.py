"""Focused proof for the unattended living-community loop core."""

import asyncio
from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from simulation import community_loop as loop
from simulation.community_runner import CommunityRunnerError, TickResult


NOW = datetime(2026, 10, 13, 18, 0, tzinfo=timezone.utc)


def result(status, cursor=0, *, action="none", event_id=None, receipt_id=None):
    return TickResult(
        "run-1", status, action, event_id, receipt_id,
        cursor, cursor + (action != "none"), 1, action == "advance_cursor_from_receipt",
    )


class World:
    def __init__(self, **changes):
        self.row = {
            "run_id": "run-1", "state": "RUNNING", "cursor": 0,
            "sim_minute": 10,
        }
        self.row.update(changes)
        self.now = NOW
        self.advance_to = self.row["sim_minute"]
        self.advances = []

    def clock(self):
        return self.now

    async def load(self, *, run_id):
        assert run_id == self.row["run_id"]
        return deepcopy(self.row)

    async def advance(self, **call):
        self.advances.append(call)
        assert call["observed_run"] == self.row
        self.row["sim_minute"] = min(call["horizon_minutes"], self.advance_to)
        return deepcopy(self.row)

    async def complete(self, **call):
        assert call["observed_run"] == self.row
        self.row.update(
            state="STOPPED", sim_minute=call["horizon_minutes"],
            terminal_reason="completed", completion_receipt_id="receipt-complete",
        )
        return deepcopy(self.row)


class GateSleep:
    def __init__(self):
        self.calls = []
        self.entered = asyncio.Event()

    async def __call__(self, delay):
        self.calls.append(delay)
        self.entered.set()
        await asyncio.Event().wait()


async def until(predicate, attempts=500):
    for _ in range(attempts):
        if predicate():
            return
        await asyncio.sleep(0)
    raise AssertionError("condition was not reached")


def manager(world, tick, *, sleep=asyncio.sleep, **config):
    return loop.CommunityLoopManager(
        store=object(), timeline=object(), services=object(),
        load_run=world.load, advance_sim_clock=world.advance,
        complete_run=world.complete,
        tick=tick, clock=world.clock, sleep=sleep,
        config=loop.LoopConfig(**config),
    )


def test_paused_run_resumes_without_advancing_while_paused():
    async def case():
        world = World(state="PAUSED")
        calls = []

        async def tick(*_args, **_kwargs):
            cursor = world.row["cursor"]
            calls.append(cursor)
            world.row["cursor"] += 1
            world.row["state"] = "PAUSED" if cursor == 0 else "STOPPED"
            return result(
                "executed", cursor, action="execute_event_then_advance",
                event_id=f"event-{cursor}", receipt_id=f"receipt-{cursor}",
            )

        control = manager(world, tick, poll_seconds=0.01)
        assert control.start("run-1", "loop-a") is True
        await until(lambda: control.status("run-1").phase == "paused")
        assert calls == [] and world.advances == []

        world.row["state"] = "RUNNING"
        control.wake("run-1")
        await until(lambda: control.status("run-1").events_executed == 1)
        await until(lambda: control.status("run-1").phase == "paused")
        assert calls == [0]

        world.row["state"] = "RUNNING"
        control.wake("run-1")
        status = await control.wait("run-1")
        assert calls == [0, 1]
        assert status.phase == "stopped" and status.events_executed == 2
    asyncio.run(case())


def test_cancellation_waits_for_an_inflight_fenced_tick_then_stops():
    async def case():
        world = World()
        tick_started, release_tick = asyncio.Event(), asyncio.Event()

        async def tick(*_args, **_kwargs):
            tick_started.set()
            await release_tick.wait()
            return result("future")

        control = manager(world, tick)
        control.start("run-1", "loop-a")
        await tick_started.wait()
        cancellation = asyncio.create_task(control.cancel("run-1"))
        await asyncio.sleep(0)
        assert cancellation.done() is False
        release_tick.set()
        status = await cancellation
        assert status.phase == "cancelled"
        assert status.ticks_started == status.ticks_finished == 1
    asyncio.run(case())


def test_only_one_process_local_loop_can_own_a_run():
    async def case():
        world = World()
        entered, release = asyncio.Event(), asyncio.Event()

        async def tick(*_args, **_kwargs):
            entered.set()
            await release.wait()
            world.row["state"] = "STOPPED"
            return result("executed", action="execute_event_then_advance")

        first, second = manager(world, tick), manager(world, tick)
        assert first.start("run-1", "loop-a") is True
        await entered.wait()
        assert first.start("run-1", "loop-b") is False
        assert second.start("run-1", "loop-c") is False
        release.set()
        await first.wait("run-1")
        await asyncio.sleep(0)
        assert second.start("run-1", "loop-c") is True
        await second.wait("run-1")
    asyncio.run(case())


def test_restart_drains_receipted_event_before_new_due_work():
    async def case():
        world = World(cursor=4, sim_minute=500)
        seen = []

        async def tick(*_args, **_kwargs):
            cursor = world.row["cursor"]
            seen.append(cursor)
            world.row["cursor"] += 1
            if cursor == 4:
                return result(
                    "advanced", cursor, action="advance_cursor_from_receipt",
                    event_id="event-4", receipt_id="receipt-before-restart",
                )
            world.row["state"] = "STOPPED"
            return result(
                "executed", cursor, action="execute_event_then_advance",
                event_id="event-5", receipt_id="receipt-after-restart",
            )

        control = manager(world, tick)
        control.start("run-1", "replacement-loop")
        status = await control.wait("run-1")
        assert seen == [4, 5]
        assert status.receipts_recovered == 1
        assert status.events_executed == 1 and status.cursor == 6
    asyncio.run(case())


@pytest.mark.parametrize(
    "outcome,phase,delay",
    [
        ("blocked", "blocked", 11.0),
        ("inconsistent", "inconsistent", 7.0),
        ("error", "error", 7.0),
    ],
)
def test_blocked_and_error_states_back_off_without_busy_spinning(outcome, phase, delay):
    async def case():
        world, sleeping = World(), GateSleep()
        calls = 0

        async def tick(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            if outcome == "inconsistent":
                raise CommunityRunnerError("timeline reconciliation is inconsistent")
            if outcome == "error":
                raise RuntimeError("canonical service unavailable")
            return result("blocked")

        control = manager(
            world, tick, sleep=sleeping,
            blocked_backoff_seconds=11.0, error_backoff_seconds=7.0,
        )
        control.start("run-1", "loop-a")
        await sleeping.entered.wait()
        status = control.status("run-1")
        assert status.phase == phase and calls == 1
        assert sleeping.calls == [delay]
        if outcome != "blocked":
            assert status.error_count == status.consecutive_errors == 1
            assert outcome in status.last_error.lower()
        else:
            assert status.blocked_count == 1
        await control.cancel("run-1")
    asyncio.run(case())


def test_ticks_are_strictly_serial_even_when_woken_repeatedly():
    async def case():
        world = World()
        entered, release = asyncio.Event(), asyncio.Event()
        active = maximum = calls = 0

        async def tick(*_args, **_kwargs):
            nonlocal active, maximum, calls
            calls += 1
            active += 1
            maximum = max(maximum, active)
            entered.set()
            await release.wait()
            active -= 1
            world.row["state"] = "STOPPED"
            return result("executed", action="execute_event_then_advance")

        control = manager(world, tick)
        control.start("run-1", "loop-a")
        await entered.wait()
        for _ in range(20):
            control.wake("run-1")
        assert control.start("run-1", "loop-b") is False
        await asyncio.sleep(0)
        assert calls == maximum == 1
        release.set()
        await control.wait("run-1")
        assert calls == maximum == 1
    asyncio.run(case())


def test_completion_persists_exact_90_day_boundary_and_status_is_read_only():
    async def case():
        world = World(cursor=24_030, sim_minute=loop.HORIZON_MINUTES - 1)

        async def tick(*_args, **_kwargs):
            return result("complete", world.row["cursor"])

        control = manager(world, tick, acceleration=120.0)
        control.start("run-1", "loop-a")
        status = await control.wait("run-1")
        assert status.phase == "complete"
        assert status.run_state == "STOPPED"
        assert status.sim_minute == 90 * 24 * 60
        assert world.row["state"] == "STOPPED"
        assert status.last_receipt_id == "receipt-complete"
        assert world.advances[0]["acceleration"] == 120.0
        with pytest.raises(FrozenInstanceError):
            status.phase = "forged"
        assert status.last_tick_status == "complete" and status.finished_at
    asyncio.run(case())


@pytest.mark.parametrize("bad", [0, -1, True])
def test_invalid_acceleration_fails_before_any_loop_starts(bad):
    with pytest.raises(loop.CommunityLoopError, match="positive"):
        loop.LoopConfig(acceleration=bad)
