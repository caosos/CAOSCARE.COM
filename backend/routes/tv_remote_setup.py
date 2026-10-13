"""Resident-voice TV remote commissioning with physical confirmation.

Only server-held catalog candidates can be tested. A live room session and
explicit later-turn speech are required. One-way IR is recorded as SENT /
UNVERIFIED until the resident confirms the physical result; only then is the
device registry updated.
"""
import re
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from deps import db
from device_ir_adapter import execute_ir_blaster
from ir_catalog import candidate, candidates
from models import now_utc, uid
from routes.device_registry_receipts import record_device_change
from routes.receipts import create_receipt
from routes.session_grounding import find_live_session

router = APIRouter(prefix="/devices/public/tv-remote-setup", tags=["devices"])
YES = re.compile(r"\b(yes|yeah|yep|okay|ok|sure|go ahead|try it|it worked|that worked)\b", re.I)
NO = re.compile(r"\b(no|nope|didn'?t work|did not work|nothing happened|not that one)\b", re.I)


class SetupInput(BaseModel):
    phase: Literal["start", "test", "confirm"]
    resident_id: str = Field(min_length=1, max_length=100)
    session_id: str = Field(min_length=1, max_length=100)
    device_id: Optional[str] = Field(default=None, max_length=100)
    vendor: Optional[str] = Field(default=None, max_length=80)
    model: Optional[str] = Field(default=None, max_length=120)
    setup_id: Optional[str] = Field(default=None, max_length=100)
    candidate_id: Optional[str] = Field(default=None, max_length=100)
    confirmation_text: Optional[str] = Field(default=None, max_length=300)
    worked: Optional[bool] = None
    turn_suspect: bool = False


async def _session(body: SetupInput) -> dict:
    found = await find_live_session(body.resident_id, body.session_id)
    if not found:
        raise HTTPException(status_code=403, detail="TV setup is only available during this resident's live conversation")
    return found


async def _tv(room: str, device_id: Optional[str]) -> dict:
    q = {"room": room, "kind": "tv", "online": {"$ne": False}}
    if device_id:
        q["$or"] = [{"device_id": device_id}, {"label": device_id}]
    items = await db.smart_devices.find(q, {"_id": 0}).to_list(10)
    if len(items) != 1:
        detail = "No TV is set up in this room" if not items else "More than one TV is present; name which TV to configure"
        raise HTTPException(status_code=400, detail=detail)
    return items[0]


async def _receipt(action: str, setup: dict, result: str, label: str, before=None, after=None):
    return await create_receipt(
        action_type=action, related_object_type="device", related_object_id=setup["device_id"],
        source="aria_voice", resident_id=setup["resident_id"], room=setup["room"],
        conversation_session_id=setup["session_id"], status="completed", result=result,
        provenance={"actor_id": setup["resident_id"], "actor_type": "resident",
                    "identity_basis": "live_room_session_and_spoken_confirmation",
                    "authority": "resident_room_device_commissioning", "before_state": before,
                    "after_state": after, "result_label": label},
    )


@router.post("")
async def tv_remote_setup(body: SetupInput):
    found = await _session(body)
    room = found.get("room")
    if body.phase == "start":
        tv = await _tv(room, body.device_id)
        options = candidates(body.vendor or "", body.model or "")
        if not options:
            return {"ok": False, "message": "I don't have an approved remote candidate for that brand yet. I did not change the TV."}
        setup = {
            "setup_id": uid("tvsetup"), "resident_id": body.resident_id, "session_id": body.session_id,
            "room": room, "device_id": tv["device_id"], "vendor": (body.vendor or "").strip(),
            "model": (body.model or "").strip(), "candidate_id": options[0]["candidate_id"],
            "state": "candidate_ready", "created_at": now_utc().isoformat(),
        }
        await db.tv_remote_setups.insert_one(setup)
        setup.pop("_id", None)
        await _receipt("tv_remote_candidate_ready", setup, "approved catalog candidate selected", "unverified",
                       after={"candidate_id": setup["candidate_id"], "vendor": setup["vendor"], "model": setup["model"]})
        return {"ok": True, "setup_id": setup["setup_id"], "candidate": options[0],
                "message": "I found one approved match. May I lower the TV volume by one step to test it?"}

    setup = await db.tv_remote_setups.find_one({"setup_id": body.setup_id, "resident_id": body.resident_id,
                                                "session_id": body.session_id}, {"_id": 0})
    if not setup or setup.get("room") != room:
        raise HTTPException(status_code=404, detail="No matching TV setup is active in this conversation")
    if body.candidate_id and body.candidate_id != setup.get("candidate_id"):
        raise HTTPException(status_code=409, detail="That candidate does not match the active TV test")
    cand = candidate(setup["candidate_id"])
    tv = await _tv(room, setup["device_id"])
    spoken = (body.confirmation_text or "").strip()
    if body.turn_suspect:
        raise HTTPException(status_code=409, detail="Please repeat that confirmation clearly")

    if body.phase == "test":
        if setup["state"] != "candidate_ready" or not YES.search(spoken):
            raise HTTPException(status_code=409, detail="I need a clear yes before sending the test")
        trial = {**tv, "protocol": "ir_blaster", "ir_codeset": cand["codeset"]}
        result = await execute_ir_blaster(trial, cand["test_action"], cand["test_value"])
        receipt = await _receipt("tv_remote_test_sent", setup, result["detail"], "unverified",
                                 after={"candidate_id": cand["candidate_id"], "command": "volume down one step"})
        await db.tv_remote_setups.update_one({"setup_id": setup["setup_id"]}, {"$set": {
            "state": "test_sent_unverified", "tested_at": now_utc().isoformat(),
            "test_receipt_id": receipt["receipt_id"],
        }})
        return {"ok": True, "setup_id": setup["setup_id"], "receipt_id": receipt["receipt_id"],
                "message": "I sent one volume-down test. Did the TV volume go down?"}

    if setup["state"] not in ("test_sent_unverified", "confirmed"):
        raise HTTPException(status_code=409, detail="No unconfirmed TV test is waiting")
    explicit_yes, explicit_no = bool(YES.search(spoken)), bool(NO.search(spoken))
    if (body.worked is True and not explicit_yes) or (body.worked is False and not explicit_no):
        raise HTTPException(status_code=409, detail="Please answer clearly whether the TV changed")
    if body.worked is None or explicit_yes == explicit_no:
        raise HTTPException(status_code=409, detail="Please answer yes or no")
    if setup["state"] == "confirmed":
        return {"ok": True, "setup_id": setup["setup_id"], "message": "That remote setting is already saved."}

    trial = {**tv, "protocol": "ir_blaster", "ir_codeset": cand["codeset"]}
    await execute_ir_blaster(trial, cand["test_action"], cand["restore_value"])
    if body.worked is False:
        await db.tv_remote_setups.update_one({"setup_id": setup["setup_id"]},
                                             {"$set": {"state": "rejected", "confirmed_at": now_utc().isoformat(),
                                                       "confirmation_text": spoken}})
        await _receipt("tv_remote_candidate_rejected", setup, "resident said the physical test did not work", "verified")
        return {"ok": True, "setup_id": setup["setup_id"], "message": "Okay. I restored the test step and did not save that remote setting."}

    before = tv
    await db.smart_devices.update_one({"device_id": tv["device_id"]}, {"$set": {
        "protocol": "ir_blaster", "ir_codeset": cand["codeset"], "vendor": setup["vendor"],
        "model": setup["model"] or tv.get("model"),
    }})
    after = await db.smart_devices.find_one({"device_id": tv["device_id"]}, {"_id": 0})
    actor = {"user_id": body.resident_id, "name": body.resident_id, "role": "resident",
             "actor_type": "resident", "identity_basis": "live_room_session_and_spoken_confirmation",
             "authority": "resident_room_device_commissioning"}
    registry_receipt = await record_device_change("updated", tv["device_id"], actor, before=before, after=after,
                                                   note="TV remote candidate physically confirmed by resident")
    await db.tv_remote_setups.update_one({"setup_id": setup["setup_id"]},
                                         {"$set": {"state": "confirmed", "confirmed_at": now_utc().isoformat(),
                                                   "confirmation_text": spoken,
                                                   "registry_receipt_id": registry_receipt["receipt_id"]}})
    await _receipt("tv_remote_candidate_confirmed", setup, "resident confirmed physical test; remote setting saved",
                   "verified", before={"ir_codeset": before.get("ir_codeset")},
                   after={"ir_codeset": cand["codeset"], "registry_receipt_id": registry_receipt["receipt_id"]})
    return {"ok": True, "setup_id": setup["setup_id"], "receipt_id": registry_receipt["receipt_id"],
            "message": "The test worked, I restored the volume step, and I saved that remote setting."}
