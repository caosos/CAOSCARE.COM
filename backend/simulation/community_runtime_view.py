"""Read-only projection: failures stay unknown; no writes or adapters."""

from datetime import datetime, timezone

from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_readiness_view import attach_resident_readiness
from simulation.community_routines import ADAPTER_CAPABILITIES, BLOCKED
from simulation.community_runtime_shapes import append_error as _error, source_status as _source
from simulation.community_runtime_staffing import staffing_projection as _staffing
from simulation.community_timeline import build_90_day_timeline, cohort_of_revision


RUN_STATES = frozenset({"RUNNING", "PAUSED", "STOPPED"})
TASK_STATES = frozenset({"pending", "in_progress", "completed", "skipped"})


def _default_store():
    from deps import db
    return db


def _events(run: dict):
    """The run's own plan (its revision names the cohort); empty if unknown."""
    try:
        return build_90_day_timeline(cohort_of_revision(run.get("plan_revision"))).events
    except ValueError:
        return ()


async def _rows(collection, query: dict, projection: dict) -> list[dict]:
    return await collection.find(query, projection).to_list(None)


def _stamp(row: dict) -> str | None:
    value = row.get("updated_at") or row.get("created_at")
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat() if value.tzinfo else None
    return value if isinstance(value, str) and value.strip() else None


def _select_run(rows: list[dict]) -> tuple[dict | None, str | None]:
    active = [row for row in rows if row.get("state") in {"RUNNING", "PAUSED"}]
    if len(active) > 1:
        return None, "multiple_active_runs"
    if active:
        return active[0], None
    if not rows:
        return None, None
    stamped = [(stamp, row) for row in rows if (stamp := _stamp(row))]
    if not stamped:
        return (rows[0], None) if len(rows) == 1 else (None, "latest_run_ambiguous")
    newest = max(stamp for stamp, _row in stamped)
    matches = [row for stamp, row in stamped if stamp == newest]
    return (matches[0], None) if len(matches) == 1 else (None, "latest_run_ambiguous")


def _empty_run(status: str) -> dict:
    return {
        "status": status,
        "run_id": None,
        "state": None,
        "simulated_time": {
            "absolute_minute": None, "day_index": None,
            "minute": None, "hh_mm": None,
        },
        "cursor": None,
        "event_count": None,
        "progress": {"completed_events": None, "total_events": None, "percent": None},
        "next_event": None,
        "last_evidence": None,
        "resident_readiness": {
            "status": status, "residents_provisioned": None,
            "expected_resident_count": None, "receipt_id": None, "reason": None,
        },
    }


def _event(row) -> dict:
    return {
        key: getattr(row, key)
        for key in (
            "event_id", "stream_kind", "action_type", "day_index", "minute",
            "actor_id", "actor_name", "department", "target_type", "target_id",
        )
    } | {"blocked": ADAPTER_CAPABILITIES.get(row.adapter, {}).get("status") == BLOCKED,
         "capability_not_invoked": row.blocked_capability}


def _run_projection(run: dict, events: tuple, errors: list[dict]) -> dict:
    out = _empty_run("loaded")
    out.update(run_id=run.get("run_id"), state=run.get("state"))
    cursor, sim_minute = run.get("cursor"), run.get("sim_minute")
    valid_cursor = isinstance(cursor, int) and not isinstance(cursor, bool) and 0 <= cursor <= len(events)
    valid_minute = isinstance(sim_minute, int) and not isinstance(sim_minute, bool)
    valid_minute = valid_minute and 0 <= sim_minute <= 90 * 1440
    if sim_minute == 90 * 1440:
        valid_minute = run.get("state") == "STOPPED" and cursor == len(events)
    if run.get("state") not in RUN_STATES:
        _error(errors, "runs", "invalid_run_state")
    if not valid_cursor:
        _error(errors, "runs", "invalid_cursor")
    if not valid_minute:
        _error(errors, "runs", "invalid_simulated_time")
    if not run.get("run_id"):
        _error(errors, "runs", "missing_run_id")
    if errors:
        out["status"] = "error"
        return out
    day_index, minute = divmod(sim_minute, 1440)
    out.update(
        simulated_time={
            "absolute_minute": sim_minute,
            "day_index": day_index,
            "minute": minute,
            "hh_mm": f"{minute // 60:02d}:{minute % 60:02d}",
        },
        cursor=cursor,
        event_count=len(events),
        progress={
            "completed_events": cursor,
            "total_events": len(events),
            "percent": round(cursor * 100 / len(events), 2) if events else 100.0,
        },
        next_event=_event(events[cursor]) if cursor < len(events) else None,
    )
    return out


async def _ticket_projection(collection, query: dict) -> dict:
    total = await collection.count_documents(query)
    observed = {
        state: await collection.count_documents({**query, "status": state})
        for state in TASK_STATES
    }
    known = sum(observed.values())
    if known > total:
        raise RuntimeError("task counts changed during the scoped read")
    counts = {
        "open": observed["pending"],
        "in_progress": observed["in_progress"],
        "completed": observed["completed"],
        "skipped": observed["skipped"],
        "other": total - known,
        "total": total,
    }
    return {"status": "loaded", "counts": counts}


def _null_tickets(status: str) -> dict:
    return {"status": status, "counts": {
        "open": None, "in_progress": None, "completed": None,
        "skipped": None, "other": None, "total": None,
    }}


async def _receipt_projection(collection, query: dict, run: dict, run_view: dict,
                              errors: list[dict]) -> dict | None:
    cursor = run_view.get("cursor")
    receipt_id = run.get("last_evidence_receipt_id")
    if cursor == 0 and not receipt_id:
        return None
    if not receipt_id:
        _error(errors, "receipts", "last_evidence_id_missing")
        return None
    row = await collection.find_one({**query, "receipt_id": receipt_id}, {"_id": 0})
    if row is None:
        _error(errors, "receipts", "last_evidence_not_exact")
        return None
    expected = {
        "simulation_run_id": run.get("run_id"),
        "simulation_event_id": run.get("last_event_id"),
        "execution_cursor": cursor - 1,
    }
    fence = row.get("execution_fence")
    provenance_exact = (
        isinstance(fence, int) and not isinstance(fence, bool) and fence >= 1
        and row.get("status") in {"completed", "failed", "cancelled"}
        and row.get("actor_type") == "simulated-agent"
        and row.get("identity_basis") == "synthetic"
        and row.get("simulated") is True
        and row.get("authority") == "living_community_executor"
    )
    if run.get("last_evidence_status") is not None:
        provenance_exact = provenance_exact and row.get("status") == run["last_evidence_status"]
    if (not provenance_exact
            or any(row.get(key) != value for key, value in expected.items())):
        _error(errors, "receipts", "last_evidence_provenance_mismatch")
        return None
    return {key: row.get(key) for key in (
        "receipt_id", "status", "action_type", "simulation_event_id",
        "execution_cursor", "execution_fence", "actor_id", "actor_name",
        "actor_department", "related_object_type", "related_object_id", "created_at",
    )}


async def runtime_snapshot(*, store=None, events=None) -> dict:
    """Project one exact run without writes or provider access."""
    store = store if store is not None else _default_store()
    errors: list[dict] = []
    sources = {name: _source("unknown") for name in ("runs", "readiness", "tasks", "receipts")}
    run_view = _empty_run("unknown")
    tickets = _null_tickets("unknown")
    staffing = {"status": "unknown", "basis": "deterministic_schedule_at_persisted_simulated_time",
                "day_index": None, "minute": None, "workers": [], "coverage": None, "gaps": None}
    query = {"simulation_scope": SIMULATION_SCOPE, "simulation_community_id": COMMUNITY_ID}
    try:
        runs = await _rows(store.sim_runs, query, {"_id": 0})
        sources["runs"] = _source("loaded")
    except Exception as exc:
        sources["runs"] = _source("error", type(exc).__name__)
        _error(errors, "runs", "read_failed")
        runs = []
    run, selection_error = _select_run(runs) if sources["runs"]["status"] == "loaded" else (None, None)
    if selection_error:
        sources["runs"] = _source("error", selection_error)
        _error(errors, "runs", selection_error)
    if run is None:
        status = "error" if errors else "unknown"
        run_view = _empty_run("error" if errors else "not_started")
        tickets = _null_tickets("error" if errors else "not_started")
        staffing["status"] = "error" if errors else "not_started"
        return _response(status, run_view, tickets, staffing, sources, errors)

    timeline = tuple(events) if events is not None else tuple(_events(run))
    run_view = _run_projection(run, timeline, errors)
    staffing = _staffing(run, run_view)
    scoped = {**query, "simulation_run_id": run.get("run_id")}
    await attach_resident_readiness(run_view, sources, errors, store.receipts, run)
    try:
        tickets = await _ticket_projection(
            store.staff_tasks, {**scoped, "simulated": True}
        )
        sources["tasks"] = _source("loaded")
    except Exception as exc:
        sources["tasks"] = _source("error", type(exc).__name__)
        tickets = _null_tickets("error")
        _error(errors, "tasks", "read_failed")
    try:
        run_view["last_evidence"] = await _receipt_projection(
            store.receipts, scoped, run, run_view, errors
        )
        sources["receipts"] = _source("loaded")
    except Exception as exc:
        sources["receipts"] = _source("error", type(exc).__name__)
        _error(errors, "receipts", "read_failed")
    if errors:
        run_view["status"] = "error" if any(row["source"] in {"runs", "readiness", "receipts"} for row in errors) else run_view["status"]
    return _response("error" if errors else "loaded", run_view, tickets, staffing, sources, errors)


def _response(status: str, run: dict, tickets: dict, staffing: dict,
              sources: dict, errors: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "read_only": True,
        "simulation_scope": SIMULATION_SCOPE,
        "community_id": COMMUNITY_ID,
        "truth_statement": (
            "Counts are exact run-scoped canonical reads; failed or skipped reads remain null. "
            "Staffing is the deterministic schedule at the persisted simulated time, not real attendance."
        ),
        "run": run,
        "tickets": tickets,
        "staffing": staffing,
        "sources": sources,
        "errors": errors,
    }
