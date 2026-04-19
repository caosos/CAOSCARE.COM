"""Resident long-term memory — the Python-backed memory server.

Philosophy
  CAOS is not Alexa. Every resident has a lifelong companion that grows with
  them. We keep two parallel stores:

  1. db.conversations   — rolling conversation log. The last N messages are
     replayed into Claude every turn so the AI stays coherent across days.
  2. db.memories        — discrete, human-readable facts the AI has learned
     ("Frank's dog Bruno died in 2023"; "Margaret hates the red chair").
     Pinned memories never drop out of context. Importance scores let us
     keep the most-trusted facts front-and-center when the context window
     gets tight.

Flow
  1. Every /api/ai/chat turn writes a row to db.conversations.
  2. A background extractor (fire-and-forget after the reply is sent) runs
     Claude on the latest exchange and proposes new ResidentMemory rows.
  3. Admins + staff can manually add / edit / pin memories at any time.

Retrieval
  build_memory_context(resident_id) returns a pre-formatted block of
  memories + the last 40 messages that /api/ai/chat injects into its
  system prompt.
"""
import os
import json
import logging
import re
from datetime import timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps import db, get_current_user
from models import (
    ResidentMemory, ResidentMemoryCreate, ResidentMemoryUpdate, now_utc, uid,
)

from emergentintegrations.llm.chat import LlmChat, UserMessage

router = APIRouter(prefix="/memory", tags=["memory"])

EMERGENT_KEY = os.environ["EMERGENT_LLM_KEY"]
MAX_HISTORY_MESSAGES = 40
MAX_MEMORIES_IN_CONTEXT = 25

EXTRACTOR_SYSTEM = """You read the most recent exchange between a senior living
resident and their AI companion. Your only job is to extract durable facts
worth remembering for months or years. Output ONLY a JSON array (no prose).
Each item: {"text": "...", "category": "family|preferences|health|history|daily_pattern|concern|relationship|milestone|other", "importance": 1-5}

RULES
- Skip small-talk, weather, greetings, reassurance.
- Skip info already widely known (e.g. "she is a resident").
- Prefer first-person factual claims: names, dates, relationships, likes, dislikes, routines, fears, keepsakes, past jobs, hobbies.
- 'importance': 5 = life-critical/emotionally central; 4 = core identity; 3 = useful context; 2 = minor; 1 = barely worth keeping.
- Output [] if nothing is worth storing. Never output null."""


def _iso(doc: dict) -> dict:
    for k in ("created_at", "last_referenced_at"):
        v = doc.get(k)
        if v and not isinstance(v, str):
            doc[k] = v.isoformat()
    return doc


# ---------------- Retrieval helpers (used by routes/ai.py) ----------------

async def get_recent_conversation(resident_id: str, limit: int = MAX_HISTORY_MESSAGES) -> List[dict]:
    if not resident_id:
        return []
    msgs = await db.conversations.find(
        {"resident_id": resident_id}, {"_id": 0},
    ).sort("created_at", -1).to_list(limit)
    msgs.reverse()
    for m in msgs:
        _iso(m)
    return msgs


async def get_top_memories(resident_id: str, limit: int = MAX_MEMORIES_IN_CONTEXT) -> List[dict]:
    if not resident_id:
        return []
    # Pinned first, then by importance desc, then recency
    pinned = await db.memories.find(
        {"resident_id": resident_id, "pinned": True}, {"_id": 0},
    ).sort("importance", -1).to_list(limit)
    remaining = max(limit - len(pinned), 0)
    if remaining:
        rest = await db.memories.find(
            {"resident_id": resident_id, "pinned": {"$ne": True}}, {"_id": 0},
        ).sort([("importance", -1), ("created_at", -1)]).to_list(remaining)
    else:
        rest = []
    out = pinned + rest
    for m in out:
        _iso(m)
    return out


async def append_conversation(resident_id: Optional[str], session_id: str, role: str, content: str) -> None:
    if not resident_id:
        return
    await db.conversations.insert_one({
        "conv_id": uid("conv"),
        "resident_id": resident_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "created_at": now_utc().isoformat(),
    })


async def mark_referenced(memory_ids: List[str]) -> None:
    if not memory_ids:
        return
    await db.memories.update_many(
        {"memory_id": {"$in": memory_ids}},
        {"$set": {"last_referenced_at": now_utc().isoformat()}, "$inc": {"times_referenced": 1}},
    )


async def build_memory_context(resident_id: Optional[str]) -> dict:
    """Return {'memories_block': str, 'history': [{'role','content'}], 'memory_ids': [...]}."""
    if not resident_id:
        return {"memories_block": "", "history": [], "memory_ids": []}
    memories = await get_top_memories(resident_id)
    history = await get_recent_conversation(resident_id)
    memory_ids = [m["memory_id"] for m in memories]
    lines = []
    for m in memories:
        star = "★ " if m.get("pinned") else ""
        lines.append(f"{star}[{m.get('category','other')} · i{m.get('importance',3)}] {m['text']}")
    block = "\n".join(lines) if lines else "(no long-term memories yet)"
    return {
        "memories_block": block,
        "history": [{"role": h["role"], "content": h["content"]} for h in history],
        "memory_ids": memory_ids,
    }


# ---------------- Extraction (runs async after each AI reply) ----------------

async def extract_and_store_memories(resident_id: str, session_id: str, user_text: str, assistant_text: str) -> int:
    """Lightweight Claude call that reads the latest exchange and proposes memories.
    Runs best-effort; swallows all errors so a flaky extraction never breaks chat."""
    if not resident_id or not user_text:
        return 0
    try:
        prompt = (
            f"User said: \"{user_text}\"\nCAOS replied: \"{assistant_text}\"\n\n"
            f"Return JSON array of new durable memories."
        )
        llm = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=f"extractor-{resident_id}",
            system_message=EXTRACTOR_SYSTEM,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        raw = await llm.send_message(UserMessage(text=prompt))
        raw = (raw or "").strip()
        # Strip code fences if Claude wraps it
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw.rsplit("```", 1)[0]
            if raw.lstrip().startswith("json"):
                raw = raw.split("\n", 1)[1]
        items = json.loads(raw)
        if not isinstance(items, list):
            return 0
        saved = 0
        for it in items:
            text = (it.get("text") or "").strip()
            if not text or len(text) > 400:
                continue
            # Dedupe by resident_id + near-identical text prefix (first 60 chars, regex-safe)
            prefix = re.escape(text[:60].strip())
            existing = await db.memories.find_one({
                "resident_id": resident_id,
                "text": {"$regex": f"^{prefix}", "$options": "i"},
            }, {"_id": 0})
            if existing:
                continue
            m = ResidentMemory(
                resident_id=resident_id,
                text=text,
                category=it.get("category", "other"),
                importance=int(it.get("importance", 3)) if it.get("importance") is not None else 3,
                source="extraction",
                source_session=session_id,
            )
            doc = m.model_dump()
            doc["created_at"] = doc["created_at"].isoformat()
            await db.memories.insert_one(doc)
            saved += 1
        return saved
    except Exception as e:
        logging.warning(f"Memory extraction failed for resident {resident_id}: {e}")
        return 0


# ---------------- REST routes (admin / staff UI) ----------------

@router.get("/{resident_id}")
async def list_memories(resident_id: str, user=Depends(get_current_user)):
    items = await db.memories.find(
        {"resident_id": resident_id}, {"_id": 0},
    ).sort([("pinned", -1), ("importance", -1), ("created_at", -1)]).to_list(500)
    for i in items:
        _iso(i)
    return items


@router.post("")
async def create_memory(data: ResidentMemoryCreate, user=Depends(get_current_user)):
    r = await db.residents.find_one({"resident_id": data.resident_id}, {"_id": 0, "name": 1})
    if not r:
        raise HTTPException(status_code=404, detail="Resident not found")
    m = ResidentMemory(**data.model_dump())
    doc = m.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.memories.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.patch("/{memory_id}")
async def update_memory(memory_id: str, data: ResidentMemoryUpdate, user=Depends(get_current_user)):
    patch = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    if not patch:
        raise HTTPException(status_code=400, detail="Nothing to update")
    r = await db.memories.update_one({"memory_id": memory_id}, {"$set": patch})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Memory not found")
    return _iso(await db.memories.find_one({"memory_id": memory_id}, {"_id": 0}))


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str, user=Depends(get_current_user)):
    r = await db.memories.delete_one({"memory_id": memory_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"ok": True}


class ExtractRequest(BaseModel):
    resident_id: str
    user_text: str
    assistant_text: str
    session_id: Optional[str] = ""


@router.post("/extract")
async def manual_extract(data: ExtractRequest, user=Depends(get_current_user)):
    """Admin convenience: force-extract memories from a specific exchange."""
    saved = await extract_and_store_memories(
        data.resident_id, data.session_id or "manual", data.user_text, data.assistant_text,
    )
    return {"ok": True, "saved": saved}


# ---------------- Conversation log ----------------

@router.get("/conversation/{resident_id}")
async def conversation_history(resident_id: str, limit: int = 200, user=Depends(get_current_user)):
    items = await db.conversations.find(
        {"resident_id": resident_id}, {"_id": 0},
    ).sort("created_at", -1).to_list(limit)
    items.reverse()
    for i in items:
        _iso(i)
    return items
