"""Aria operator memory — deliberately separate from resident memory.

routes/memory.py governs elder-care facts about a resident_id under
docs/CAOSCARE_MEMORY_AUTOMATION_CONTRACT.md. This module stores Michael's
own identity/preferences/projects/commitments, scoped to owner_user_id.
It must never be merged into a resident bulletin, extraction pipeline, or
facility-facing view — that boundary is the whole point of keeping it a
separate module and separate Mongo collection (db.aria_memories).

Two stores, same shape as resident memory:
  db.aria_memories        — discrete standing facts / episodic session notes.
  db.aria_voice_sessions  — session summaries/receipts. No raw audio, ever.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from deps import db, require_owner
from models import (
    AriaMemory, AriaMemoryCreate, AriaMemoryUpdate, default_aria_bin_for_category,
    AriaVoiceSession, AriaVoiceSessionCreate, AriaVoiceSessionEnd, now_utc,
)

router = APIRouter(prefix="/aria", tags=["aria"])


def _iso(doc: dict) -> dict:
    for k in ("created_at", "last_referenced_at", "started_at", "ended_at"):
        v = doc.get(k)
        if v and not isinstance(v, str):
            doc[k] = v.isoformat()
    return doc


# ---------------- Operator memory CRUD ----------------

@router.get("/memory/{owner_user_id}")
async def list_memory(owner_user_id: str, user=Depends(require_owner)):
    items = await db.aria_memories.find(
        {"owner_user_id": owner_user_id}, {"_id": 0},
    ).sort([("pinned", -1), ("importance", -1), ("created_at", -1)]).to_list(500)
    return [_iso(i) for i in items]


@router.post("/memory")
async def create_memory(data: AriaMemoryCreate, user=Depends(require_owner)):
    payload = data.model_dump()
    if not payload.get("bin"):
        payload["bin"] = default_aria_bin_for_category(payload.get("category", "other"))
    m = AriaMemory(**payload)
    doc = m.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.aria_memories.insert_one(doc)
    doc.pop("_id", None)
    return _iso(doc)


@router.patch("/memory/{memory_id}")
async def update_memory(memory_id: str, data: AriaMemoryUpdate, user=Depends(require_owner)):
    patch = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    if not patch:
        raise HTTPException(status_code=400, detail="Nothing to update")
    r = await db.aria_memories.update_one({"memory_id": memory_id}, {"$set": patch})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Memory not found")
    return _iso(await db.aria_memories.find_one({"memory_id": memory_id}, {"_id": 0}))


@router.delete("/memory/{memory_id}")
async def delete_memory(memory_id: str, user=Depends(require_owner)):
    r = await db.aria_memories.delete_one({"memory_id": memory_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"ok": True}


async def build_aria_context_block(owner_user_id: str) -> str:
    """Concise pre-formatted block for the start of a voice session — standing
    facts first (identity/preference/project), then a handful of the most
    recent episodic notes. Mirrors build_memory_context() in routes/memory.py
    but reads db.aria_memories, never db.memories. Shared by the /context
    route below and routes/realtime.py's Aria session builder."""
    standing = await db.aria_memories.find(
        {"owner_user_id": owner_user_id, "bin": "standing", "archived": {"$ne": True}},
        {"_id": 0},
    ).sort([("pinned", -1), ("importance", -1), ("created_at", -1)]).to_list(100)
    episodic = await db.aria_memories.find(
        {"owner_user_id": owner_user_id, "bin": "episodic", "archived": {"$ne": True}},
        {"_id": 0},
    ).sort("created_at", -1).to_list(20)
    if not standing and not episodic:
        return "No standing facts or recent notes on file yet for this person."
    lines = ["Standing facts:"]
    lines += [f"- {m['text']}" for m in standing] if standing else ["- (none yet)"]
    lines += ["Recent notes:"]
    lines += [f"- {m['text']}" for m in episodic] if episodic else ["- (none yet)"]
    return "\n".join(lines)


@router.get("/memory/{owner_user_id}/context")
async def get_context(owner_user_id: str, user=Depends(require_owner)):
    return {"context": await build_aria_context_block(owner_user_id)}


# ---------------- Voice session summaries/receipts ----------------

@router.post("/sessions")
async def start_session(data: AriaVoiceSessionCreate, user=Depends(require_owner)):
    s = AriaVoiceSession(**data.model_dump())
    doc = s.model_dump()
    doc["started_at"] = doc["started_at"].isoformat()
    await db.aria_voice_sessions.insert_one(doc)
    doc.pop("_id", None)
    return _iso(doc)


@router.post("/sessions/{session_id}/end")
async def end_session(session_id: str, data: AriaVoiceSessionEnd, user=Depends(require_owner)):
    existing = await db.aria_voice_sessions.find_one({"session_id": session_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Session not found")
    patch = data.model_dump()
    patch["ended_at"] = now_utc().isoformat()
    await db.aria_voice_sessions.update_one({"session_id": session_id}, {"$set": patch})
    return _iso(await db.aria_voice_sessions.find_one({"session_id": session_id}, {"_id": 0}))


@router.get("/sessions/{owner_user_id}")
async def list_sessions(owner_user_id: str, user=Depends(require_owner)):
    items = await db.aria_voice_sessions.find(
        {"owner_user_id": owner_user_id}, {"_id": 0},
    ).sort("started_at", -1).to_list(200)
    return [_iso(i) for i in items]
