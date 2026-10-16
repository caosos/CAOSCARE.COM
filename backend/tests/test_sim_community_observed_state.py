"""Observed community truth stays read-only and preserves uncertainty."""
import asyncio
from copy import deepcopy

import pytest

from simulation.community_blueprint import (
    BURN_IN_RESIDENTS,
    COMMUNITY_ID,
    SIMULATION_SCOPE,
)
from simulation.community_observed_state import (
    COLLECTIONS,
    observe_community_state,
)


def marked(collection, object_id, **extra):
    id_field = {
        "residents": "resident_id",
        "staff_tasks": "task_id",
        "notifications": "notification_id",
        "sim_runs": "run_id",
    }[collection]
    row = {
        id_field: object_id,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        **extra,
    }
    if collection == "residents":
        row.setdefault("synthetic", True)
    elif collection in ("staff_tasks", "notifications"):
        row.setdefault("simulated", True)
    return row


def blueprint_resident(recipe, **changes):
    return {
        "resident_id": recipe.resident_id,
        "room": recipe.room,
        "pendant_id": recipe.pendant_id,
        "synthetic": True,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        **changes,
    }


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, *, length):
        assert length is None
        return deepcopy(self.rows)


class ReadOnlyCollection:
    def __init__(self, rows):
        self.rows = rows
        self.reads = []

    def find(self, query, projection):
        self.reads.append((deepcopy(query), deepcopy(projection)))
        return Cursor(self.rows)


class Store:
    def __init__(self, rows_by_collection):
        for name in COLLECTIONS:
            setattr(self, name, ReadOnlyCollection(rows_by_collection.get(name, [])))


def test_loaded_counts_only_exact_marked_records_and_never_writes():
    rows = {
        "residents": [marked("residents", "sim:resident:001")],
        "staff_tasks": [marked("staff_tasks", "task-1", resident_id="sim:resident:001")],
        "notifications": [marked("notifications", "note-1", resident_id="sim:resident:001")],
        "sim_runs": [marked("sim_runs", "run-1")],
    }
    store = Store(rows)
    result = asyncio.run(observe_community_state(store=store))

    assert result["status"] == "loaded"
    assert result["counts"] == {
        "residents": 1, "tasks": 1, "notifications": 1, "runs": 1,
    }
    assert result["marker_anomalies"] == []
    assert result["provisioning"] == {
        "cohort": "burn_in_10",
        "state": "inconsistent",
        "expected_residents": 10,
        "observed_residents": 1,
        "exact_blueprint_residents": 0,
        "missing_count": 9,
        "collision_count": 1,
    }
    for name in COLLECTIONS:
        assert store.__dict__[name].reads[0][0] == {}
        assert store.__dict__[name].reads[0][1]["_id"] == 0
        assert not hasattr(store.__dict__[name], "insert_one")


def test_unrelated_real_and_other_simulation_rows_are_ignored():
    rows = {
        "residents": [
            {"resident_id": "real-1"},
            {"resident_id": "demo", "synthetic": True, "simulation_scope": "demo_room"},
        ],
        "staff_tasks": [{"task_id": "real-task", "simulated": False}],
        "notifications": [{"notification_id": "other", "simulated": True,
                           "simulation_scope": "other"}],
        "sim_runs": [{"run_id": "legacy-unmarked"}],
    }
    result = asyncio.run(observe_community_state(store=Store(rows)))

    assert result["status"] == "loaded"
    assert result["counts"] == {
        "residents": 0, "tasks": 0, "notifications": 0, "runs": 0,
    }
    assert result["marker_anomalies"] == []


def test_attributable_partial_markers_are_anomalies_not_exact_counts():
    rows = {
        "residents": [{
            "resident_id": "sim:resident:001",
            "synthetic": False,
            "simulation_scope": SIMULATION_SCOPE,
        }],
        "staff_tasks": [{
            "task_id": "task-bad",
            "resident_id": "sim:resident:001",
            "simulated": True,
            "simulation_scope": "wrong",
            "simulation_community_id": COMMUNITY_ID,
        }],
        "notifications": [{
            "notification_id": "note-bad",
            "simulated": False,
            "simulation_run_id": "run-partial",
        }],
        "sim_runs": [{
            "run_id": "run-partial",
            "simulation_scope": SIMULATION_SCOPE,
            "simulation_community_id": "wrong-community",
        }],
    }
    result = asyncio.run(observe_community_state(store=Store(rows)))

    assert result["counts"] == {
        "residents": 0, "tasks": 0, "notifications": 0, "runs": 0,
    }
    assert [item["object_id"] for item in result["marker_anomalies"]] == [
        "note-bad", "sim:resident:001", "run-partial", "task-bad",
    ]
    reasons = {item["object_id"]: item["reasons"] for item in result["marker_anomalies"]}
    assert reasons["sim:resident:001"] == ["synthetic_not_true", "community_id_missing"]
    assert reasons["task-bad"] == ["scope_mismatch"]
    assert reasons["note-bad"] == [
        "simulated_not_true", "scope_missing", "community_id_missing",
    ]
    assert reasons["run-partial"] == ["community_id_mismatch"]


def test_read_error_is_error_with_null_count_not_false_zero():
    async def reader(name, _projection):
        if name == "staff_tasks":
            raise RuntimeError("database unavailable")
        return [marked(name, f"{name}-1")]

    result = asyncio.run(observe_community_state(collection_reader=reader))

    assert result["status"] == "error"
    assert result["counts"]["tasks"] is None
    assert result["sources"]["tasks"] == {
        "collection": "staff_tasks", "status": "error", "error": "RuntimeError",
        "exact_marked": None, "marker_anomalies": None,
    }
    assert result["counts"]["residents"] == 1


def test_unavailable_reader_result_is_unknown_with_null_count():
    async def reader(name, _projection):
        return None if name == "notifications" else []

    result = asyncio.run(observe_community_state(collection_reader=reader))

    assert result["status"] == "unknown"
    assert result["counts"]["notifications"] is None
    assert result["sources"]["notifications"]["status"] == "unknown"
    assert result["counts"]["residents"] == 0


def test_successful_empty_resident_read_is_not_provisioned():
    result = asyncio.run(observe_community_state(store=Store({})))

    assert result["provisioning"] == {
        "cohort": "burn_in_10",
        "state": "not_provisioned",
        "expected_residents": 10,
        "observed_residents": 0,
        "exact_blueprint_residents": 0,
        "missing_count": 10,
        "collision_count": 0,
    }


def test_all_ten_exact_blueprint_residents_are_provisioned():
    residents = [blueprint_resident(recipe) for recipe in BURN_IN_RESIDENTS]
    result = asyncio.run(observe_community_state(
        store=Store({"residents": residents})
    ))

    assert result["provisioning"] == {
        "cohort": "burn_in_10",
        "state": "provisioned",
        "expected_residents": 10,
        "observed_residents": 10,
        "exact_blueprint_residents": 10,
        "missing_count": 0,
        "collision_count": 0,
    }


def test_some_exact_blueprint_residents_are_partial():
    residents = [blueprint_resident(recipe) for recipe in BURN_IN_RESIDENTS[:4]]
    result = asyncio.run(observe_community_state(
        store=Store({"residents": residents})
    ))

    assert result["provisioning"]["state"] == "partial"
    assert result["provisioning"]["observed_residents"] == 4
    assert result["provisioning"]["exact_blueprint_residents"] == 4
    assert result["provisioning"]["missing_count"] == 6
    assert result["provisioning"]["collision_count"] == 0


@pytest.mark.parametrize("field", [
    "resident_id", "room", "pendant_id", "synthetic",
    "simulation_scope", "simulation_community_id",
])
def test_any_identity_or_marker_collision_is_inconsistent(field):
    recipe = BURN_IN_RESIDENTS[0]
    row = blueprint_resident(recipe)
    row[field] = False if field == "synthetic" else f"wrong-{field}"
    # Keep one stable identity so the corrupted row is attributable.
    row["resident_id" if field != "resident_id" else "room"] = (
        recipe.resident_id if field != "resident_id" else recipe.room
    )
    result = asyncio.run(observe_community_state(
        store=Store({"residents": [row]})
    ))

    assert result["provisioning"]["state"] == "inconsistent"
    assert result["provisioning"]["collision_count"] == 1
    assert result["provisioning"]["exact_blueprint_residents"] == 0


def test_split_and_duplicate_identity_is_one_collided_recipe():
    recipe = BURN_IN_RESIDENTS[0]
    rows = [
        blueprint_resident(recipe),
        marked("residents", "different", room=recipe.room, pendant_id="different"),
    ]
    result = asyncio.run(observe_community_state(
        store=Store({"residents": rows})
    ))

    assert result["provisioning"]["state"] == "inconsistent"
    assert result["provisioning"]["observed_residents"] == 2
    assert result["provisioning"]["collision_count"] == 1


def test_failed_resident_read_does_not_invent_provisioning_state():
    async def reader(name, _projection):
        if name == "residents":
            raise OSError("unavailable")
        return []

    result = asyncio.run(observe_community_state(collection_reader=reader))

    assert result["provisioning"] == {
        "cohort": "burn_in_10",
        "state": None,
        "expected_residents": 10,
        "observed_residents": None,
        "exact_blueprint_residents": None,
        "missing_count": None,
        "collision_count": None,
    }


def test_reader_and_store_are_mutually_exclusive():
    async def reader(_name, _projection):
        return []

    with pytest.raises(ValueError, match="either store or collection_reader"):
        asyncio.run(observe_community_state(store=Store({}), collection_reader=reader))
