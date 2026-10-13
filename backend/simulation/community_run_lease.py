"""Durable execution lease for the living-community simulator.

This module does not start a loop or execute work.  It supplies the atomic
Mongo boundary a future executor must use so only one process can own a run
and only that fenced owner can advance its cursor.  The lease lives on the
canonical ``sim_runs`` row and is bound to the exact living-community scope.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from pymongo import ReturnDocument

from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE


RUNNING = "RUNNING"
PAUSED = "PAUSED"
ACTIVE = (RUNNING, PAUSED)
DEFAULT_TTL_SECONDS = 30
RUNNER_MODE = "runner"
MANUAL_STEP_MODE = "manual_step"
LEASE_MODES = (RUNNER_MODE, MANUAL_STEP_MODE)


class RunLeaseError(RuntimeError):
    """A lease operation was refused without changing the run."""


def _store_default():
    from deps import db

    return db


def _utc(value: Optional[datetime] = None) -> datetime:
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None:
        raise RunLeaseError("lease timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def _scope(run_id: str) -> dict:
    if not run_id:
        raise RunLeaseError("run_id is required")
    return {
        "run_id": run_id,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
    }


def _holder(holder_id: str) -> str:
    holder_id = (holder_id or "").strip()
    if not holder_id:
        raise RunLeaseError("lease holder_id is required")
    return holder_id


def _mode(mode: str) -> str:
    if mode not in LEASE_MODES:
        raise RunLeaseError("execution lease mode is invalid")
    return mode


def ownership_fields(
    holder_id: str, fence: int, instant: datetime, *, mode: str = RUNNER_MODE,
) -> dict:
    """Exact live-lease predicates shared with transactional controls."""
    if not isinstance(fence, int) or isinstance(fence, bool) or fence < 1:
        raise RunLeaseError("a positive lease fence is required")
    mode = _mode(mode)
    fields = {
        "execution_lease_generation": fence,
        "execution_lease.holder_id": _holder(holder_id),
        "execution_lease.expires_at": {"$gt": _utc(instant).isoformat()},
    }
    if mode == MANUAL_STEP_MODE:
        fields["execution_lease.mode"] = mode
    return fields


def owns_snapshot(
    row: dict, holder_id: str, fence: int, instant: datetime,
    *, mode: str = RUNNER_MODE,
) -> bool:
    """Validate an already-read run against exact live lease ownership."""
    mode = _mode(mode)
    execution = (row or {}).get("execution_lease") or {}
    try:
        expires = datetime.fromisoformat(execution.get("expires_at"))
    except (TypeError, ValueError):
        return False
    return bool(
        row
        and row.get("state") == (PAUSED if mode == MANUAL_STEP_MODE else RUNNING)
        and row.get("execution_lease_generation") == fence
        and execution.get("holder_id") == _holder(holder_id)
        and (mode != MANUAL_STEP_MODE or execution.get("mode") == mode)
        and expires.tzinfo is not None
        and expires.astimezone(timezone.utc) > _utc(instant)
    )


def claim_matches(claim: dict, run_id: str, holder_id: str, mode: str) -> bool:
    fence = claim.get("fence") if isinstance(claim, dict) else None
    return bool(
        isinstance(fence, int) and not isinstance(fence, bool) and fence >= 1
        and claim.get("run_id") == run_id
        and claim.get("holder_id") == holder_id
        and claim.get("mode", RUNNER_MODE) == mode
    )


async def acquire(
    run_id: str,
    holder_id: str,
    *,
    store=None,
    now: Optional[datetime] = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    mode: str = RUNNER_MODE,
    expected_cursor: Optional[int] = None,
    expected_sim_minute: Optional[int] = None,
) -> dict:
    """Atomically claim an absent/expired lease and return its fence token."""
    if ttl_seconds < 5:
        raise RunLeaseError("lease TTL must be at least 5 seconds")
    holder_id = _holder(holder_id)
    mode = _mode(mode)
    instant = _utc(now)
    expires = instant + timedelta(seconds=ttl_seconds)
    query = {
        **_scope(run_id),
        "state": PAUSED if mode == MANUAL_STEP_MODE else {"$in": list(ACTIVE)},
        "$or": [
            {"execution_lease": {"$exists": False}},
            {"execution_lease.expires_at": {"$lte": instant.isoformat()}},
        ],
    }
    for field, value in (("cursor", expected_cursor), ("sim_minute", expected_sim_minute)):
        if value is not None:
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise RunLeaseError(f"expected {field} must be a non-negative integer")
            query[field] = value
    update = {
        "$inc": {"execution_lease_generation": 1},
        "$set": {
            "execution_lease": {
                "holder_id": holder_id,
                "mode": mode,
                "acquired_at": instant.isoformat(),
                "heartbeat_at": instant.isoformat(),
                "expires_at": expires.isoformat(),
            },
            "updated_at": instant.isoformat(),
        },
    }
    row = await (store or _store_default()).sim_runs.find_one_and_update(
        query, update, projection={"_id": 0}, return_document=ReturnDocument.AFTER
    )
    if not row:
        raise RunLeaseError("run is missing, out of scope, stopped, or already leased")
    return {
        "run_id": run_id,
        "holder_id": holder_id,
        "mode": mode,
        "fence": row["execution_lease_generation"],
        "expires_at": row["execution_lease"]["expires_at"],
    }


def _owned(
    run_id: str, holder_id: str, fence: int, instant: datetime,
    *, mode: str = RUNNER_MODE,
) -> dict:
    mode = _mode(mode)
    return {
        **_scope(run_id),
        "state": PAUSED if mode == MANUAL_STEP_MODE else RUNNING,
        **ownership_fields(holder_id, fence, instant, mode=mode),
    }


async def heartbeat(
    run_id: str,
    holder_id: str,
    fence: int,
    *,
    store=None,
    now: Optional[datetime] = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    mode: str = RUNNER_MODE,
) -> dict:
    """Extend a live mode-compatible lease; stale ownership is refused."""
    if ttl_seconds < 5:
        raise RunLeaseError("lease TTL must be at least 5 seconds")
    instant = _utc(now)
    expires = instant + timedelta(seconds=ttl_seconds)
    row = await (store or _store_default()).sim_runs.find_one_and_update(
        _owned(run_id, holder_id, fence, instant, mode=mode),
        {"$set": {
            "execution_lease.heartbeat_at": instant.isoformat(),
            "execution_lease.expires_at": expires.isoformat(),
            "updated_at": instant.isoformat(),
        }},
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER,
    )
    if not row:
        raise RunLeaseError("lease heartbeat refused: ownership, fence, state, or expiry changed")
    return row


async def advance_cursor(
    run_id: str,
    holder_id: str,
    fence: int,
    expected_cursor: int,
    next_cursor: int,
    *,
    store=None,
    now: Optional[datetime] = None,
    fields: Optional[dict] = None,
    mode: str = RUNNER_MODE,
) -> dict:
    """Advance once under the current fence and exact expected cursor."""
    if expected_cursor < 0 or next_cursor != expected_cursor + 1:
        raise RunLeaseError("cursor must advance by exactly one")
    instant = _utc(now)
    query = {
        **_owned(run_id, holder_id, fence, instant, mode=mode),
        "cursor": expected_cursor,
    }
    reserved = {
        "run_id", "simulation_scope", "simulation_community_id", "state",
        "cursor", "execution_lease", "execution_lease_generation",
    }
    extra = dict(fields or {})
    if reserved.intersection(extra):
        raise RunLeaseError("cursor metadata cannot replace protected run fields")
    row = await (store or _store_default()).sim_runs.find_one_and_update(
        query,
        {"$set": {**extra, "cursor": next_cursor, "updated_at": instant.isoformat()}},
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER,
    )
    if not row:
        raise RunLeaseError("cursor advance refused: lease, state, expiry, or cursor changed")
    return row


async def release(
    run_id: str,
    holder_id: str,
    fence: int,
    *,
    store=None,
    now: Optional[datetime] = None,
) -> dict:
    """Release only the exact fenced lease; generation remains as history."""
    instant = _utc(now)
    query = {
        **_scope(run_id),
        "execution_lease_generation": fence,
        "execution_lease.holder_id": _holder(holder_id),
    }
    row = await (store or _store_default()).sim_runs.find_one_and_update(
        query,
        {"$unset": {"execution_lease": ""}, "$set": {"updated_at": instant.isoformat()}},
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER,
    )
    if not row:
        raise RunLeaseError("lease release refused: ownership or fence changed")
    return row
