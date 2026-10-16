"""Focused proof for default-off living-community startup recovery."""

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_run_lifecycle import RUN_KIND
from simulation.community_startup_recovery import (
    CommunityStartupRecoveryCoordinator,
    CommunityStartupRecoveryError,
    StartupRecoveryConfig,
    bounded_runner_reconciler,
)
from simulation.community_startup_capability import shared_capability_probe
from simulation.community_index_contract import REQUIRED_INDEXES


NOW = datetime(2026, 10, 13, 18, 30, tzinfo=timezone.utc)


def capability(*, transactions=True, indexes=True, controls=True, extra=()):
    required = [
        {"name": row["name"], "status": "ready" if indexes else "missing"}
        for row in REQUIRED_INDEXES
    ]
    blockers = list(extra)
    if not controls:
        blockers.append({"code": "controls_not_enabled"})
    if not transactions:
        blockers.append({"code": "transactions_unavailable"})
    if not indexes:
        blockers.append({"code": "required_indexes_unavailable"})
    return {
        "schema_version": 1,
        "controls_enabled": controls,
        "transaction_probe": {"supported": transactions},
        "index_probe": {"ready": indexes, "required": required},
        "mutations_allowed": controls and transactions and indexes,
        "blockers": blockers,
    }


def _matches(row, query):
    return all(row.get(key) == value for key, value in query.items())


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, limit):
        rows = self.rows if limit is None else self.rows[:limit]
        return deepcopy(rows)


class Collection:
    def __init__(self, rows=()):
        self.rows = [deepcopy(row) for row in rows]
        self.find_calls = 0
        self.insert_calls = 0

    def find(self, query, projection=None):
        self.find_calls += 1
        rows = [row for row in self.rows if _matches(row, query)]
        if projection and projection.get("_id") == 0:
            rows = [{key: value for key, value in row.items() if key != "_id"} for row in rows]
        return Cursor(rows)

    async def find_one(self, query, projection=None):
        rows = [row for row in self.rows if _matches(row, query)]
        if not rows:
            return None
        row = deepcopy(rows[0])
        if projection and projection.get("_id") == 0:
            row.pop("_id", None)
        return row

    async def insert_one(self, row):
        self.insert_calls += 1
        if any(existing.get("_id") == row.get("_id") for existing in self.rows):
            raise AssertionError("test attempted a duplicate receipt insert")
        self.rows.append(deepcopy(row))


class Store:
    def __init__(self, runs=()):
        self.sim_runs = Collection(runs)
        self.receipts = Collection()


class LoopManager:
    def __init__(self):
        self.starts = []
        self.cancelled = []
        self.active = {}

    def start(self, run_id, holder_id):
        self.starts.append((run_id, holder_id))
        if run_id in self.active:
            return False
        self.active[run_id] = SimpleNamespace(finished_at=None)
        return True

    def status(self, run_id):
        return self.active.get(run_id)

    async def cancel(self, run_id):
        self.cancelled.append(run_id)
        status = self.active.pop(run_id, None)
        if status:
            status.finished_at = NOW.isoformat()
        return status


def run_row(state="RUNNING", run_id="run-1", **changes):
    row = {
        "_id": run_id,
        "run_id": run_id,
        "state": state,
        "cursor": 7,
        "sim_minute": 480,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "run_kind": RUN_KIND,
        "origin_receipt_id": f"receipt:{run_id}:origin",
        "last_transition_receipt_id": f"receipt:{run_id}:resume",
    }
    row.update(changes)
    return row


class Harness:
    def __init__(self, runs=(None,), *, enabled=True, capability_value=None):
        actual = [run_row() if row is None else row for row in runs]
        self.store = Store(actual)
        self.loop = LoopManager()
        self.probes = self.advances = self.reconciles = 0
        self.capability = capability_value or capability()
        self.reconcile_error = None
        self.advance_to = None
        self.config = StartupRecoveryConfig(
            enabled=enabled, startup_id="service-start-123", holder_id="runner-a",
        )

    async def probe(self):
        self.probes += 1
        return self.capability

    async def advance(self, **call):
        self.advances += 1
        row = deepcopy(call["observed_run"])
        assert call["observed_at"] == NOW
        if self.advance_to is not None:
            row["sim_minute"] = self.advance_to
            self.store.sim_runs.rows[0]["sim_minute"] = self.advance_to
        return row

    async def reconcile(self, run_id, holder_id, *, now):
        self.reconciles += 1
        assert (run_id, holder_id, now) == ("run-1", "runner-a", NOW)
        if self.reconcile_error:
            error, self.reconcile_error = self.reconcile_error, None
            raise error
        row = self.store.sim_runs.rows[0]
        return SimpleNamespace(
            run_id=run_id, status="future", action="none", receipt_id=None,
            cursor_before=row["cursor"], cursor_after=row["cursor"],
        )

    def coordinator(self):
        return CommunityStartupRecoveryCoordinator(
            store=self.store, loop_manager=self.loop,
            capability_probe=self.probe, advance_sim_clock=self.advance,
            reconcile_tick=self.reconcile, config=self.config, clock=lambda: NOW,
        )


def execute(awaitable):
    return asyncio.run(awaitable)


def test_cold_start_reconciles_once_starts_one_loop_and_chains_receipts():
    harness = Harness()
    result = execute(harness.coordinator().recover())

    assert result.status == "started" and result.loop_started is True
    assert result.reconcile_status == "future"
    assert harness.probes == harness.advances == harness.reconciles == 1
    assert harness.loop.starts == [("run-1", "runner-a")]
    assert len(harness.store.receipts.rows) == 2
    requested, started = harness.store.receipts.rows
    assert requested["action_type"] == "simulation_community_startup_recovery_requested"
    assert requested["parent_receipt_id"] == "receipt:run-1:resume"
    assert started["action_type"] == "simulation_community_startup_recovery_started"
    assert started["parent_receipt_id"] == requested["receipt_id"]
    assert started["actor_id"] == "system:living-community-startup-recovery"
    assert started["authority"] == "simulation_run:run-1:startup-recovery"
    assert started["after_state"]["reconcile"]["cursor_before"] == 7


def test_repeated_startup_call_returns_same_proof_without_second_tick_or_loop():
    harness = Harness()
    coordinator = harness.coordinator()

    first = execute(coordinator.recover())
    second = execute(coordinator.recover())

    assert second.idempotent_replay is True
    assert second.decision_receipt_id == first.decision_receipt_id
    assert second.outcome_receipt_id == first.outcome_receipt_id
    assert harness.probes == harness.advances == harness.reconciles == 1
    assert len(harness.loop.starts) == 1
    assert len(harness.store.receipts.rows) == 2


@pytest.mark.parametrize("rows", [[], [run_row("PAUSED")], [run_row("STOPPED")]])
def test_no_running_run_does_not_reconcile_write_or_start(rows):
    harness = Harness(rows)
    result = execute(harness.coordinator().recover())

    assert result.status == "no_running_run"
    assert harness.probes == 1
    assert harness.advances == harness.reconciles == 0
    assert harness.loop.starts == [] and harness.store.receipts.rows == []


@pytest.mark.parametrize(
    "capability,expected",
    [
        (capability(transactions=False), "transactions_unavailable"),
        (capability(indexes=False), "required_indexes_unavailable"),
        (capability(transactions=False, indexes=False,
                    extra=({"code": "probe_failed"},)), "probe_failed"),
    ],
)
def test_failed_capability_gate_performs_no_database_or_loop_work(capability, expected):
    harness = Harness(capability_value=capability)
    result = execute(harness.coordinator().recover())

    assert result.status == "blocked" and expected in result.blockers
    assert harness.store.sim_runs.find_calls == 0
    assert harness.store.receipts.rows == [] and harness.loop.starts == []
    assert harness.advances == harness.reconciles == 0


def test_default_off_performs_no_probe_database_or_loop_work():
    harness = Harness(enabled=False)
    result = execute(harness.coordinator().recover())

    assert result.status == "disabled"
    assert harness.probes == 0 and harness.store.sim_runs.find_calls == 0
    assert harness.store.receipts.rows == [] and harness.loop.starts == []


def test_crash_after_requested_receipt_retries_without_duplicate_history():
    harness = Harness()
    harness.advance_to = 481
    harness.reconcile_error = RuntimeError("injected crash")
    coordinator = harness.coordinator()

    with pytest.raises(RuntimeError, match="injected crash"):
        execute(coordinator.recover())
    assert len(harness.store.receipts.rows) == 1
    assert harness.loop.starts == []

    result = execute(coordinator.recover())
    assert result.status == "started"
    assert harness.reconciles == 2 and len(harness.store.receipts.rows) == 2
    assert harness.store.receipts.insert_calls == 2


def test_duplicate_exact_running_runs_fail_closed_before_receipts_or_loop():
    harness = Harness([run_row(run_id="run-1"), run_row(run_id="run-2")])

    with pytest.raises(CommunityStartupRecoveryError, match="multiple exact RUNNING"):
        execute(harness.coordinator().recover())
    assert harness.advances == harness.reconciles == 0
    assert harness.store.receipts.rows == [] and harness.loop.starts == []


def test_receipted_cursor_recovery_may_advance_exactly_one_event():
    harness = Harness()

    async def recovered(run_id, holder_id, *, now):
        harness.reconciles += 1
        harness.store.sim_runs.rows[0]["cursor"] = 8
        return SimpleNamespace(
            run_id=run_id, status="advanced",
            action="advance_cursor_from_receipt", receipt_id="receipt:event-7",
            cursor_before=7, cursor_after=8,
        )

    coordinator = CommunityStartupRecoveryCoordinator(
        store=harness.store, loop_manager=harness.loop,
        capability_probe=harness.probe, advance_sim_clock=harness.advance,
        reconcile_tick=recovered, config=harness.config, clock=lambda: NOW,
    )
    result = execute(coordinator.recover())

    assert result.status == "started" and result.reconcile_status == "advanced"
    proof = harness.store.receipts.rows[-1]["after_state"]["reconcile"]
    assert proof["cursor_after"] == 8 and proof["receipt_id"] == "receipt:event-7"


def test_cursor_advance_without_receipt_is_refused_before_loop_start():
    harness = Harness()

    async def invalid(run_id, holder_id, *, now):
        return SimpleNamespace(
            run_id=run_id, status="advanced", action="none", receipt_id=None,
            cursor_before=7, cursor_after=8,
        )

    coordinator = CommunityStartupRecoveryCoordinator(
        store=harness.store, loop_manager=harness.loop,
        capability_probe=harness.probe, advance_sim_clock=harness.advance,
        reconcile_tick=invalid, config=harness.config, clock=lambda: NOW,
    )
    with pytest.raises(CommunityStartupRecoveryError, match="status/action"):
        execute(coordinator.recover())
    assert harness.loop.starts == []


def test_bounded_runner_adapter_passes_only_injected_boundaries():
    calls = []

    async def tick(run_id, holder_id, **kwargs):
        calls.append((run_id, holder_id, kwargs))
        return "proof"

    store, timeline, services = object(), object(), object()

    def clock():
        return NOW

    reconcile = bounded_runner_reconciler(
        store=store, timeline=timeline, services=services, tick=tick,
        clock=clock,
    )
    assert execute(reconcile("run-1", "runner-a", now=NOW)) == "proof"
    assert calls == [("run-1", "runner-a", {
        "store": store, "timeline": timeline, "services": services, "now": NOW,
        "clock": clock,
    })]


def test_shared_capability_adapter_passes_only_the_injected_store(monkeypatch):
    monkeypatch.setenv("CAOSCARE_LIVING_COMMUNITY_CONTROLS", "true")
    calls, store = [], object()

    async def probe(value):
        calls.append(value)
        return capability()

    adapted = shared_capability_probe(store=store, probe=probe)
    assert execute(adapted())["mutations_allowed"] is True
    assert calls == [store]


def test_shared_capability_adapter_never_probes_when_controls_are_off(monkeypatch):
    monkeypatch.delenv("CAOSCARE_LIVING_COMMUNITY_CONTROLS", raising=False)
    calls, store = [], object()

    async def probe(value):
        calls.append(value)
        raise AssertionError("disabled startup must not probe storage")

    result = execute(shared_capability_probe(store=store, probe=probe)())
    assert result["mutations_allowed"] is False
    assert calls == []
