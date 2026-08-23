"""Resident conversations as first-class, session-grouped records (Resident
Record -> Conversations). Reuses the existing db.conversations turns (keyed
by session_id, already written by the Realtime pipeline), db.receipts and
db.staff_tasks (keyed by conversation_session_id), and db.realtime_diagnostics
(keyed by session_id) - no new conversation-storage system, just a
session-shaped read over what already exists. Device actions are matched by
room + time-window (best-effort - device_commands isn't session-tagged),
labeled accordingly rather than claimed as certain.
"""
from fastapi import APIRouter, HTTPException, Depends

from deps import db, get_current_user

router = APIRouter(prefix="/residents", tags=["resident-conversations"])


def _is_test_resident(resident: dict) -> bool:
    return (resident.get("name") or "").upper().startswith("TEST") or (resident.get("room") or "").upper().startswith("TEST")


@router.get("/{resident_id}/conversation-sessions")
async def list_conversation_sessions(resident_id: str, user=Depends(get_current_user)):
    resident = await db.residents.find_one({"resident_id": resident_id}, {"_id": 0, "name": 1, "room": 1})
    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")
    turns = await db.conversations.find({"resident_id": resident_id}, {"_id": 0}).sort("created_at", 1).to_list(5000)

    sessions: dict[str, list] = {}
    for t in turns:
        sessions.setdefault(t.get("session_id") or "unknown", []).append(t)

    is_test = _is_test_resident(resident)
    out = []
    for sid, s_turns in sessions.items():
        first, last = s_turns[0], s_turns[-1]
        user_turns = [t for t in s_turns if t.get("role") == "user"]
        topic_src = (user_turns[0] if user_turns else s_turns[0]).get("content") or ""
        room = next((t.get("room") for t in s_turns if t.get("room")), resident.get("room"))
        out.append({
            "session_id": sid,
            "date": first["created_at"][:10],
            "start_at": first["created_at"],
            "end_at": last["created_at"],
            "turn_count": len(s_turns),
            "source": first.get("source"),
            "room": room,
            "is_test": is_test,
            "topic": topic_src[:80],
        })
    out.sort(key=lambda s: s["start_at"], reverse=True)
    return out


@router.get("/{resident_id}/conversation-sessions/{session_id}")
async def get_conversation_session(resident_id: str, session_id: str, user=Depends(get_current_user)):
    turns = await db.conversations.find(
        {"resident_id": resident_id, "session_id": session_id}, {"_id": 0},
    ).sort("created_at", 1).to_list(2000)
    if not turns:
        raise HTTPException(status_code=404, detail="Conversation session not found")

    receipts = await db.receipts.find({"conversation_session_id": session_id}, {"_id": 0}).sort("created_at", 1).to_list(200)
    tasks = await db.staff_tasks.find({"conversation_session_id": session_id}, {"_id": 0}).sort("created_at", 1).to_list(200)
    diagnostics = await db.realtime_diagnostics.find({"session_id": session_id}, {"_id": 0}).sort("created_at", 1).to_list(2000)

    room = next((t.get("room") for t in turns if t.get("room")), None)
    device_actions = []
    if room:
        device_actions = await db.device_commands.find({
            "issued_by": f"kiosk:room:{room}",
            "issued_at": {"$gte": turns[0]["created_at"], "$lte": turns[-1]["created_at"]},
        }, {"_id": 0}).sort("issued_at", 1).to_list(100)

    return {
        "session_id": session_id,
        "turns": turns,
        "receipts": receipts,
        "tasks": tasks,
        "diagnostics": diagnostics,
        "device_actions": device_actions,          # best-effort, room + time-window match, not session-tagged at the source
    }
