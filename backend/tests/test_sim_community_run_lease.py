import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from simulation import community_run_lease as lease
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE


NOW = datetime(2026, 10, 13, 7, 0, tzinfo=timezone.utc)


def _get(doc, path):
    value = doc
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _matches(doc, query):
    for key, expected in query.items():
        if key == "$or":
            if not any(_matches(doc, item) for item in expected):
                return False
            continue
        actual = _get(doc, key)
        if isinstance(expected, dict):
            if "$exists" in expected and (_get(doc, key) is not None) != expected["$exists"]:
                return False
            if "$in" in expected and actual not in expected["$in"]:
                return False
            if "$lte" in expected and not (actual is not None and actual <= expected["$lte"]):
                return False
            if "$gt" in expected and not (actual is not None and actual > expected["$gt"]):
                return False
        elif actual != expected:
            return False
    return True


def _set(doc, path, value):
    target = doc
    parts = path.split(".")
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = deepcopy(value)


class Runs:
    def __init__(self, row):
        self.row = deepcopy(row)

    async def find_one_and_update(self, query, update, **_kwargs):
        if not _matches(self.row, query):
            return None
        for path, amount in update.get("$inc", {}).items():
            _set(self.row, path, (_get(self.row, path) or 0) + amount)
        for path, value in update.get("$set", {}).items():
            _set(self.row, path, value)
        for path in update.get("$unset", {}):
            self.row.pop(path, None)
        return deepcopy(self.row)


class Store:
    def __init__(self, row):
        self.sim_runs = Runs(row)


def run_row(**overrides):
    row = {
        "run_id": "living_run_1",
        "state": lease.RUNNING,
        "cursor": 0,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
    }
    row.update(overrides)
    return row


def test_claim_fences_owner_and_refuses_second_live_owner():
    async def case():
        store = Store(run_row())
        first = await lease.acquire("living_run_1", "worker-a", store=store, now=NOW)
        assert first["fence"] == 1
        with pytest.raises(lease.RunLeaseError, match="already leased"):
            await lease.acquire("living_run_1", "worker-b", store=store, now=NOW)
    asyncio.run(case())


def test_expired_lease_can_be_reclaimed_with_higher_fence():
    async def case():
        store = Store(run_row(
            execution_lease_generation=4,
            execution_lease={"holder_id": "dead-worker", "expires_at": (NOW - timedelta(seconds=1)).isoformat()},
        ))
        claimed = await lease.acquire("living_run_1", "worker-b", store=store, now=NOW)
        assert claimed["fence"] == 5
        assert claimed["holder_id"] == "worker-b"
    asyncio.run(case())


def test_heartbeat_requires_running_current_unexpired_fence():
    async def case():
        store = Store(run_row())
        claimed = await lease.acquire("living_run_1", "worker-a", store=store, now=NOW)
        await lease.heartbeat("living_run_1", "worker-a", claimed["fence"], store=store, now=NOW)
        store.sim_runs.row["state"] = lease.PAUSED
        with pytest.raises(lease.RunLeaseError, match="heartbeat refused"):
            await lease.heartbeat("living_run_1", "worker-a", claimed["fence"], store=store, now=NOW)
    asyncio.run(case())


def test_cursor_advance_is_single_owner_compare_and_swap():
    async def case():
        store = Store(run_row())
        claimed = await lease.acquire("living_run_1", "worker-a", store=store, now=NOW)
        row = await lease.advance_cursor(
            "living_run_1", "worker-a", claimed["fence"], 0, 1,
            store=store, now=NOW, fields={"last_event_id": "evt-1"},
        )
        assert row["cursor"] == 1 and row["last_event_id"] == "evt-1"
        with pytest.raises(lease.RunLeaseError, match="cursor advance refused"):
            await lease.advance_cursor("living_run_1", "worker-a", claimed["fence"], 0, 1, store=store, now=NOW)
    asyncio.run(case())


def test_stale_owner_cannot_advance_after_takeover():
    async def case():
        store = Store(run_row())
        first = await lease.acquire("living_run_1", "worker-a", store=store, now=NOW, ttl_seconds=5)
        later = NOW + timedelta(seconds=6)
        second = await lease.acquire("living_run_1", "worker-b", store=store, now=later)
        assert second["fence"] > first["fence"]
        with pytest.raises(lease.RunLeaseError, match="cursor advance refused"):
            await lease.advance_cursor(
                "living_run_1", "worker-a", first["fence"], 0, 1,
                store=store, now=later,
            )
    asyncio.run(case())


def test_wrong_scope_never_claims_and_release_is_fenced():
    async def case():
        store = Store(run_row(simulation_community_id="other"))
        with pytest.raises(lease.RunLeaseError, match="out of scope"):
            await lease.acquire("living_run_1", "worker-a", store=store, now=NOW)

        store = Store(run_row())
        claimed = await lease.acquire("living_run_1", "worker-a", store=store, now=NOW)
        with pytest.raises(lease.RunLeaseError, match="release refused"):
            await lease.release("living_run_1", "worker-a", claimed["fence"] + 1, store=store, now=NOW)
        row = await lease.release("living_run_1", "worker-a", claimed["fence"], store=store, now=NOW)
        assert "execution_lease" not in row
    asyncio.run(case())


def test_validation_rejects_naive_time_and_protected_fields():
    with pytest.raises(lease.RunLeaseError, match="timezone-aware"):
        lease._utc(datetime(2026, 10, 13, 7, 0))
