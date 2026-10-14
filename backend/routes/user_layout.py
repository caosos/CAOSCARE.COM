"""Per-user dashboard layout (Live Operations workspace).

GET /me/dashboard-layout?workspace=live_ops   the signed-in user's saved layout
                                              (null = use the default).
PUT /me/dashboard-layout                      save it; `version` must match the
                                              stored one (409 otherwise, so two
                                              open tabs cannot silently overwrite
                                              each other). Each save writes one
                                              receipt naming the user.
DELETE /me/dashboard-layout?workspace=...     back to the default (receipted).

The server stores box positions and visibility only; which boxes exist is the
frontend widget catalog's job, and unknown ids are ignored there.
"""
import re
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from deps import db, get_current_user
from models import now_utc
from routes.actor_context import actor_from_user
from routes.receipts import create_receipt

router = APIRouter(prefix="/me/dashboard-layout", tags=["dashboard-layout"])
WORKSPACES = ("live_ops",)
_ID = re.compile(r"^[a-z0-9_.:-]{1,60}$")


class Box(BaseModel):
    id: str
    x: int = Field(ge=0, le=48)
    y: int = Field(ge=0, le=500)
    w: int = Field(ge=1, le=48)
    h: int = Field(ge=1, le=40)
    hidden: bool = False

    @field_validator("id")
    @classmethod
    def _id(cls, v):
        if not _ID.match(v):
            raise ValueError("invalid box id")
        return v


class LayoutInput(BaseModel):
    workspace: str = "live_ops"
    version: int = Field(ge=0)          # the version this edit started from (0 = none saved)
    boxes: List[Box] = Field(max_length=80)


def _key(user: dict, workspace: str) -> dict:
    if workspace not in WORKSPACES:
        raise HTTPException(422, f"workspace must be one of {', '.join(WORKSPACES)}")
    return {"user_id": user["user_id"], "workspace": workspace}


async def _receipt(user: dict, workspace: str, action: str, before: int, after: int, boxes: list):
    hidden = sum(1 for b in boxes if b.get("hidden"))
    await create_receipt(
        action_type=action, related_object_type="dashboard_layout",
        related_object_id=f"{user['user_id']}:{workspace}", source="staff", requested_by=user["user_id"],
        status="completed", result=f"{len(boxes)} boxes, {hidden} hidden",
        provenance={**actor_from_user(user).receipt_fields(), "authority": "self",
                    "before_state": {"version": before}, "after_state": {"version": after},
                    "result_label": "verified"})


@router.get("")
async def get_layout(workspace: str = "live_ops", user=Depends(get_current_user)):
    doc = await db.user_layouts.find_one(_key(user, workspace), {"_id": 0})
    return {"workspace": workspace, "layout": doc}


@router.put("")
async def save_layout(body: LayoutInput, user=Depends(get_current_user)):
    key = _key(user, body.workspace)
    if len({b.id for b in body.boxes}) != len(body.boxes):
        raise HTTPException(422, "duplicate box id")
    boxes = [b.model_dump() for b in body.boxes]
    new_version = body.version + 1
    doc = {**key, "boxes": boxes, "version": new_version, "updated_at": now_utc().isoformat()}
    if body.version == 0:
        res = await db.user_layouts.update_one(key, {"$setOnInsert": doc}, upsert=True)
        changed = res.upserted_id is not None
    else:
        res = await db.user_layouts.update_one({**key, "version": body.version}, {"$set": doc})
        changed = res.modified_count == 1
    if not changed:
        current = await db.user_layouts.find_one(key, {"_id": 0})
        raise HTTPException(409, {"detail": "layout changed elsewhere", "layout": current})
    await _receipt(user, body.workspace, "dashboard_layout_saved", body.version, new_version, boxes)
    return {"workspace": body.workspace, "layout": doc}


@router.delete("")
async def reset_layout(workspace: str = "live_ops", user=Depends(get_current_user)):
    key = _key(user, workspace)
    before = await db.user_layouts.find_one_and_delete(key)
    if before:
        await _receipt(user, workspace, "dashboard_layout_reset", before.get("version", 0), 0, [])
    return {"workspace": workspace, "layout": None}
