"""Atomic transport-retry protection for the Dot Aria request tool.

The operation id belongs to one assistant tool invocation.  Reusing it with
the same payload returns the original result; reusing it with different input
is a conflict.  A different operation id remains a genuine new resident ask
and therefore goes through the canonical request dedup/re-request policy.
"""
import hashlib
import json
from typing import Optional

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from deps import db
from models import now_utc


def request_fingerprint(*, resident_id: str, room: str, category: str,
                        summary: str, priority: str) -> str:
    canonical = json.dumps({
        "resident_id": resident_id,
        "room": room,
        "category": category,
        "summary": " ".join(summary.split()),
        "priority": priority,
    }, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


async def claim(operation_id: str, fingerprint: str) -> Optional[dict]:
    """Claim once, or return the already completed response for a retry."""
    now = now_utc().isoformat()
    try:
        await db.dot_aria_operations.insert_one({
            "_id": operation_id,
            "fingerprint": fingerprint,
            "state": "processing",
            "created_at": now,
            "updated_at": now,
        })
        return None
    except DuplicateKeyError:
        existing = await db.dot_aria_operations.find_one({"_id": operation_id})
        if not existing or existing.get("fingerprint") != fingerprint:
            raise HTTPException(409, "Operation ID was already used for different request details")
        if existing.get("state") == "completed" and isinstance(existing.get("response"), dict):
            response = dict(existing["response"])
            response["idempotent_replay"] = True
            return response
        raise HTTPException(409, "This operation is already being processed; retry the same operation ID")


async def complete(operation_id: str, response: dict) -> None:
    result = await db.dot_aria_operations.update_one(
        {"_id": operation_id, "state": "processing"},
        {"$set": {"state": "completed", "response": response, "updated_at": now_utc().isoformat()}},
    )
    if result.modified_count != 1:
        # The task may already exist, so never retry the write path here.
        raise RuntimeError("Dot Aria operation result could not be committed safely")


async def mark_failed_unknown(operation_id: str, reason: str) -> None:
    """Latch uncertainty. A later retry must not create a duplicate task."""
    await db.dot_aria_operations.update_one(
        {"_id": operation_id, "state": "processing"},
        {"$set": {
            "state": "failed_unknown",
            "failure": reason[:160],
            "updated_at": now_utc().isoformat(),
        }},
    )
