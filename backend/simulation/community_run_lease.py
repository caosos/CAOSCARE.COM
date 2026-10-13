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


async def acquire(
    run_id: str,
    holder_id: str,
    *,
    store=None,
    now: Optional[datetime] = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> dict:
    """Atomically claim an absent/expired lease and return its fence token."""
    if ttl_seconds < 5:
        raise RunLeaseError("lease TTL must be at least 5 seconds")
    holder_id = _holder(holder_id)
    instant = _utc(now)
    expires = instant + timedelta(seconds=ttl_seconds)
    query = {
        **_scope(run_id),
        "state": {"$in": list(ACTIVE)},
        "$or": [
            {"execution_lease": {"$exists": False}},
            {"execution_lease.expires_at": {"$lte": instant.isoformat()}},
        ],
    }
    update = {
        "$inc": {"execution_lease_generation": 1},
        "$set": {
            "execution_lease": {
                "holder_id": holder_id,
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
        "fence": row["execution_lease_generation"],
        "expires_at": row["execution_lease"]["expires_at"],
    }


def _owned(run_id: str, holder_id: str, fence: int, instant: datetime) -> dict:
    if not isinstance(fence, int) or fence < 1:
        raise RunLeaseError("a positive lease fence is required")
    return {
        **_scope(run_id),
        "state": RUNNING,
        "execution_lease_generation": fence,
        "execution_lease.holder_id": _holder(holder_id),
        "execution_lease.expires_at": {"$gt": instant.isoformat()},
    }


async def heartbeat(
    run_id: str,
    holder_id: str,
    fence: int,
    *,
    store=None,
    now: Optional[datetime] = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> dict:
    """Extend a live RUNNING lease; stale owners and paused runs are refused."""
    if ttl_seconds < 5:
        raise RunLeaseError("lease TTL must be at least 5 seconds")
    instant = _utc(now)
    expires = instant + timedelta(seconds=ttl_seconds)
    row = await (store or _store_default()).sim_runs.find_one_and_update(
        _owned(run_id, holder_id, fence, instant),
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
) -> dict:
    """Advance once under the current fence and exact expected cursor."""
    if expected_cursor < 0 or next_cursor != expected_cursor + 1:
        raise RunLeaseError("cursor must advance by exactly one")
    instant = _utc(now)
    query = {**_owned(run_id, holder_id, fence, instant), "cursor": expected_cursor}
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
