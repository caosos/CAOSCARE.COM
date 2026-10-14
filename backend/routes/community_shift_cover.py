"""Owner/admin: cover a simulated worker's shift as a real staff member."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import db, require_admin
from routes.actor_context import actor_from_user
from routes.receipts import create_receipt
from simulation.community_shift_cover import ShiftCoverError, end_cover, start_cover


router = APIRouter(prefix="/simulator/community/shift-cover", tags=["simulator"])


class ShiftCoverInput(BaseModel):
    run_id: str = Field(min_length=1, max_length=160)
    worker_actor_id: str = Field(min_length=1, max_length=160, pattern=r"^sim:staff:")


def _refused(exc: ShiftCoverError):
    raise HTTPException(status_code=409, detail={"code": "shift_cover_refused", "message": str(exc)}) from exc


@router.post("")
async def cover(body: ShiftCoverInput, user=Depends(require_admin)):
    try:
        row = await start_cover(db, create_receipt, run_id=body.run_id,
                                worker_actor_id=body.worker_actor_id,
                                actor=actor_from_user(user, channel="staff_ui"))
    except ShiftCoverError as exc:
        _refused(exc)
    return {"ok": True, "cover": row}


@router.post("/end")
async def end(body: ShiftCoverInput, user=Depends(require_admin)):
    try:
        row = await end_cover(db, create_receipt, run_id=body.run_id,
                              worker_actor_id=body.worker_actor_id,
                              actor=actor_from_user(user, channel="staff_ui"))
    except ShiftCoverError as exc:
        _refused(exc)
    return {"ok": True, "cover": row}
