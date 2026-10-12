"""Lifelong resident memory (Michael, 2026-10-12): a resident keeps Aria for life, so every
conversation must carry on from all the earlier ones, not only the last 3 days.

Built on the existing two-bin store (db.memories), no new collection:
  * each finished conversation is summarized ONCE into an events-bin memory
    (category "conversation", source_session = its session_id, event_at = when it ended);
    a conversation with nothing substantive is recorded archived, so it is never retried
    and never shown;
  * the summaries are folded into ONE life story per resident (facts bin, category
    "life_story", pinned), rewritten to stay under LIFE_STORY_MAX_CHARS however many
    years of conversations it covers. covers_sessions is its provenance.
Only the resident's trusted turns and Aria's replies are read. Runs in the background
when a session is minted; summarizing never blocks or fails a call.
"""
import json
import logging
from typing import Optional

from deps import db
from models import now_utc
from routes.aria_time import parse_dt
from routes.memory import _openai_chat

LIFE_STORY_MAX_CHARS = 1500
SETTLE_SECONDS = 120          # a session whose last turn is newer than this may still be going
_MAX_TRANSCRIPT_CHARS = 6000

_chat = _openai_chat          # patched in tests

_SUMMARY_SYSTEM = """You summarize one voice conversation between a senior-living resident and
Aria, their companion. Output ONLY JSON: {"summary": "...", "substantive": true|false}.
- summary: one or two plain past-tense sentences in the third person, using the resident's
  name, saying what was talked about or done ("Michael asked Aria to turn on the overhead
  light and talked about the Cubs."). Only what the transcript shows - never invent.
- Ignore garbled or foreign-language fragments that are clearly mis-transcribed noise.
- substantive=false (and summary "") when nothing was really said (only greetings, noise).
- Never include medical advice. Keep names and details exactly as said."""

_STORY_SYSTEM = """You keep the life story Aria, a senior-living companion, carries about one
resident across their whole life. You get the current life story and new conversation
summaries. Rewrite the life story in plain third-person prose, at most {max} characters:
keep people, relationships, important events, preferences, routines and ongoing threads
(things to ask about later); drop one-off trivia like single light commands. Never invent
anything that is not in the inputs: never add a relationship, role or label the inputs do not
state (someone merely named is not "a friend" or "family"; a topic asked about is not a
belief), and never guess at feelings. Do not describe testing or how the system works. Use
the resident's own words for names and details. Output only the life story text."""


async def _ended_sessions(resident_id: str, current_session_id: Optional[str]) -> list:
    """Session ids for this resident whose last turn is settled, oldest first."""
    rows = await db.conversations.aggregate([
        {"$match": {"resident_id": resident_id}},
        {"$group": {"_id": "$session_id", "last": {"$max": "$created_at"}}},
        {"$sort": {"last": 1}},
    ]).to_list(10000)
    now = now_utc().timestamp()
    out = []
    for r in rows:
        sid = r["_id"]
        if not sid or sid == current_session_id:
            continue
        try:
            if now - parse_dt(r["last"]).timestamp() < SETTLE_SECONDS:
                continue
        except Exception:
            continue
        out.append((sid, r["last"]))
    return out


def _transcript(turns: list, name: str) -> str:
    lines = []
    for t in turns:
        text = " ".join(str(t.get("content") or "").split())
        if not text:
            continue
        if t.get("role") == "user":
            if t.get("trusted") is False:
                continue
            lines.append(f"{name}: {text}")
        elif t.get("role") == "assistant":
            lines.append(f"Aria: {text}")
    return "\n".join(lines)[-_MAX_TRANSCRIPT_CHARS:]


async def _resident_name(resident_id: str) -> str:
    r = await db.residents.find_one({"resident_id": resident_id}, {"name": 1, "preferred_name": 1}) or {}
    return (r.get("preferred_name") or (r.get("name") or "").split(" ")[0] or "the resident").strip()


async def _summarize(resident_id: str, sid: str, ended_at: str, name: str) -> None:
    turns = await db.conversations.find({"resident_id": resident_id, "session_id": sid}).sort("created_at", 1).to_list(500)
    transcript = _transcript(turns, name)
    summary, substantive = "", False
    if any(line.startswith(f"{name}: ") for line in transcript.splitlines()):
        raw = (await _chat(_SUMMARY_SYSTEM, f"Resident's name: {name}\n\n{transcript}") or "").strip()
        raw = raw.strip("`").removeprefix("json").strip()
        data = json.loads(raw)
        summary = " ".join(str(data.get("summary") or "").split())[:400]
        substantive = bool(data.get("substantive")) and bool(summary)
    await db.memories.insert_one({
        "memory_id": f"mem_conv_{sid}", "resident_id": resident_id, "text": summary or "(nothing substantive said)",
        "category": "conversation", "bin": "events", "importance": 2, "source": "extraction",
        "source_session": sid, "event_at": ended_at, "pinned": False, "archived": not substantive,
        "times_referenced": 0, "created_at": now_utc().isoformat(),
    })


def _trim_to_sentence(text: str, limit: int) -> str:
    """Never cut the story mid-word: over the limit, keep whole sentences."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind(".\n"), cut.rfind("! "), cut.rfind("? "))
    return cut[:end + 1] if end > 0 else cut.rsplit(" ", 1)[0]


async def _fold_into_life_story(resident_id: str, name: str, new: list) -> None:
    story = await db.memories.find_one({"resident_id": resident_id, "category": "life_story"})
    current = (story or {}).get("text") or "(no life story yet)"
    lines = "\n".join(f"- {when[:10]}: {text}" for when, text, _ in new)
    text = (await _chat(_STORY_SYSTEM.format(max=int(LIFE_STORY_MAX_CHARS * 0.8)),
                        f"Resident's name: {name}\n\nCurrent life story:\n{current}\n\nNew conversations:\n{lines}") or "").strip()
    if not text:
        return
    text = _trim_to_sentence(text, LIFE_STORY_MAX_CHARS)
    covers = list(dict.fromkeys(((story or {}).get("covers_sessions") or []) + [sid for _, _, sid in new]))
    now = now_utc().isoformat()
    await db.memories.update_one(
        {"resident_id": resident_id, "category": "life_story"},
        {"$set": {"text": text, "covers_sessions": covers, "updated_at": now},
         "$setOnInsert": {"memory_id": f"mem_life_{resident_id}", "resident_id": resident_id, "category": "life_story",
                          "bin": "facts", "importance": 5, "pinned": True, "archived": False, "source": "extraction",
                          "times_referenced": 0, "created_at": now}},
        upsert=True)


async def summarize_pending_sessions(resident_id: Optional[str], current_session_id: Optional[str] = None,
                                     max_sessions: int = 5) -> int:
    """Summarize up to max_sessions unsummarized finished conversations (oldest first) and fold the
    substantive ones into the life story. Returns how many sessions were processed. Never raises."""
    if not resident_id:
        return 0
    try:
        done = set(await db.memories.distinct("source_session", {"resident_id": resident_id, "category": "conversation"}))
        pending = [(sid, last) for sid, last in await _ended_sessions(resident_id, current_session_id) if sid not in done]
        name = await _resident_name(resident_id)
        processed = 0
        for sid, last in pending[:max_sessions]:
            try:
                await _summarize(resident_id, sid, last, name)
                processed += 1
            except Exception:
                logging.exception("life memory: could not summarize %s; will retry next session", sid)
        # Fold every shown conversation summary the life story does not cover yet (also catches a
        # fold that failed last time).
        story = await db.memories.find_one({"resident_id": resident_id, "category": "life_story"}, {"covers_sessions": 1})
        covered = set((story or {}).get("covers_sessions") or [])
        unfolded = await db.memories.find(
            {"resident_id": resident_id, "category": "conversation", "archived": {"$ne": True},
             "source_session": {"$nin": list(covered)}}).sort("event_at", 1).to_list(200)
        if unfolded:
            await _fold_into_life_story(resident_id, name, [(m["event_at"], m["text"], m["source_session"]) for m in unfolded])
        return processed
    except Exception:
        logging.exception("life memory: summarizing sessions failed for %s", resident_id)
        return 0
