"""Read-only observed truth for the living-community simulator.

The static community preview says what is planned.  This module reports only
what canonical collections can actually prove.  Reads are injectable for
focused tests and future route composition; no writer is accepted or used.
"""
from collections.abc import Awaitable, Callable, Iterable
from typing import Optional

from simulation.community_blueprint import (
    BURN_IN_RESIDENTS,
    COMMUNITY_ID,
    RESIDENTS,
    SIMULATION_SCOPE,
)


COLLECTIONS = ("residents", "staff_tasks", "notifications", "sim_runs")
OUTPUT_NAMES = {
    "residents": "residents",
    "staff_tasks": "tasks",
    "notifications": "notifications",
    "sim_runs": "runs",
}
ID_FIELDS = {
    "residents": "resident_id",
    "staff_tasks": "task_id",
    "notifications": "notification_id",
    "sim_runs": "run_id",
}
TRUTH_FIELDS = {
    "residents": "synthetic",
    "staff_tasks": "simulated",
    "notifications": "simulated",
}
PROJECTIONS = {
    name: {
        "_id": 0,
        ID_FIELDS[name]: 1,
        "resident_id": 1,
        "room": 1,
        "pendant_id": 1,
        "simulation_run_id": 1,
        "simulation_scope": 1,
        "simulation_community_id": 1,
        **({TRUTH_FIELDS[name]: 1} if name in TRUTH_FIELDS else {}),
    }
    for name in COLLECTIONS
}

Reader = Callable[[str, dict], Awaitable[Optional[Iterable[dict]]]]
_BLUEPRINT_RESIDENT_IDS = frozenset(row.resident_id for row in RESIDENTS)


def _default_store():
    from deps import db

    return db


async def _store_reader(store, collection_name: str, projection: dict):
    collection = getattr(store, collection_name)
    return await collection.find({}, projection).to_list(length=None)


def _marker_reasons(collection_name: str, row: dict) -> list[str]:
    reasons = []
    truth_field = TRUTH_FIELDS.get(collection_name)
    if truth_field and row.get(truth_field) is not True:
        reasons.append(f"{truth_field}_not_true")
    scope = row.get("simulation_scope")
    if scope != SIMULATION_SCOPE:
        reasons.append("scope_missing" if scope is None else "scope_mismatch")
    community_id = row.get("simulation_community_id")
    if community_id != COMMUNITY_ID:
        reasons.append(
            "community_id_missing" if community_id is None else "community_id_mismatch"
        )
    return reasons


def _is_candidate(
    collection_name: str,
    row: dict,
    candidate_run_ids: frozenset[str],
) -> bool:
    if row.get("simulation_scope") == SIMULATION_SCOPE:
        return True
    if row.get("simulation_community_id") == COMMUNITY_ID:
        return True
    if collection_name == "residents":
        return row.get("resident_id") in _BLUEPRINT_RESIDENT_IDS
    if collection_name in ("staff_tasks", "notifications"):
        return (
            row.get("resident_id") in _BLUEPRINT_RESIDENT_IDS
            or row.get("simulation_run_id") in candidate_run_ids
        )
    return False


def _object_id(collection_name: str, row: dict) -> Optional[str]:
    value = row.get(ID_FIELDS[collection_name])
    return str(value) if value is not None else None


def _burn_in_provisioning(rows: tuple[dict, ...]) -> dict:
    """Classify the exact ten-resident burn-in identity set."""
    observed_indexes: set[int] = set()
    exact = missing = collisions = 0
    for recipe in BURN_IN_RESIDENTS:
        hits = [
            (index, row)
            for index, row in enumerate(rows)
            if (
                row.get("resident_id") == recipe.resident_id
                or row.get("room") == recipe.room
                or row.get("pendant_id") == recipe.pendant_id
            )
        ]
        observed_indexes.update(index for index, _row in hits)
        if not hits:
            missing += 1
            continue
        if len(hits) != 1:
            collisions += 1
            continue
        row = hits[0][1]
        identity_matches = (
            row.get("resident_id") == recipe.resident_id
            and row.get("room") == recipe.room
            and row.get("pendant_id") == recipe.pendant_id
        )
        if identity_matches and not _marker_reasons("residents", row):
            exact += 1
        else:
            collisions += 1

    if collisions:
        state = "inconsistent"
    elif exact == len(BURN_IN_RESIDENTS):
        state = "provisioned"
    elif not observed_indexes:
        state = "not_provisioned"
    else:
        state = "partial"
    return {
        "state": state,
        "expected_residents": len(BURN_IN_RESIDENTS),
        "observed_residents": len(observed_indexes),
        "exact_blueprint_residents": exact,
        "missing_count": missing,
        "collision_count": collisions,
    }


def _unavailable_provisioning() -> dict:
    return {
        "state": None,
        "expected_residents": len(BURN_IN_RESIDENTS),
        "observed_residents": None,
        "exact_blueprint_residents": None,
        "missing_count": None,
        "collision_count": None,
    }


def _analyze(rows_by_collection: dict[str, tuple[dict, ...]]) -> tuple[dict, list[dict]]:
    run_rows = rows_by_collection.get("sim_runs", ())
    candidate_run_ids = frozenset(
        str(row["run_id"])
        for row in run_rows
        if row.get("run_id") is not None
        and (
            row.get("simulation_scope") == SIMULATION_SCOPE
            or row.get("simulation_community_id") == COMMUNITY_ID
        )
    )
    counts, anomalies = {}, []
    for collection_name, rows in rows_by_collection.items():
        exact = 0
        for row in rows:
            if not _is_candidate(collection_name, row, candidate_run_ids):
                continue
            reasons = _marker_reasons(collection_name, row)
            if reasons:
                anomalies.append({
                    "collection": collection_name,
                    "object_id": _object_id(collection_name, row),
                    "reasons": reasons,
                })
            else:
                exact += 1
        counts[collection_name] = exact
    anomalies.sort(key=lambda item: (item["collection"], item["object_id"] or ""))
    return counts, anomalies


async def observe_community_state(
    *,
    store=None,
    collection_reader: Optional[Reader] = None,
) -> dict:
    """Read exact living-community markers without changing canonical state.

    ``None`` returned by an injected reader means that source is unavailable,
    so its status and count are ``unknown``.  A raised read error is reported
    as ``error`` and also keeps the count ``None``.  Neither case is reported
    as an empty collection.
    """
    if store is not None and collection_reader is not None:
        raise ValueError("provide either store or collection_reader, not both")
    selected_store = (
        store
        if store is not None
        else None
        if collection_reader is not None
        else _default_store()
    )

    async def read(name: str, projection: dict):
        if collection_reader is not None:
            return await collection_reader(name, projection)
        return await _store_reader(selected_store, name, projection)

    rows_by_collection: dict[str, tuple[dict, ...]] = {}
    sources = {}
    for name in COLLECTIONS:
        try:
            result = await read(name, PROJECTIONS[name])
            if result is None:
                sources[name] = {"status": "unknown", "error": None}
                continue
            rows_by_collection[name] = tuple(dict(row) for row in result)
            sources[name] = {"status": "loaded", "error": None}
        except Exception as exc:  # the response must preserve read uncertainty
            sources[name] = {
                "status": "error",
                "error": f"{type(exc).__name__}",
            }

    loaded_counts, anomalies = _analyze(rows_by_collection)
    provisioning = (
        _burn_in_provisioning(rows_by_collection["residents"])
        if sources["residents"]["status"] == "loaded"
        else _unavailable_provisioning()
    )
    for name in COLLECTIONS:
        source = sources[name]
        source["exact_marked"] = (
            loaded_counts[name] if source["status"] == "loaded" else None
        )
        source["marker_anomalies"] = (
            sum(1 for item in anomalies if item["collection"] == name)
            if source["status"] == "loaded"
            else None
        )

    states = {source["status"] for source in sources.values()}
    overall = "error" if "error" in states else "unknown" if "unknown" in states else "loaded"
    return {
        "status": overall,
        "simulation_scope": SIMULATION_SCOPE,
        "community_id": COMMUNITY_ID,
        "truth_statement": (
            "Counts are observed canonical records with exact living-community markers; "
            "unknown or failed reads remain null and are never represented as zero."
        ),
        "counts": {
            OUTPUT_NAMES[name]: sources[name]["exact_marked"]
            for name in COLLECTIONS
        },
        "sources": {
            OUTPUT_NAMES[name]: {"collection": name, **sources[name]}
            for name in COLLECTIONS
        },
        "provisioning": provisioning,
        "marker_anomalies": anomalies,
    }
