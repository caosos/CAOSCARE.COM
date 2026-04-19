"""Daily haiku generator — Claude writes one short, warm haiku per resident
for the family portal. Uses each resident's preferences + memory for personal touch.

Idempotent per resident per day (YYYY-MM-DD). Admin triggers via
`POST /api/haiku/generate-today` or calls one-off `POST /api/haiku/{resident_id}`.
"""
import os
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from deps import db, get_current_user
from models import now_utc, uid

from emergentintegrations.llm.chat import LlmChat, UserMessage

router = APIRouter(prefix="/haiku", tags=["haiku"])

EMERGENT_KEY = os.environ["EMERGENT_LLM_KEY"]

HAIKU_SYSTEM = """You are CAOS, writing a tiny bedtime haiku to send to a senior's family.
RULES
- 3 lines, roughly 5/7/5 syllables (approximate is fine).
- Warm, peaceful, present-tense. Never medical, never dramatic.
- Reference something the resident loves (from their preferences) if natural.
- No names, no em-dashes, no hashtags. Lowercase first letter, no ending period.
- Output ONLY the three lines separated by newlines."""


async def _generate_one(resident: dict) -> dict:
    pref_name = resident.get("preferred_name") or resident.get("name", "")
    prefs = resident.get("preferences") or ""
    memory = resident.get("memory") or ""
    prompt = (
        f"Write tonight's bedtime haiku for {pref_name}. "
        f"What they love: {prefs or 'quiet evenings, old songs'}. "
        f"Background: {memory or 'seeking peace'}."
    )
    llm = LlmChat(
        api_key=EMERGENT_KEY,
        session_id=f"haiku-{resident['resident_id']}-{now_utc().date().isoformat()}",
        system_message=HAIKU_SYSTEM,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")
    try:
        reply = await llm.send_message(UserMessage(text=prompt))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Claude haiku failed: {e}")

    text = (reply or "").strip().strip('"').strip()
    doc = {
        "haiku_id": uid("haiku"),
        "resident_id": resident["resident_id"],
        "resident_name": resident.get("name"),
        "text": text,
        "day": now_utc().date().isoformat(),
        "created_at": now_utc().isoformat(),
    }
    await db.haikus.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.post("/generate-today")
async def generate_today(user=Depends(get_current_user)):
    """Idempotent — skips residents who already have a haiku dated today."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    today = now_utc().date().isoformat()
    created = 0
    skipped = 0
    failed = 0
    async for r in db.residents.find({}, {"_id": 0}):
        existing = await db.haikus.find_one(
            {"resident_id": r["resident_id"], "day": today}, {"_id": 0}
        )
        if existing:
            skipped += 1
            continue
        try:
            await _generate_one(r)
            created += 1
        except Exception:
            failed += 1
    return {"ok": True, "created": created, "skipped": skipped, "failed": failed, "day": today}


@router.post("/{resident_id}")
async def generate_for_resident(resident_id: str, user=Depends(get_current_user)):
    r = await db.residents.find_one({"resident_id": resident_id}, {"_id": 0})
    if not r:
        raise HTTPException(status_code=404, detail="Resident not found")
    return await _generate_one(r)


@router.get("/latest")
async def list_latest(user=Depends(get_current_user)):
    # one haiku per resident (the latest)
    residents = await db.residents.find({}, {"_id": 0, "resident_id": 1, "name": 1}).to_list(200)
    out = []
    for r in residents:
        h = await db.haikus.find_one(
            {"resident_id": r["resident_id"]}, {"_id": 0},
            sort=[("created_at", -1)],
        )
        if h:
            out.append(h)
    return out
