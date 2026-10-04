"""Voice bridge: who is speaking, which session, and how a session ends.

Identity: a Home Assistant voice endpoint (Voice PE) is identified by its
HA device id (or satellite entity id). CAOSCare maps that id to exactly one
registered room endpoint (Kiosk.voice_device_ids); the room gives the
resident and the facility gives the community. Nothing here trusts what the
resident says about their room.

Session: one CAOSCare voice session per HA conversation id, bound to the
device that opened it. A closed session is never reused - a later turn with
the same conversation id opens a new session (suffix -r2, -r3, ...).

Ending: a fixed set of closing phrases ends the session without asking the
language model (ARIA contract: deterministic session ending).
"""
import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from deps import db
from routes.realtime_facility import get_active_facility
from routes.resident_assistant_identity import assistant_name

DUPLICATE_WINDOW = timedelta(seconds=10)

_ENDINGS = [re.compile(p) for p in (
    r"(ok(ay)? )?(that'?ll|that will|that'?s|that is) (be )?all( for (now|today|tonight))?( thanks?| thank you)?",
    r"((thank you|thanks)( very much| so much)? )?(good ?bye|bye( bye)?)",
    r"(i'?m|i am) (all )?done( for now| now)?( thanks?| thank you)?",
)]


def normalize(text: str) -> str:
    t = (text or "").lower().replace("’", "'")
    t = re.sub(r"[^a-z' ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def ending_phrase(text: str) -> Optional[str]:
    """The normalized closing phrase if the whole utterance is one, else None.
    The assistant's name is ignored ("Goodbye, Aria"); anything else said
    with it ("I'm done eating, take my tray") is not a closing phrase."""
    names = {"aria", normalize(assistant_name())}
    words = [w for w in normalize(text).split() if w not in names]
    t = " ".join(words)
    if t and any(p.fullmatch(t) for p in _ENDINGS):
        return t
    return None


def turn_key(text: str) -> str:
    return hashlib.sha256(normalize(text).encode()).hexdigest()[:16]


async def resolve_identity(device_ids: list) -> dict:
    """Device -> kiosk -> room -> resident (+ facility). Raises with a reason
    the caller records as a refusal."""
    ids = [d for d in device_ids if d]
    if not ids:
        raise HTTPException(422, "device_id is required")
    kiosks = await db.kiosks.find({"voice_device_ids": {"$in": ids}}, {"_id": 0}).to_list(5)
    if not kiosks:
        raise HTTPException(404, "unknown voice device")
    if len({k["kiosk_id"] for k in kiosks}) > 1:
        raise HTTPException(409, "voice device is mapped to more than one room endpoint")
    kiosk = kiosks[0]
    if not kiosk.get("room"):
        raise HTTPException(404, "room endpoint has no room")
    resident = await db.residents.find_one(
        {"room": kiosk["room"]},
        {"_id": 0, "resident_id": 1, "name": 1, "preferred_name": 1, "synthetic": 1})
    if not resident:
        raise HTTPException(404, "no resident is assigned to this room")
    facility = {}
    if kiosk.get("facility_id"):
        facility = await db.facilities.find_one({"facility_id": kiosk["facility_id"]}, {"_id": 0}) or {}
    facility = facility or await get_active_facility() or {}
    return {"device_id": ids[0], "kiosk_id": kiosk["kiosk_id"], "room": kiosk["room"],
            "resident_id": resident["resident_id"],
            "resident_name": resident.get("preferred_name") or resident.get("name"),
            "synthetic": bool(resident.get("synthetic")),
            "facility_id": facility.get("facility_id"), "facility_name": facility.get("name")}


def _base(conversation_id: str) -> str:
    raw = re.sub(r"[^A-Za-z0-9_-]", "", conversation_id or "")[:64]
    return f"vb_{raw}"


async def ensure_indexes():
    await db.voice_bridge_sessions.create_index("session_id", unique=True)
    await db.voice_bridge_sessions.create_index([("conversation_key", 1), ("status", 1)])


async def open_or_get_session(conversation_id: str, ident: dict) -> dict:
    """The open session for this HA conversation, or a new one. A session is
    bound to the device that opened it; another device using the same
    conversation id is refused."""
    key = _base(conversation_id)
    for _ in range(4):
        open_s = await db.voice_bridge_sessions.find_one(
            {"conversation_key": key, "status": "open"}, {"_id": 0})
        if open_s:
            if open_s["kiosk_id"] != ident["kiosk_id"]:
                raise HTTPException(409, "conversation belongs to another room endpoint")
            return open_s
        n = await db.voice_bridge_sessions.count_documents({"conversation_key": key})
        doc = {"session_id": key if n == 0 else f"{key}-r{n + 1}", "conversation_key": key,
               "ha_conversation_id": conversation_id, "status": "open",
               "device_id": ident["device_id"], "kiosk_id": ident["kiosk_id"],
               "room": ident["room"], "resident_id": ident["resident_id"],
               "facility_id": ident.get("facility_id"), "turn_count": 0,
               "opened_at": datetime.now(timezone.utc), "closed_at": None,
               "origin_receipt_id": None, "last_receipt_id": None,
               "last_turn_key": None, "last_turn_at": None, "last_response": None}
        try:
            await db.voice_bridge_sessions.insert_one(dict(doc))
            return doc
        except DuplicateKeyError:
            continue  # a concurrent first turn created it; read again
    raise HTTPException(503, "could not open a voice session")


async def claim_turn(session: dict, text: str) -> Optional[dict]:
    """Mark this utterance as the session's current turn. Returns the earlier
    turn record if the same utterance arrived within DUPLICATE_WINDOW (an HA
    retry), so it is answered once, not twice."""
    now = datetime.now(timezone.utc)
    key = turn_key(text)
    claimed = await db.voice_bridge_sessions.find_one_and_update(
        {"session_id": session["session_id"],
         "$or": [{"last_turn_key": {"$ne": key}}, {"last_turn_at": {"$lt": now - DUPLICATE_WINDOW}}]},
        {"$set": {"last_turn_key": key, "last_turn_at": now, "last_response": None}})
    if claimed is not None:
        return None
    current = await db.voice_bridge_sessions.find_one({"session_id": session["session_id"]}, {"_id": 0})
    return current or {}


async def record_turn(session_id: str, receipt_id: str, response: dict, *, close: bool = False):
    s = await db.voice_bridge_sessions.find_one({"session_id": session_id}, {"origin_receipt_id": 1})
    update = {"$set": {"last_receipt_id": receipt_id, "last_response": response},
              "$inc": {"turn_count": 1}}
    if not (s or {}).get("origin_receipt_id"):
        update["$set"]["origin_receipt_id"] = receipt_id
    if close:
        update["$set"].update({"status": "closed", "closed_at": datetime.now(timezone.utc)})
    await db.voice_bridge_sessions.update_one({"session_id": session_id}, update)


def session_state(session: dict, *, status: Optional[str] = None, turns: Optional[int] = None) -> dict:
    return {"session_status": status or session.get("status"),
            "turn_count": session.get("turn_count", 0) if turns is None else turns}
