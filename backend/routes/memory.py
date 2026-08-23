"""Resident long-term memory — the Python-backed memory server.

Philosophy
  CAOS is not Alexa. Every resident has a lifelong companion that grows with
  them. We keep two parallel stores:

  1. db.conversations   — rolling conversation log. The last N messages are
     replayed into the OpenAI text model every turn so the AI stays coherent across days.
  2. db.memories        — discrete, human-readable facts the AI has learned
     ("Frank's dog Bruno died in 2023"; "Margaret hates the red chair").
     Pinned memories never drop out of context. Importance scores let us
     keep the most-trusted facts front-and-center when the context window
     gets tight.

Flow
  1. Every /api/ai/chat turn writes a row to db.conversations.
  2. A background extractor (fire-and-forget after the reply is sent) runs
     the OpenAI text model on the latest exchange and proposes new ResidentMemory rows.
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
import asyncio
import requests
from datetime import timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps import db, get_current_user, require_owner
from models import (
    ResidentMemory, ResidentMemoryCreate, ResidentMemoryUpdate, now_utc, uid,
    default_bin_for_category,
)

router = APIRouter(prefix="/memory", tags=["memory"])

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
OPENAI_TEXT_MODEL = os.environ.get("OPENAI_TEXT_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
OPENAI_API_BASE = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/")


def _openai_unavailable() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail="OPENAI_API_KEY is not configured; OpenAI memory extraction is unavailable.",
    )


def _post_openai_chat(system_message: str, user_message: str) -> str:
    if not OPENAI_API_KEY:
        raise _openai_unavailable()
    resp = requests.post(
        f"{OPENAI_API_BASE}/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": OPENAI_TEXT_MODEL,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
        },
        timeout=60,
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"OpenAI memory extraction failed: {resp.text[:300]}")
    data = resp.json()
    return (data.get("choices") or [{}])[0].get("message", {}).get("content", "")


async def _openai_chat(system_message: str, user_message: str) -> str:
    return await asyncio.to_thread(_post_openai_chat, system_message, user_message)

# OpenAI text models have a large context window. We previously capped history
# at 40 to keep prompts cheap, but that meant rich conversations aged out
# before important context could dehydrate into the bins. Raise the rolling
# window to 500 turns; the dehydration pipeline + two-bin bulletin do the
# heavy lifting for anything older.
MAX_HISTORY_MESSAGES = 500
MAX_FACTS_IN_CONTEXT = 40   # durable identity facts (Personal Facts bin)
MAX_EVENTS_IN_CONTEXT = 25  # dated moments (Life Events bin)

EXTRACTOR_SYSTEM = """You read the most recent exchange between a senior living
resident and their AI companion. Your only job is to extract durable facts
worth remembering for months or years. Output ONLY a JSON array (no prose).
Each item: {"text": "...", "category": "family|preferences|health|history|daily_pattern|concern|relationship|milestone|other", "importance": 1-5}

RULES
- Skip small-talk, weather, greetings, reassurance.
- Skip info already widely known (e.g. "she is a resident").
- Prefer first-person factual claims: names, dates, relationships, likes, dislikes, routines, fears, keepsakes, past jobs, hobbies.
- 2026-08-22 (real bug, confirmed live): NEVER extract a scheduled
  appointment, errand, or transportation arrangement (e.g. "has a doctor's
  appointment at 3 PM", "is going to the pharmacy Tuesday") as a durable
  fact. Those already have their own authoritative record (the resident
  request/transportation system) - re-deriving them into an undated
  "durable identity" fact is what caused a real resident to be told about
  a fabricated permanent 3 PM appointment in an unrelated later
  conversation. A transportation request is proof a ride was arranged,
  never proof an appointment exists or is confirmed.
- 'importance': 5 = life-critical/emotionally central; 4 = core identity; 3 = useful context; 2 = minor; 1 = barely worth keeping.
- Output [] if nothing is worth storing. Never output null."""


def _iso(doc: dict) -> dict:
    for k in ("created_at", "last_referenced_at", "event_at"):
        v = doc.get(k)
        if v and not isinstance(v, str):
            doc[k] = v.isoformat()
    return doc


# ---------------- Retrieval helpers (used by routes/ai.py) ----------------

async def get_recent_conversation(resident_id: str, session_id: Optional[str] = None, limit: int = MAX_HISTORY_MESSAGES) -> List[dict]:
    """Return conversation history.

    If session_id is provided, return ONLY turns from this session — this is
    the critical piece that stops CAOS from conflating a current emergency
    ("I need the restroom now") with a past event ("you fell yesterday").
    Long-term facts are still available via db.memories.
    """
    if not resident_id:
        return []
    query = {"resident_id": resident_id}
    if session_id:
        query["session_id"] = session_id
    msgs = await db.conversations.find(
        query, {"_id": 0},
    ).sort("created_at", -1).to_list(limit)
    msgs.reverse()
    for m in msgs:
        _iso(m)
    return msgs


async def get_facts_bin(resident_id: str, limit: int = MAX_FACTS_IN_CONTEXT) -> List[dict]:
    """Personal Facts bin: durable identity (family, preferences, health,
    daily patterns, relationships, history). Pinned first, then importance."""
    if not resident_id:
        return []
    q_base = {"resident_id": resident_id, "bin": "facts", "archived": {"$ne": True}}
    pinned = await db.memories.find(
        {**q_base, "pinned": True}, {"_id": 0},
    ).sort("importance", -1).to_list(limit)
    remaining = max(limit - len(pinned), 0)
    rest = []
    if remaining:
        rest = await db.memories.find(
            {**q_base, "pinned": {"$ne": True}}, {"_id": 0},
        ).sort([("importance", -1), ("created_at", -1)]).to_list(remaining)
    out = pinned + rest
    for m in out:
        _iso(m)
    return out


async def get_events_bin(resident_id: str, limit: int = MAX_EVENTS_IN_CONTEXT) -> List[dict]:
    """Life Events bin: dated moments (concerns, milestones, significant
    conversations). Pinned first, then most-recent event_at/created_at."""
    if not resident_id:
        return []
    q_base = {"resident_id": resident_id, "bin": "events", "archived": {"$ne": True}}
    pinned = await db.memories.find(
        {**q_base, "pinned": True}, {"_id": 0},
    ).sort("importance", -1).to_list(limit)
    remaining = max(limit - len(pinned), 0)
    rest = []
    if remaining:
        rest = await db.memories.find(
            {**q_base, "pinned": {"$ne": True}}, {"_id": 0},
        ).sort([("event_at", -1), ("created_at", -1)]).to_list(remaining)
    out = pinned + rest
    for m in out:
        _iso(m)
    return out


async def get_top_memories(resident_id: str, limit: int = MAX_FACTS_IN_CONTEXT + MAX_EVENTS_IN_CONTEXT) -> List[dict]:
    """Backwards-compatible fetcher used by older callers. Returns facts+events
    merged. Prefer get_facts_bin / get_events_bin for new code."""
    facts = await get_facts_bin(resident_id, MAX_FACTS_IN_CONTEXT)
    events = await get_events_bin(resident_id, MAX_EVENTS_IN_CONTEXT)
    return facts + events


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


async def build_memory_context(resident_id: Optional[str], session_id: Optional[str] = None) -> dict:
    """Return {'memories_block': str, 'history': [{'role','content'}], 'memory_ids': [...]}.

    Hydration pipeline:
      - Personal Facts bin — durable identity (pinned first, then importance)
      - Life Events bin   — dated moments (pinned first, then most recent)
      - Rolling recent window of this session's conversation

    History is session-scoped when session_id is provided so the AI never
    conflates a past emergency with the current one. The two bins cover
    everything older than this session."""
    if not resident_id:
        return {"memories_block": "", "history": [], "memory_ids": []}
    facts = await get_facts_bin(resident_id)
    events = await get_events_bin(resident_id)
    history = await get_recent_conversation(resident_id, session_id=session_id)
    memory_ids = [m["memory_id"] for m in (facts + events)]

    parts = []
    if facts:
        parts.append("PERSONAL FACTS (durable identity):")
        for m in facts:
            star = "★ " if m.get("pinned") else ""
            parts.append(f"  {star}[{m.get('category','other')} · i{m.get('importance',3)}] {m['text']}")
    if events:
        parts.append("\nLIFE EVENTS (dated moments, newest first):")
        for m in events:
            star = "★ " if m.get("pinned") else ""
            when = (m.get("event_at") or m.get("created_at") or "")[:10]
            parts.append(f"  {star}[{when} · {m.get('category','other')}] {m['text']}")
    block = "\n".join(parts) if parts else "(no long-term memories yet)"
    return {
        "memories_block": block,
        "history": [{"role": h["role"], "content": h["content"]} for h in history],
        "memory_ids": memory_ids,
    }


# ---------------- Extraction (runs async after each AI reply) ----------------

async def extract_and_store_memories(resident_id: str, session_id: str, user_text: str, assistant_text: str) -> int:
    """Lightweight OpenAI call that reads the latest exchange and proposes memories.
    Runs best-effort; swallows all errors so a flaky extraction never breaks chat."""
    if not resident_id or not user_text:
        return 0
    try:
        prompt = (
            f"User said: \"{user_text}\"\nCAOS replied: \"{assistant_text}\"\n\n"
            f"Return JSON array of new durable memories."
        )
        if not OPENAI_API_KEY:
            logging.warning("Memory extraction skipped: OPENAI_API_KEY is not configured")
            return 0
        raw = await _openai_chat(EXTRACTOR_SYSTEM, prompt)
        raw = (raw or "").strip()
        # Strip code fences if the model wraps it
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
            cat = it.get("category", "other")
            m = ResidentMemory(
                resident_id=resident_id,
                text=text,
                category=cat,
                bin=default_bin_for_category(cat),
                importance=int(it.get("importance", 3)) if it.get("importance") is not None else 3,
                source="extraction",
                source_session=session_id,
                event_at=now_utc() if default_bin_for_category(cat) == "events" else None,
            )
            doc = m.model_dump()
            doc["created_at"] = doc["created_at"].isoformat()
            if doc.get("event_at"):
                doc["event_at"] = doc["event_at"].isoformat()
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
    payload = data.model_dump()
    # Auto-derive bin from category if caller didn't specify
    if not payload.get("bin"):
        payload["bin"] = default_bin_for_category(payload.get("category", "other"))
    # Stamp event_at for events-bin items so they sort chronologically
    if payload["bin"] == "events" and not payload.get("event_at"):
        payload["event_at"] = now_utc()
    m = ResidentMemory(**payload)
    doc = m.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    if doc.get("event_at"):
        doc["event_at"] = doc["event_at"].isoformat()
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
    if not OPENAI_API_KEY:
        raise _openai_unavailable()
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


# ---------------- Owner-only bulletin (the bin view) ----------------

@router.get("/bulletin/{resident_id}")
async def bulletin(resident_id: str, user=Depends(require_owner)):
    """Owner-only. Returns both bins separately so the Blueprint bulletin
    can render Personal Facts and Life Events as two columns."""
    resident = await db.residents.find_one({"resident_id": resident_id}, {"_id": 0, "name": 1, "preferred_name": 1, "room": 1})
    facts = await db.memories.find(
        {"resident_id": resident_id, "bin": "facts"}, {"_id": 0},
    ).sort([("pinned", -1), ("importance", -1), ("created_at", -1)]).to_list(1000)
    events = await db.memories.find(
        {"resident_id": resident_id, "bin": "events"}, {"_id": 0},
    ).sort([("pinned", -1), ("event_at", -1), ("created_at", -1)]).to_list(1000)
    for i in facts + events:
        _iso(i)
    conv_count = await db.conversations.count_documents({"resident_id": resident_id})
    return {
        "resident": resident,
        "facts": facts,
        "events": events,
        "conversation_turns": conv_count,
        "rolling_window": MAX_HISTORY_MESSAGES,
    }


@router.post("/backfill-bins")
async def backfill_bins(user=Depends(require_owner)):
    """Owner-only one-shot migration: assigns 'bin' to every legacy memory
    that predates the two-bin model. Idempotent — only touches rows missing bin."""
    cursor = db.memories.find({"bin": {"$exists": False}}, {"_id": 0, "memory_id": 1, "category": 1, "created_at": 1})
    updated = 0
    async for m in cursor:
        b = default_bin_for_category(m.get("category", "other"))
        patch: dict = {"bin": b}
        if b == "events":
            patch["event_at"] = m.get("created_at")
        await db.memories.update_one({"memory_id": m["memory_id"]}, {"$set": patch})
        updated += 1
    return {"ok": True, "updated": updated}
