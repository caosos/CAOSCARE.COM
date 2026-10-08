"""Person-specific interpretation continuity (Terminal 10 / conversation
substrate). NON-NEGOTIABLE per AGENTS.md's "Mandatory preserve list" and
docs/CAOS_CARE_AGENT_ONBOARDING_CONTRACT.md's "Person-specific interpretation
continuity" section.

Canonical acceptance case: "dos savor" -> "dos sabores" -> "two flavors".

A resident's imperfect, phonetic, shorthand, or language-learning speech
should not be treated as isolated raw text once a pattern has actually been
confirmed for that person. This module is the durable store + retrieval for
that: a SMALL, resident-scoped set of heard->understood pairs, distinct from
db.memories (routes/memory.py, prose facts/events) because matching needs a
structured "what was heard" key, not free-text recall.

Deliberately its own collection (db.interpretation_patterns), not a second
generic memory architecture: it holds nothing but heard/understood/meaning
triples plus confirmation evidence. Resident-scoped only (resident_id is
always part of every query) - no cross-resident leakage.

Read/write only; no lifecycle logic belongs anywhere else, and this module
never reads/writes db.memories or db.alerts/db.staff_tasks.
"""
import re
import uuid
from difflib import SequenceMatcher
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import db, require_admin
from models import now_utc
from routes.realtime_room_lease import STALE_SECONDS

router = APIRouter(prefix="/aria/interpretation-patterns", tags=["realtime"])

MAX_PATTERNS_IN_CONTEXT = 15
MAX_EXAMPLES = 5
MAX_CORRECTION_HISTORY = 5
FUZZY_MATCH_THRESHOLD = 0.82  # phonetic-approximation tolerance, not a loose guess
GROUNDING_WINDOW_MINUTES = 15  # how recent the resident's grounding turn must be


def _normalize(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text)


class ConfirmInterpretationInput(BaseModel):
    resident_id: str
    heard_as: str = Field(max_length=200)        # the resident's actual words, verbatim
    understood_as: str = Field(max_length=200)   # the corrected / intended phrase
    meaning: Optional[str] = Field(None, max_length=300)  # plain-language meaning, e.g. English translation
    language: Optional[str] = Field(None, max_length=16)  # ISO-639-1 of `understood_as`, e.g. "es"
    category: Optional[str] = Field(None, max_length=40)  # "phonetic" | "shorthand" | "substitution" | "language_learning" | "other"
    # Internal only: the HTTP route overwrites this with "resident_confirmed"
    # (RQ-025) - a body value is never trusted.
    source: str = "resident_confirmed"


class ConfirmInterpretationRequest(ConfirmInterpretationInput):
    """Wire shape of POST /confirm: the live Aria session the confirmation
    is grounded in."""
    session_id: str = Field(max_length=120)


async def _grounding_error(data: ConfirmInterpretationRequest) -> Optional[str]:
    """None if the confirmation is grounded; otherwise why not. Requires a
    live Aria room lease for this session AND this resident, and the
    resident's own (trusted) turn in that session containing `heard_as`."""
    now = now_utc()
    lease = await db.resident_aria_leases.find_one({
        "session_id": data.session_id, "resident_id": data.resident_id,
        "status": {"$in": ["activating", "active"]},
        "last_seen_at": {"$gte": (now - timedelta(seconds=STALE_SECONDS)).isoformat()},
    })
    if not lease:
        return "no live session for this resident"
    heard = _normalize(data.heard_as)
    if not heard:
        return "empty heard_as"
    cutoff = (now - timedelta(minutes=GROUNDING_WINDOW_MINUTES)).isoformat()
    turns = await db.conversations.find({
        "resident_id": data.resident_id, "session_id": data.session_id, "role": "user",
        "trusted": {"$ne": False}, "created_at": {"$gte": cutoff},
    }, {"content": 1}).to_list(100)
    if not any(heard in _normalize(t.get("content", "")) for t in turns):
        return "the resident did not say that in this session"
    return None


async def record_pattern(data: ConfirmInterpretationInput) -> dict:
    """Upsert by (resident_id, normalized heard_as). Strengthens a repeated
    confirmation (confirmed_count, last_confirmed_at); a DIFFERENT
    understood_as is treated as a correction - applied to this one pattern
    only, with the prior value kept in `correction_history`, never silent
    and never touching any other pattern."""
    heard_norm = _normalize(data.heard_as)
    now_iso = now_utc().isoformat()
    existing = await db.interpretation_patterns.find_one(
        {"resident_id": data.resident_id, "heard_as_norm": heard_norm}, {"_id": 0},
    )

    if not existing:
        doc = {
            "pattern_id": f"ipat_{uuid.uuid4().hex[:12]}",
            "resident_id": data.resident_id,
            "heard_as": data.heard_as.strip(),
            "heard_as_norm": heard_norm,
            "understood_as": data.understood_as.strip(),
            "meaning": data.meaning,
            "language": data.language,
            "category": data.category or "other",
            "source": data.source,
            "confirmed_count": 1,
            "examples": [data.heard_as.strip()],
            "correction_history": [],
            "created_at": now_iso,
            "last_confirmed_at": now_iso,
        }
        await db.interpretation_patterns.insert_one(dict(doc))
        return doc

    update: dict = {"last_confirmed_at": now_iso}
    inc = {"confirmed_count": 1}
    push_ops: dict = {}

    if data.understood_as.strip() and data.understood_as.strip() != existing["understood_as"]:
        history = (existing.get("correction_history") or [])[-(MAX_CORRECTION_HISTORY - 1):]
        history.append({"was": existing["understood_as"], "changed_at": now_iso})
        update["correction_history"] = history
        update["understood_as"] = data.understood_as.strip()
    if data.meaning:
        update["meaning"] = data.meaning
    if data.language:
        update["language"] = data.language
    if data.category:
        update["category"] = data.category

    examples = existing.get("examples") or []
    if data.heard_as.strip() not in examples:
        push_ops["examples"] = {"$each": [data.heard_as.strip()], "$slice": -MAX_EXAMPLES}

    pipeline_update: dict = {"$set": update, "$inc": inc}
    if push_ops:
        pipeline_update["$push"] = push_ops
    await db.interpretation_patterns.update_one(
        {"resident_id": data.resident_id, "heard_as_norm": heard_norm}, pipeline_update,
    )
    return await db.interpretation_patterns.find_one(
        {"resident_id": data.resident_id, "heard_as_norm": heard_norm}, {"_id": 0},
    )


async def list_patterns(resident_id: str, limit: int = MAX_PATTERNS_IN_CONTEXT) -> list[dict]:
    """Bounded, ranked set for mint-time context - never a full dump."""
    if not resident_id:
        return []
    return await db.interpretation_patterns.find(
        {"resident_id": resident_id}, {"_id": 0},
    ).sort([("confirmed_count", -1), ("last_confirmed_at", -1)]).to_list(limit)


async def find_matching_patterns(resident_id: str, utterance: str, limit: int = 5) -> list[dict]:
    """Exact normalized substring match (always included) plus a bounded
    fuzzy pass for phonetic approximations (SequenceMatcher, stdlib - no
    invented ML matching). Used for the teaching/comparison endpoint and
    for tests; mint-time context uses list_patterns() (bounded, not matched
    against a not-yet-spoken utterance)."""
    patterns = await list_patterns(resident_id, limit=200)
    if not patterns:
        return []
    norm_utt = _normalize(utterance)
    scored = []
    for p in patterns:
        h = p["heard_as_norm"]
        if h and h in norm_utt:
            scored.append((1.0, p))
            continue
        ratio = SequenceMatcher(None, h, norm_utt).ratio()
        if ratio >= FUZZY_MATCH_THRESHOLD:
            scored.append((ratio, p))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [p for _, p in scored[:limit]]


_HEADER = (
    "## What you've learned about how {name} talks\n"
    "These are CONFIRMED person-specific patterns - things {name} has actually "
    "said before whose meaning is already established. When {name} says "
    "something close to a \"heard\" line below, understand it the way it was "
    "confirmed, not as meaningless or wrong. If something is close but not a "
    "close-enough match, or the context suggests a different meaning this "
    "time, ask rather than force the old pattern. Never claim {name} has a "
    "pattern that is not listed here. When correcting or teaching is useful, "
    "say what {name} said, what you understood, the natural/corrected form, "
    "and the meaning - do not silently replace {name}'s own words.\n"
)


def _plain(text) -> str:
    """One plain line: no newlines, markdown headings, backticks or quotes
    that could read as prompt structure."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return re.sub(r"[`#\"]", "", text)


def render_interpretation_block(patterns: list, name: str = "them") -> str:
    if not patterns:
        return ""
    lines = ["\n\n" + _HEADER.format(name=name)]
    for p in patterns:
        meaning = f" — meaning: {_plain(p['meaning'])}" if p.get("meaning") else ""
        lines.append(f"- heard \"{_plain(p['heard_as'])}\" -> understood as \"{_plain(p['understood_as'])}\"{meaning}\n")
    return "".join(lines)


@router.get("")
async def get_interpretation_patterns(resident_id: str, user=Depends(require_admin)):
    """Admin-only (RQ-025; was public). Lets staff verify what Aria has
    actually learned; the session mint reads list_patterns() in-process."""
    return {"resident_id": resident_id, "patterns": await list_patterns(resident_id)}


@router.get("/match")
async def match_interpretation_patterns(resident_id: str, utterance: str, user=Depends(require_admin)):
    return {"resident_id": resident_id, "utterance": utterance,
            "matches": await find_matching_patterns(resident_id, utterance)}


@router.post("/confirm")
async def confirm_interpretation_pattern(data: ConfirmInterpretationRequest):
    """Kiosk tool path (not logged in), so grounded in the session instead
    (RQ-025): a live Aria lease for this resident + session, and the
    resident's own turn in that session containing `heard_as`. The server
    sets `source`; the body value is ignored."""
    why = await _grounding_error(data)
    if why:
        raise HTTPException(status_code=403, detail=f"Pattern not confirmed: {why}")
    fields = data.model_dump(exclude={"session_id", "source"})
    return await record_pattern(ConfirmInterpretationInput(**fields, source="resident_confirmed"))
