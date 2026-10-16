"""Legacy bulk services must not cross into the living-community world."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from living_community_boundary import (
    is_living_community_resident,
    protected_resident_ids,
)
from routes import insights, location
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE


REAL = {"resident_id": "real-1", "name": "Real", "room": "101"}
DEMO = {
    "resident_id": "demo-1", "name": "Demo", "room": "DEMO",
    "synthetic": True, "simulation_scope": "demo_room",
}
EXACT = {
    "resident_id": "sim:resident:001", "name": "Exact", "room": "SIM-001",
    "synthetic": True, "simulation_scope": SIMULATION_SCOPE,
    "simulation_community_id": COMMUNITY_ID,
}
MALFORMED_SCOPE = {
    "resident_id": "malformed-scope", "name": "Malformed scope", "room": "X1",
    "synthetic": False, "simulation_scope": SIMULATION_SCOPE,
    "simulation_community_id": "wrong-community",
}
MALFORMED_COMMUNITY = {
    "resident_id": "malformed-community", "name": "Malformed community", "room": "X2",
    "simulation_scope": "wrong-scope", "simulation_community_id": COMMUNITY_ID,
}
RESERVED_UNMARKED = {
    "resident_id": "sim:resident:075", "name": "Reserved", "room": "X3",
}


class _Cursor:
    def __init__(self, rows):
        self.rows = [deepcopy(row) for row in rows]

    async def to_list(self, limit):
        return deepcopy(self.rows[:limit])


class _Residents:
    def __init__(self, rows):
        self.rows = [deepcopy(row) for row in rows]

    def find(self, _query, _projection=None):
        return _Cursor(self.rows)


class _Locations:
    def __init__(self):
        self.inserted = []

    async def insert_one(self, doc):
        self.inserted.append(deepcopy(doc))


class _Insights:
    def __init__(self, rows):
        self.rows = [deepcopy(row) for row in rows]
        self.delete_queries = []

    async def delete_many(self, query):
        self.delete_queries.append(deepcopy(query))
        protected = set(query["resident_id"]["$nin"])
        self.rows = [row for row in self.rows if row.get("resident_id") in protected]

    async def insert_one(self, doc):
        self.rows.append(deepcopy(doc))


@pytest.mark.parametrize(
    "resident",
    [EXACT, MALFORMED_SCOPE, MALFORMED_COMMUNITY, RESERVED_UNMARKED],
)
def test_boundary_protects_exact_partial_and_reserved_identity(resident):
    assert is_living_community_resident(resident) is True


@pytest.mark.parametrize("resident", [REAL, DEMO])
def test_boundary_preserves_real_and_legacy_demo_behavior(resident):
    assert is_living_community_resident(resident) is False


def test_protected_ids_come_from_blueprint_and_malformed_resident_truth():
    ids = protected_resident_ids([REAL, DEMO, MALFORMED_SCOPE])
    assert "sim:resident:001" in ids
    assert "sim:resident:075" in ids
    assert "malformed-scope" in ids
    assert "real-1" not in ids
    assert "demo-1" not in ids


def test_location_mock_generation_skips_community_and_keeps_real_demo(monkeypatch):
    rows = [REAL, DEMO, EXACT, MALFORMED_SCOPE, MALFORMED_COMMUNITY, RESERVED_UNMARKED]
    store = SimpleNamespace(residents=_Residents(rows), locations=_Locations())
    monkeypatch.setattr(location, "db", store)
    monkeypatch.setattr(location.random, "choice", lambda _values: "Lounge")
    monkeypatch.setattr(location.random, "randint", lambda _low, _high: 80)

    result = asyncio.run(location.generate_mock_location(user={"role": "owner"}))

    assert result["generated"] == 2
    assert {row["resident_id"] for row in store.locations.inserted} == {"real-1", "demo-1"}
    assert all(row["source"] == "mock" for row in store.locations.inserted)


def test_insights_bulk_preserves_community_rows_and_computes_real_demo(monkeypatch):
    rows = [REAL, DEMO, EXACT, MALFORMED_SCOPE, MALFORMED_COMMUNITY, RESERVED_UNMARKED]
    prior = [
        {"insight_id": "real-old", "resident_id": "real-1"},
        {"insight_id": "demo-old", "resident_id": "demo-1"},
        {"insight_id": "exact-old", "resident_id": "sim:resident:001"},
        {"insight_id": "malformed-old", "resident_id": "malformed-scope"},
    ]
    store = SimpleNamespace(residents=_Residents(rows), insights=_Insights(prior))
    computed = []

    async def no_metrics(resident):
        computed.append(resident["resident_id"])
        return []

    monkeypatch.setattr(insights, "db", store)
    monkeypatch.setattr(insights, "compute_for_resident", no_metrics)

    result = asyncio.run(insights.compute_all(user={"role": "owner"}))

    assert computed == ["real-1", "demo-1"]
    assert result == {"computed": 0, "residents": 2, "living_community_skipped": 4}
    assert {row["insight_id"] for row in store.insights.rows} == {
        "exact-old", "malformed-old",
    }
    excluded = set(store.insights.delete_queries[0]["resident_id"]["$nin"])
    assert {"sim:resident:001", "sim:resident:075", "malformed-scope"} <= excluded
    assert "real-1" not in excluded and "demo-1" not in excluded
