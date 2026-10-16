"""Bounded read model for recent living-community task activity."""

from datetime import datetime, timezone

from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE


TASK_LIMIT = 12
RECEIPT_LIMIT = 24


def _default_store():
    from deps import db

    return db


def _source(status: str, error: str | None = None) -> dict:
    return {"status": status, "error": error}


def _stamp(value) -> str | None:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat() if value.tzinfo else None
    return value if isinstance(value, str) and value.strip() else None


async def _recent(collection, query: dict, projection: dict, limit: int) -> list[dict]:
    cursor = collection.find(query, projection)
    if hasattr(cursor, "sort"):
        cursor = cursor.sort("created_at", -1)
    return await cursor.to_list(limit)


def _empty(status: str, run_id: str | None, sources: dict, errors: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "status": status,
        "read_only": True,
        "simulation_scope": SIMULATION_SCOPE,
        "community_id": COMMUNITY_ID,
        "run_id": run_id,
        "truth_statement": (
            "Only exact run-scoped canonical simulated tasks and their receipts are shown; "
            "unavailable reads remain unknown."
        ),
        "tasks": {"status": status, "items": None},
        "transitions": {"status": status, "items": None},
        "sources": sources,
        "errors": errors,
    }


def _updated_at(task: dict) -> str | None:
    events = task.get("event_log") or []
    if events:
        latest = _stamp(events[-1].get("at"))
        if latest:
            return latest
    for key in ("completed_at", "started_at", "acknowledged_at", "created_at"):
        if value := _stamp(task.get(key)):
            return value
    return None


def _task_view(task: dict, residents: dict[str, dict]) -> dict:
    resident_id = task.get("resident_id")
    resident = residents.get(resident_id) if isinstance(resident_id, str) else None
    assignee = None
    if task.get("assigned_to"):
        assignee = {"id": task["assigned_to"], "name": task.get("assigned_name")}
    return {
        "task_id": task.get("task_id"),
        "simulated": True,
        "resident": {
            "id": resident_id if resident else None,
            "name": resident.get("name") if resident else None,
        },
        "department": task.get("visibility_role") or task.get("category"),
        "category": task.get("category"),
        "summary": task.get("description") or task.get("title") or "",
        "priority": task.get("priority"),
        "status": task.get("status"),
        "assigned_worker": assignee,
        "created_at": _stamp(task.get("created_at")),
        "acknowledged_at": _stamp(task.get("acknowledged_at")),
        "started_at": _stamp(task.get("started_at")),
        "updated_at": _updated_at(task),
        "completed_at": _stamp(task.get("completed_at")),
    }


def _receipt_view(row: dict) -> dict:
    actor = {
        "id": row.get("actor_id"),
        "type": row.get("actor_type"),
        "name": row.get("actor_name"),
        "role": row.get("actor_role"),
        "department": row.get("actor_department"),
        "channel": row.get("channel"),
        "identity_basis": row.get("identity_basis"),
        "simulated": row.get("simulated"),
    }
    complete = all((actor["id"], actor["type"], actor["identity_basis"], row.get("authority")))
    return {
        "receipt_id": row.get("receipt_id"),
        "task_id": row.get("related_object_id"),
        "action_type": row.get("action_type"),
        "source": row.get("source"),
        "status": row.get("status"),
        "actor": actor,
        "authority": row.get("authority"),
        "provenance_status": "complete" if complete else "incomplete",
        "parent_receipt_id": row.get("parent_receipt_id"),
        "correlation_id": row.get("correlation_id"),
        "before_status": (row.get("before_state") or {}).get("status"),
        "after_status": (row.get("after_state") or {}).get("status"),
        "next_state": row.get("next_state"),
        "created_at": _stamp(row.get("created_at")),
        "completed_at": _stamp(row.get("completed_at")),
    }


async def activity_snapshot(*, run_id: str | None, store=None) -> dict:
    """Read recent canonical tasks/receipts for one exact living-community run."""
    store = store if store is not None else _default_store()
    sources = {name: _source("unknown") for name in ("run", "tasks", "residents", "receipts")}
    errors: list[dict] = []
    if not run_id:
        return _empty("not_started", None, sources, errors)
    exact = {
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "simulation_run_id": run_id,
    }
    try:
        run = await store.sim_runs.find_one({
            "run_id": run_id,
            "simulation_scope": SIMULATION_SCOPE,
            "simulation_community_id": COMMUNITY_ID,
        }, {"_id": 0, "run_id": 1})
        if not run:
            raise LookupError("run_not_exact")
        sources["run"] = _source("loaded")
    except Exception as exc:
        sources["run"] = _source("error", type(exc).__name__)
        errors.append({"source": "run", "code": "run_not_exact"})
        return _empty("error", run_id, sources, errors)

    task_rows = None
    residents: dict[str, dict] = {}
    try:
        task_rows = await _recent(
            store.staff_tasks, {**exact, "simulated": True}, {"_id": 0}, TASK_LIMIT,
        )
        sources["tasks"] = _source("loaded")
    except Exception as exc:
        sources["tasks"] = _source("error", type(exc).__name__)
        errors.append({"source": "tasks", "code": "read_failed"})
    if task_rows is not None:
        ids = sorted({row.get("resident_id") for row in task_rows if row.get("resident_id")})
        try:
            rows = await store.residents.find({
                "resident_id": {"$in": ids},
                "synthetic": True,
                "simulation_scope": SIMULATION_SCOPE,
                "simulation_community_id": COMMUNITY_ID,
            }, {"_id": 0, "resident_id": 1, "name": 1}).to_list(len(ids))
            residents = {row["resident_id"]: row for row in rows}
            sources["residents"] = _source("loaded")
        except Exception as exc:
            sources["residents"] = _source("error", type(exc).__name__)
            errors.append({"source": "residents", "code": "read_failed"})

    receipt_rows = None
    try:
        receipt_rows = await _recent(
            store.receipts, {**exact, "related_object_type": "task"},
            {"_id": 0}, RECEIPT_LIMIT,
        )
        sources["receipts"] = _source("loaded")
    except Exception as exc:
        sources["receipts"] = _source("error", type(exc).__name__)
        errors.append({"source": "receipts", "code": "read_failed"})

    return {
        "schema_version": 1,
        "status": "error" if errors else "loaded",
        "read_only": True,
        "simulation_scope": SIMULATION_SCOPE,
        "community_id": COMMUNITY_ID,
        "run_id": run_id,
        "truth_statement": (
            "Only exact run-scoped canonical simulated tasks and their receipts are shown; "
            "unavailable reads remain unknown."
        ),
        "tasks": {
            "status": sources["tasks"]["status"],
            "items": None if task_rows is None else [_task_view(row, residents) for row in task_rows],
        },
        "transitions": {
            "status": sources["receipts"]["status"],
            "items": None if receipt_rows is None else [_receipt_view(row) for row in receipt_rows],
        },
        "sources": sources,
        "errors": errors,
    }
