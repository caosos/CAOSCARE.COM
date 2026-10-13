"""Default-off owner/admin HTTP controls for the living community."""

from hashlib import sha256
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from deps import db, require_admin
from routes.actor_context import actor_from_user
from simulation.community_atomic_provision import CommunityAtomicProvisionError
from simulation.community_control_capability import control_capability
from simulation.community_control_service import CommunityControlError
from simulation.community_loop_contract import CommunityLoopError
from simulation.community_manual_step import CommunityManualStepError
from simulation.community_run_lease import RunLeaseError
from simulation.community_run_lifecycle import CommunityRunLifecycleError
from simulation.community_runner import CommunityRunnerError
from simulation.community_executor import CommunityExecutorError
from routes.community_runtime_registry import (
    community_process_holder_id,
    community_process_runtime,
)


router = APIRouter(prefix="/simulator/community/controls", tags=["simulator"])
_service = None


class CreatePausedInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_state: Literal["ABSENT"]
    expected_cursor: Literal[0]
    expected_sim_minute: Literal[0]
    operation_key: str = Field(min_length=1, max_length=160, pattern=r".*\S.*")


class PositionedInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1, max_length=200)
    expected_state: Literal["RUNNING", "PAUSED"]
    expected_cursor: int = Field(ge=0)
    expected_sim_minute: int = Field(ge=0)
    operation_key: str = Field(min_length=1, max_length=160, pattern=r".*\S.*")


class ProvisionResidentsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1, max_length=200)
    expected_state: Literal["PAUSED"]
    expected_cursor: int = Field(ge=0)
    expected_sim_minute: int = Field(ge=0)
    operation_key: str = Field(min_length=1, max_length=160, pattern=r".*\S.*")


def _operator(user: dict):
    return actor_from_user(user, channel="staff_ui"), f"admin_override:{user['role']}"


def _controls():
    global _service
    if _service is None:
        return community_process_runtime(db).controls
    return _service


def _holder_id() -> str:
    return community_process_holder_id()


def _operation_key(user: dict, action: str, supplied: str) -> str:
    raw = f"{user['user_id']}:{action}:{supplied.strip()}"
    return f"http:{sha256(raw.encode()).hexdigest()}"


async def _allowed() -> dict:
    capability = await control_capability(db)
    if not capability["mutations_allowed"]:
        raise HTTPException(status_code=503, detail={
            "code": "community_controls_unavailable",
            "message": "Living Community mutations are disabled.",
            "blockers": capability["blockers"],
        })
    return capability


def _refused(exc: Exception):
    raise HTTPException(status_code=409, detail={
        "code": "community_control_refused",
        "message": str(exc),
    }) from exc


@router.get("/capability")
async def capability(user=Depends(require_admin)):
    """Explain mutation gates after a real, read-only transaction probe."""
    return await control_capability(db)


@router.post("/create-paused")
async def create_paused(body: CreatePausedInput, user=Depends(require_admin)):
    await _allowed()
    actor, authority = _operator(user)
    try:
        result = await _controls().create_paused(
            actor, authority, _operation_key(user, "create_paused", body.operation_key),
        )
    except (CommunityControlError, CommunityRunLifecycleError, CommunityLoopError) as exc:
        _refused(exc)
    return {"ok": True, "action": "create_paused", **result}


@router.post("/resume")
async def resume(body: PositionedInput, user=Depends(require_admin)):
    await _allowed()
    if body.expected_state != "PAUSED":
        raise HTTPException(status_code=409, detail="Resume requires exact PAUSED state")
    actor, authority = _operator(user)
    try:
        result = await _controls().resume_and_start(
            actor, authority, body.run_id, body.expected_cursor,
            body.expected_sim_minute,
            _operation_key(user, "resume", body.operation_key), _holder_id(),
        )
    except (CommunityControlError, CommunityRunLifecycleError, CommunityLoopError) as exc:
        _refused(exc)
    return {"ok": True, "action": "resume", **result}


@router.post("/provision-residents")
async def provision_residents(body: ProvisionResidentsInput, user=Depends(require_admin)):
    await _allowed()
    actor, authority = _operator(user)
    try:
        result = await _controls().provision_residents(
            actor, authority, body.run_id, body.expected_cursor,
            body.expected_sim_minute,
            _operation_key(user, "provision_residents", body.operation_key),
        )
    except (CommunityAtomicProvisionError, CommunityControlError) as exc:
        _refused(exc)
    return {"ok": True, "action": "provision_residents", **result}


@router.post("/pause")
async def pause(body: PositionedInput, user=Depends(require_admin)):
    await _allowed()
    if body.expected_state != "RUNNING":
        raise HTTPException(status_code=409, detail="Pause requires exact RUNNING state")
    actor, authority = _operator(user)
    try:
        result = await _controls().pause(
            actor, authority, body.run_id, body.expected_cursor,
            body.expected_sim_minute, _operation_key(user, "pause", body.operation_key),
        )
    except (CommunityControlError, CommunityRunLifecycleError, CommunityLoopError) as exc:
        _refused(exc)
    return {"ok": True, "action": "pause", **result}


@router.post("/stop")
async def stop(body: PositionedInput, user=Depends(require_admin)):
    await _allowed()
    actor, authority = _operator(user)
    try:
        result = await _controls().stop(
            actor, authority, body.run_id, body.expected_state,
            body.expected_cursor, body.expected_sim_minute,
            _operation_key(user, "stop", body.operation_key),
        )
    except (CommunityControlError, CommunityRunLifecycleError, CommunityLoopError) as exc:
        _refused(exc)
    return {"ok": True, "action": "stop", **result}


@router.post("/step")
async def step(body: PositionedInput, user=Depends(require_admin)):
    await _allowed()
    if body.expected_state != "PAUSED":
        raise HTTPException(status_code=409, detail="Step requires exact PAUSED state")
    actor, authority = _operator(user)
    try:
        result = await _controls().step_one(
            actor, authority, body.run_id, body.expected_cursor,
            body.expected_sim_minute,
            _operation_key(user, "step", body.operation_key), _holder_id(),
        )
    except (
        CommunityControlError, CommunityManualStepError,
        CommunityRunLifecycleError, CommunityLoopError, RunLeaseError,
        CommunityRunnerError, CommunityExecutorError,
    ) as exc:
        _refused(exc)
    return {"ok": True, "action": "step", **result}
