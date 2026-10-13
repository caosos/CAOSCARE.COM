"""Exact, read-only inspection for living-community runtime indexes."""

from copy import deepcopy

from simulation.community_index_contract import REQUIRED_INDEXES


UNSUPPORTED_OPTIONS = (
    "partialFilterExpression", "sparse", "expireAfterSeconds", "collation",
    "wildcardProjection", "hidden",
)


def _keys(value) -> tuple[tuple[str, int], ...]:
    try:
        return tuple((str(field), int(direction)) for field, direction in value)
    except (TypeError, ValueError):
        return ()


def _options(row: dict) -> dict:
    result = {"unique": bool(row.get("unique", False))}
    for name in UNSUPPORTED_OPTIONS:
        if name in row and row[name] not in (False, None, {}):
            result[name] = deepcopy(row[name])
    return result


def _expected(requirement: dict) -> dict:
    return {
        "collection": requirement["collection"],
        "name": requirement["name"],
        "keys": [list(item) for item in requirement["keys"]],
        "unique": requirement["unique"],
        "purpose": requirement["purpose"],
    }


async def inspect_index_contract(store, *, session=None) -> dict:
    """Classify every exact named index without changing storage."""
    metadata: dict[str, dict] = {}
    failures: dict[str, str] = {}
    for collection_name in sorted({row["collection"] for row in REQUIRED_INDEXES}):
        try:
            collection = getattr(store, collection_name)
            metadata[collection_name] = await collection.index_information(session=session)
        except Exception as exc:
            failures[collection_name] = type(exc).__name__

    rows = []
    for requirement in REQUIRED_INDEXES:
        expected = _expected(requirement)
        collection_name = requirement["collection"]
        if collection_name in failures:
            rows.append({
                **expected, "status": "probe_failed", "observed": None,
                "conflicting_name": None, "error_type": failures[collection_name],
            })
            continue
        information = metadata[collection_name]
        found = information.get(requirement["name"])
        if found is not None:
            observed_keys = _keys(found.get("key"))
            observed_options = _options(found)
            compatible = (
                observed_keys == requirement["keys"]
                and observed_options == {"unique": requirement["unique"]}
            )
            rows.append({
                **expected, "status": "ready" if compatible else "conflict",
                "observed": {
                    "keys": [list(item) for item in observed_keys],
                    **observed_options,
                },
                "conflicting_name": requirement["name"] if not compatible else None,
                "error_type": None,
            })
            continue
        equivalent = next(
            (
                (name, row) for name, row in information.items()
                if name != "_id_" and _keys(row.get("key")) == requirement["keys"]
            ),
            None,
        )
        if equivalent:
            name, row = equivalent
            rows.append({
                **expected, "status": "conflict",
                "observed": {
                    "keys": [list(item) for item in _keys(row.get("key"))],
                    **_options(row),
                },
                "conflicting_name": name, "error_type": None,
            })
        else:
            rows.append({
                **expected, "status": "missing", "observed": None,
                "conflicting_name": None, "error_type": None,
            })
    blockers = [row["name"] for row in rows if row["status"] != "ready"]
    return {
        "status": "ready" if not blockers else "blocked",
        "ready": not blockers,
        "required": rows,
        "blockers": blockers,
    }


def public_snapshot(report: dict) -> dict:
    """Return bounded receipt-safe index evidence."""
    return {
        "status": report["status"],
        "ready": report["ready"],
        "indexes": [
            {
                "collection": row["collection"], "name": row["name"],
                "keys": row["keys"], "unique": row["unique"],
                "status": row["status"],
                "conflicting_name": row["conflicting_name"],
                "error_type": row["error_type"],
            }
            for row in report["required"]
        ],
    }
