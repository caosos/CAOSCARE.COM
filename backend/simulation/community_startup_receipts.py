"""Append-only provenance for living-community startup recovery decisions."""

from datetime import datetime
from hashlib import sha256
import json
from typing import Optional

from pymongo.errors import DuplicateKeyError

from models import Receipt
from routes.actor_context import ActorContext
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_run_receipts import snapshot


class StartupReceiptError(RuntimeError):
    """A startup decision could not be durably proven."""


ACTOR = ActorContext(
    actor_id="system:living-community-startup-recovery",
    actor_type="system",
    identity_basis="system",
    channel="system",
    name="Living Community Startup Recovery",
    role="system",
    simulated=False,
)


def _text(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 180:
        raise StartupReceiptError(f"{label} must be 1-180 characters")
    return value.strip()


def recovery_key(startup_id: str, run_id: str) -> str:
    """Stable across retries of one externally identified service startup."""
    return sha256(
        f"living-community-startup:{_text(startup_id, 'startup_id')}:"
        f"{_text(run_id, 'run_id')}".encode()
    ).hexdigest()


def _receipt_id(key: str, phase: str) -> str:
    digest = sha256(f"{key}:{phase}".encode()).hexdigest()[:24]
    return f"rcpt:simstartup:{digest}"


def _document(
    *, run: dict, key: str, phase: str, decision: str, when: datetime,
    parent_receipt_id: Optional[str], reconcile: Optional[dict] = None,
) -> dict:
    run_id = _text(run.get("run_id"), "run_id")
    action = f"simulation_community_startup_recovery_{phase}"
    receipt_id = _receipt_id(key, phase)
    after = {
        "decision": decision,
        "run_state": run.get("state"),
        "cursor": run.get("cursor"),
        "sim_minute": run.get("sim_minute"),
    }
    if reconcile is not None:
        after["reconcile"] = reconcile
    row = Receipt(
        receipt_id=receipt_id,
        action_type=action,
        source="system",
        status="completed",
        result="living-community startup recovery decision recorded",
        completed_at=when,
        related_object_type="simulation_run",
        related_object_id=run_id,
        **ACTOR.receipt_fields(),
        simulation_scope=SIMULATION_SCOPE,
        simulation_community_id=COMMUNITY_ID,
        simulation_run_id=run_id,
        authority=f"simulation_run:{run_id}:startup-recovery",
        parent_receipt_id=parent_receipt_id,
        correlation_id=run.get("origin_receipt_id") or receipt_id,
        before_state=snapshot(run),
        after_state=after,
        result_label="simulated",
        next_state=decision,
        created_at=when,
    ).model_dump()
    row.update(
        _id=receipt_id,
        startup_recovery_key_sha256=key,
        startup_recovery_phase=phase,
        startup_recovery_evidence_sha256=sha256(json.dumps(
            {
                "before": row["before_state"], "after": row["after_state"],
                "parent": row["parent_receipt_id"],
            },
            sort_keys=True, separators=(",", ":"), default=str,
        ).encode()).hexdigest(),
    )
    for field in ("created_at", "completed_at"):
        row[field] = row[field].isoformat()
    return row


def _evidence_digest(row: dict) -> str:
    return sha256(json.dumps(
        {
            "before": row.get("before_state"), "after": row.get("after_state"),
            "parent": row.get("parent_receipt_id"),
        },
        sort_keys=True, separators=(",", ":"), default=str,
    ).encode()).hexdigest()


def _verify(found: Optional[dict], expected: dict, *, historical: bool) -> dict:
    if not isinstance(found, dict):
        raise StartupReceiptError("startup recovery receipt is missing")
    fields = (
        "receipt_id", "action_type", "related_object_type", "related_object_id",
        "actor_id", "actor_type", "identity_basis", "simulated", "authority",
        "simulation_scope", "simulation_community_id", "simulation_run_id",
        "correlation_id",
        "status", "result_label", "startup_recovery_key_sha256",
        "startup_recovery_phase",
    )
    if any(found.get(field) != expected.get(field) for field in fields):
        raise StartupReceiptError("startup recovery receipt provenance conflicts")
    if found.get("startup_recovery_evidence_sha256") != _evidence_digest(found):
        raise StartupReceiptError("startup recovery receipt evidence digest conflicts")
    if historical:
        before, after = found.get("before_state"), found.get("after_state")
        if (
            not isinstance(before, dict) or not isinstance(after, dict)
            or before.get("run_id") != expected["related_object_id"]
            or before.get("state") != "RUNNING"
            or before.get("simulation_scope") != SIMULATION_SCOPE
            or before.get("simulation_community_id") != COMMUNITY_ID
            or after.get("decision") != expected["after_state"]["decision"]
            or after.get("run_state") != "RUNNING"
            or after.get("cursor") != before.get("cursor")
            or after.get("sim_minute") != before.get("sim_minute")
            or not isinstance(found.get("parent_receipt_id"), str)
        ):
            raise StartupReceiptError("historical startup request evidence is invalid")
    elif (
        found.get("startup_recovery_evidence_sha256")
        != expected.get("startup_recovery_evidence_sha256")
        or any(
            found.get(field) != expected.get(field)
            for field in ("parent_receipt_id", "before_state", "after_state")
        )
    ):
        raise StartupReceiptError("startup recovery receipt state evidence conflicts")
    return {key: value for key, value in found.items() if key != "_id"}


async def write_or_verify(
    *, store, run: dict, key: str, phase: str, decision: str, when: datetime,
    parent_receipt_id: Optional[str], reconcile: Optional[dict] = None,
) -> dict:
    """Insert one deterministic receipt or prove the exact prior insert."""
    if phase not in ("requested", "started"):
        raise StartupReceiptError("startup recovery receipt phase is invalid")
    expected = _document(
        run=run, key=_text(key, "recovery key"), phase=phase,
        decision=_text(decision, "decision"), when=when,
        parent_receipt_id=parent_receipt_id, reconcile=reconcile,
    )
    found = await store.receipts.find_one({"_id": expected["_id"]}, {"_id": 0})
    if found:
        return _verify(found, expected, historical=phase == "requested")
    try:
        await store.receipts.insert_one(dict(expected))
    except DuplicateKeyError:
        pass
    except Exception:
        # A network/driver exception after acceptance is ambiguous. Re-read
        # the deterministic id before deciding that the receipt failed.
        found = await store.receipts.find_one({"_id": expected["_id"]}, {"_id": 0})
        if found:
            return _verify(found, expected, historical=phase == "requested")
        raise
    found = await store.receipts.find_one({"_id": expected["_id"]}, {"_id": 0})
    return _verify(found, expected, historical=phase == "requested")
