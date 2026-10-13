"""Paused-only adapter for the first living-community burn-in workflow.

The adapter is intentionally tiny: a synthetic resident raises one shower-
assistance request and an on-shift simulated Nursing/Care worker acknowledges
it.  Both writes go through the existing canonical request/task lifecycle.
This module never writes Mongo directly, calls a provider, or creates a User.

``simulation_run_id`` makes resident-request notification delivery simulated,
so the canonical notification path records evidence without contacting a real
provider.  Read-side guards and a process-local lock make repeated manual steps
idempotent in the backend's existing single-process simulator model.
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

from deps import db
from routes import task_actions
from routes.actor_context import ActorContext
from routes.resident_requests import ResidentRequestInput, create_resident_request
from routes.task_lifecycle import load
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE


PAUSED = "PAUSED"
SHOWER_WORDS = "I would like help with my shower, please."
NURSING_DEPARTMENT = "nursing"
_lock = asyncio.Lock()


class BurnInAdapterError(RuntimeError):
    """The manual step was refused before any canonical state change."""


@dataclass(frozen=True)
class ShiftWindow:
    start_minute: int
    end_minute: int

    def __post_init__(self) -> None:
        if not 0 <= self.start_minute < 24 * 60 or not 0 <= self.end_minute < 24 * 60:
            raise ValueError("shift minutes must be within one 24-hour day")
        if self.start_minute == self.end_minute:
            raise ValueError("shift start and end must differ")

    def contains(self, minute: int) -> bool:
        if not 0 <= minute < 24 * 60:
            return False
        if self.start_minute <= self.end_minute:
            return self.start_minute <= minute < self.end_minute
        return minute >= self.start_minute or minute < self.end_minute


@dataclass(frozen=True)
class BurnInStepResult:
    action: str
    task_id: str
    receipt_id: str
    parent_receipt_id: Optional[str]
    correlation_id: str
    idempotent_replay: bool


async def _paused_run(run_id: str) -> dict:
    run = await db.sim_runs.find_one({"run_id": run_id}, {"_id": 0})
    if not run:
        raise BurnInAdapterError(f"Unknown simulation run {run_id}")
    if run.get("state") != PAUSED:
        raise BurnInAdapterError(
            f"Manual burn-in steps require PAUSED; run is {run.get('state') or 'unknown'}"
        )
    if (
        run.get("simulation_scope") != SIMULATION_SCOPE
        or run.get("simulation_community_id") != COMMUNITY_ID
    ):
        raise BurnInAdapterError("Run is not bound to the living-community burn-in")
    return run


async def _synthetic_resident(resident_id: str, room: str) -> dict:
    resident = await db.residents.find_one({"resident_id": resident_id}, {"_id": 0})
    if not resident or not resident.get("synthetic"):
        raise BurnInAdapterError("Burn-in steps require an existing synthetic resident")
    if (
        resident.get("simulation_scope") != SIMULATION_SCOPE
        or resident.get("simulation_community_id") != COMMUNITY_ID
    ):
        raise BurnInAdapterError("Resident is not part of the living-community burn-in")
    if resident.get("room") != room:
        raise BurnInAdapterError("Resident room does not match the canonical resident record")
    return resident


async def _request_for(run_id: str, resident_id: str) -> Optional[dict]:
    return await db.staff_tasks.find_one({
        "simulation_run_id": run_id,
        "resident_id": resident_id,
        "category": NURSING_DEPARTMENT,
        "resident_words": SHOWER_WORDS,
    }, {"_id": 0})


async def _receipt(task_id: str, action_type: str) -> Optional[dict]:
    return await db.receipts.find_one({
        "related_object_type": "task",
        "related_object_id": task_id,
        "action_type": action_type,
    }, {"_id": 0}, sort=[("created_at", 1)])


def _validate_task(task: dict, run_id: str, resident_id: str) -> None:
    if not task.get("simulated") or task.get("simulation_run_id") != run_id:
        raise BurnInAdapterError("Task is not simulated work from this run")
    if task.get("resident_id") != resident_id or task.get("visibility_role") != NURSING_DEPARTMENT:
        raise BurnInAdapterError("Task is not this resident's Nursing/Care request")
    if (
        task.get("simulation_scope") != SIMULATION_SCOPE
        or task.get("simulation_community_id") != COMMUNITY_ID
    ):
        raise BurnInAdapterError("Task is not living-community burn-in work")


def _result(action: str, task_id: str, receipt: dict, replay: bool) -> BurnInStepResult:
    correlation = receipt.get("correlation_id") or receipt.get("receipt_id")
    if not receipt.get("receipt_id") or not correlation:
        raise BurnInAdapterError("Canonical receipt is missing workflow provenance")
    return BurnInStepResult(
        action=action,
        task_id=task_id,
        receipt_id=receipt["receipt_id"],
        parent_receipt_id=receipt.get("parent_receipt_id"),
        correlation_id=correlation,
        idempotent_replay=replay,
    )


async def create_shower_help_request(run_id: str, resident_id: str, room: str) -> BurnInStepResult:
    """Create the request once through ``create_resident_request``.

    The canonical service refuses a non-synthetic resident, records the task
    and origin receipt, routes it to Nursing/Care, and suppresses real provider
    delivery because ``simulation_run_id`` is present.
    """
    async with _lock:
        await _paused_run(run_id)
        await _synthetic_resident(resident_id, room)
        existing = await _request_for(run_id, resident_id)
        if existing:
            _validate_task(existing, run_id, resident_id)
            origin = await _receipt(existing["task_id"], "resident_request_created")
            if not origin:
                raise BurnInAdapterError("Existing request has no canonical origin receipt")
            return _result("request", existing["task_id"], origin, True)

        created = await create_resident_request(
            ResidentRequestInput(
                category=NURSING_DEPARTMENT,
                resident_id=resident_id,
                room=room,
                resident_words=SHOWER_WORDS,
                summary=SHOWER_WORDS,
                priority="high",
                source="aria_voice",
            ),
            simulation_run_id=run_id,
        )
        task = await load(created["task_id"])
        _validate_task(task, run_id, resident_id)
        origin = await _receipt(task["task_id"], "resident_request_created")
        if not origin:
            raise BurnInAdapterError("Canonical request did not produce an origin receipt")
        return _result("request", task["task_id"], origin, False)


def _staff_profile(actor: ActorContext) -> dict:
    if (
        not actor.simulated
        or actor.actor_type != "simulated-agent"
        or actor.identity_basis != "synthetic"
        or actor.channel != "simulator"
        or actor.role != "staff"
        or actor.department != NURSING_DEPARTMENT
    ):
        raise BurnInAdapterError("Acknowledgement requires a simulated Nursing/Care staff actor")
    return {
        "user_id": actor.actor_id,
        "name": actor.name,
        "role": "staff",
        "department": NURSING_DEPARTMENT,
        "simulated": True,
    }


async def acknowledge_shower_help_request(
    run_id: str,
    resident_id: str,
    task_id: str,
    *,
    actor: ActorContext,
    shift: ShiftWindow,
    sim_minute: int,
) -> BurnInStepResult:
    """Acknowledge once through ``task_actions`` with chained provenance."""
    async with _lock:
        await _paused_run(run_id)
        profile = _staff_profile(actor)
        if not shift.contains(sim_minute):
            raise BurnInAdapterError("Simulated Nursing/Care worker is off shift")
        task = await load(task_id)
        _validate_task(task, run_id, resident_id)

        existing = await _receipt(task_id, "task_acknowledged")
        if existing:
            return _result("acknowledge", task_id, existing, True)

        _after, receipt = await task_actions.acknowledge(task_id, actor, profile)
        receipt = receipt or await _receipt(task_id, "task_acknowledged")
        if not receipt or not receipt.get("parent_receipt_id"):
            raise BurnInAdapterError("Canonical acknowledgement lacks its parent receipt link")
        return _result("acknowledge", task_id, receipt, False)
