"""Explicit, default-off owner/admin reset for one stopped community run."""

from hashlib import sha256
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from deps import db, require_admin
from routes.actor_context import actor_from_user
from simulation.community_control_capability import control_capability
from simulation.community_loop import is_active
from simulation.community_reset import CommunityResetError, reset_living_community


router = APIRouter(prefix="/simulator/community/controls", tags=["simulator"])


class ResetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1, max_length=200, pattern=r".*\S.*")
    expected_state: Literal["STOPPED"]
    confirmation: str = Field(min_length=1, max_length=220)
    operation_key: str = Field(min_length=1, max_length=160, pattern=r".*\S.*")


def confirmation_for(run_id: str) -> str:
    return f"RESET {run_id}"


def _operation_key(user: dict, run_id: str, supplied: str) -> str:
    raw = f"{user['user_id']}:reset:{run_id}:{supplied.strip()}"
    return f"http:{sha256(raw.encode()).hexdigest()}"


async def _allowed() -> None:
    capability = await control_capability(db)
    if not capability["mutations_allowed"]:
        raise HTTPException(status_code=503, detail={
            "code": "community_controls_unavailable",
            "message": "Living Community mutations are disabled.",
            "blockers": capability["blockers"],
        })


async def _reset(body: ResetInput, user: dict) -> dict:
    actor = actor_from_user(user, channel="staff_ui")
    authority = f"admin_override:{user['role']}"
    return await reset_living_community(
        actor, authority,
        _operation_key(user, body.run_id, body.operation_key),
        body.run_id,
        store=db,
    )


@router.post("/reset")
async def reset_community(body: ResetInput, user=Depends(require_admin)):
    if body.confirmation != confirmation_for(body.run_id):
        raise HTTPException(status_code=409, detail={
            "code": "community_reset_confirmation_mismatch",
            "message": "Type the exact run-specific reset confirmation.",
        })
    await _allowed()
    if is_active(body.run_id):
        raise HTTPException(status_code=409, detail={
            "code": "community_reset_loop_active",
            "message": "Stop the local community loop before resetting this run.",
        })
    try:
        result = await _reset(body, user)
    except CommunityResetError as exc:
        raise HTTPException(status_code=409, detail={
            "code": "community_reset_refused", "message": str(exc),
        }) from exc
    return {"ok": True, "action": "reset", **result}
