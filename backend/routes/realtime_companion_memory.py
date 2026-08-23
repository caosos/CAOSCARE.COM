"""Resident profile + two-bin memory hydration for the companion prompt.

Split out of realtime_companion_prompt.py to keep that file under the
repo's 300-line cap - pure extraction, no behavior changed. Builds the
'## About this person' and '## What you know about <name>' / '## Recent
moments with <name>' blocks appended after the fixed persona text.
"""
from deps import db


async def build_resident_profile_and_memory(resident_id: str, r: dict, name: str, full_name: str) -> str:
    profile_lines = []
    if name:
        # Hard name discipline. The pilot revealed Margaret↔Maggie drift; this
        # makes the chosen name a non-negotiable rule rather than a soft hint.
        profile_lines.append(
            f"Their name is {name}. ALWAYS call them {name} — never any other "
            f"variant, nickname, diminutive, or full name. If their full name is "
            f"'{full_name}', do not use it. Just '{name}'. Never ask them what to "
            f"call them — you already know."
        )
    if r.get("low_vision"):
        profile_lines.append(
            f"{name} is visually impaired. Lean on the visually-impaired guidance above. "
            "Never reference anything they would have to see."
        )
    # Seed `preferences` and `memory` are INTAKE NOTES from family/staff — NOT
    # things the resident has told you. The model previously volunteered these
    # as conversation topics ("how about we talk about Boston?") and then lied
    # about the source ("you mentioned it before"). Reframing them as
    # third-party intake notes plus an attribution rule fixes both bugs at the
    # source — model learns these are private context, not conversation
    # starters, and learns to attribute correctly when challenged.
    intake_lines = []
    if r.get("preferences"):
        intake_lines.append(f"Things family say {name} enjoys: {r['preferences']}")
    if r.get("memory"):
        intake_lines.append(f"Background notes: {r['memory']}")
    if intake_lines:
        profile_lines.append(
            f"\n### Intake notes from {name}'s family and staff (NOT from {name})\n"
            f"The lines below were written by family or staff at admission. "
            f"{name} has NOT told you any of this directly. Treat them as "
            f"private context only — they help you understand who {name} is, "
            f"but you must NOT use them as conversation topics, and you must "
            f"NEVER claim {name} told you any of this. If {name} asks how you "
            f"know something from these notes, answer truthfully: "
            f"'your family shared that with us when you arrived' or 'the "
            f"staff has that on your file'. NEVER say 'you mentioned it'.\n"
            + "\n".join(f"  • {line}" for line in intake_lines)
        )

    # Hydrate from the two-bin memory model — this is what makes CAOS *know*
    # them rather than just *know about* them. Pulled fresh per session so
    # any edit to facts/events is reflected immediately.
    try:
        facts_cur = db.memories.find(
            {"resident_id": resident_id, "bin": "facts", "archived": {"$ne": True}},
            {"_id": 0, "text": 1, "category": 1, "importance": 1, "pinned": 1},
        ).sort([("pinned", -1), ("importance", -1), ("created_at", -1)]).limit(40)
        facts = [m async for m in facts_cur]
        events_cur = db.memories.find(
            {"resident_id": resident_id, "bin": "events", "archived": {"$ne": True}},
            {"_id": 0, "text": 1, "category": 1, "event_at": 1, "pinned": 1},
        ).sort([("pinned", -1), ("event_at", -1), ("created_at", -1)]).limit(20)
        events = [m async for m in events_cur]
    except Exception:
        facts, events = [], []

    bins = []
    bins.append(f"## What you know about {name} (durable facts)")
    if facts:
        for f in facts:
            star = "★ " if f.get("pinned") else ""
            bins.append(f"- {star}{f['text']}")
    else:
        bins.append(
            "- (No facts on file yet. You do NOT know their family, history, "
            "preferences, medical details, or where they are from. Ask gently "
            "and remember what they share. Do not invent anything.)"
        )

    bins.append(f"\n## Recent moments with {name}")
    if events:
        for e in events:
            star = "★ " if e.get("pinned") else ""
            when = (e.get("event_at") or "")
            when = (when[:10] + " · ") if isinstance(when, str) and when else ""
            bins.append(f"- {star}{when}{e['text']}")
    else:
        bins.append(
            "- (No prior moments on file. This is the start of your history "
            "together. Do NOT reference past conversations, meals, weather, "
            "trips, or anything that 'happened before' — there isn't one yet.)"
        )

    profile = ""
    if profile_lines:
        profile = "\n## About this person\n" + "\n".join(profile_lines)
    bin_block = "\n\n" + "\n".join(bins)

    return profile + bin_block
