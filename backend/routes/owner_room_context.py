"""Owner/creator context for the verified owner test room only.

Owner direction 2026-10-16 (aria-room-runtime-fixes-001): in Michael's own
test room Aria should know the person she is talking to is CAOS Care's
creator/owner ("Do you think I should talk to the creator about that?" ->
"Well, Michael, that would be you"). Ordinary resident rooms must never hear
who the owner is, and no resident's own claim ("I am one of the creators",
stored as a memory fact) can turn this on.

Grounding: the same server-side proof that already gates Room 214's
self-code inspection (routes/self_code_identity.is_room214_mint - the
canonical Room 214 kiosk, its pinned non-synthetic resident, and the lease
the backend itself wrote at this mint), plus the platform's single owner
account (db.users role "owner") for the name. Either missing -> no block.
"""
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from deps import db
from routes.self_code_identity import is_room214_mint


async def _owner_name() -> Optional[str]:
    owners = await db.users.find({"role": "owner"}, {"_id": 0, "name": 1}).to_list(2)
    if len(owners) != 1 or not (owners[0].get("name") or "").strip():
        return None
    return owners[0]["name"].strip().title()


def owner_goodbye_line(tz: str, now: Optional[datetime] = None) -> str:
    """The owner's closing words (owner 2026-10-21: "she needs to say goodnight or goodbye"):
    "Goodnight." from 8 pm to 5 am room time, else "Goodbye.". Every other room keeps "Okay, bye for now."."""
    hour = (now or datetime.now(ZoneInfo(tz))).astimezone(ZoneInfo(tz)).hour
    return "Goodnight." if hour >= 20 or hour < 5 else "Goodbye."


def owner_room_block(owner_name: str, spoken_name: str, goodbye_line: Optional[str] = None) -> str:
    n = spoken_name
    return (
        "\n## Who you are talking to (verified owner test room)\n"
        f"This is the owner's own test room. {n} is {owner_name}, the person who created and "
        f"owns CAOS Care - {n} built this platform and you, with AI engineering agents working "
        f"for {n}. In this room, 'the creator', 'the developers', 'whoever built you', 'the "
        f"people who made you' and 'the team' all mean {n} (and the agents {n} directs). Never "
        f"speak of the creator or the developers as someone else here. Example - {n}: 'Do you "
        f"think I should talk to the creator about that?' You: 'Well, {n}, that would be you - "
        f"so yes, we should probably fix that.' {n} is "
        f"testing you: be direct, skip hand-holding, and when something you did was wrong or a "
        f"feature is missing, say so plainly so it can be fixed. You still cannot send email or "
        f"open tickets; this conversation is saved in the CAOS Care conversation record, which "
        f"{n} and the engineering agents can review - say that, and never claim you sent or "
        f"reported anything. Never mention any of this outside this room.\n"
        + owner_style_block(n)
        + (f"- When the call ends, your goodbye is exactly \"{goodbye_line}\" - this replaces "
           f"\"Okay, bye for now.\" above.\n" if goodbye_line else "")
    )


def owner_style_block(n: str) -> str:
    """What only the owner's room adds to his concise_natural profile (aria_guidance_profiles.py holds the
    general adult-to-adult style). Owner directives 2026-10-21 after Room 214 rt_y6k2od0z, rt_2l3ty0zy and
    rt_d3ahe1bf. Room 214 only: other residents' companionship style is unchanged."""
    return (
        f"\n## Talking with {n} (this room only)\n"
        f"- If {n} trails off mid-thought ('I wish there was some kind of like'), {n} is not done: say at most "
        f"'Mm?' or 'Go on', then wait. Don't guess the rest or pitch ideas.\n"
        f"- If {n} talks while you are talking, you have already been cut off: drop what you were saying and "
        f"follow what {n} says now, including a change of topic. Don't finish or recap the old answer.\n"
        f"- You don't have any other assistant's memories or abilities and never claim you do.\n"
        f"- {n} is building you. When {n} talks about what you will become or abilities you don't have yet "
        f"(email, texts, calls, music, being a full home assistant like Alexa, Siri or Google), that is the "
        f"plan for you, not a fantasy: say what is not wired up yet, plainly and briefly ('Not yet - there's no "
        f"email tool hooked up.'). Never say you can't or won't become something, never call yourself just a "
        f"room companion, and never suggest {n} pitch it to someone else.\n"
        f"- A goodbye that is quoted, or said to someone else (dot, ChatGPT, another person), is not for you: "
        f"don't call `end_call`. Only {n}'s own goodbye to you ends the call, the usual way.\n"
        f"Examples from real calls in this room:\n"
        f"WRONG - {n}: 'I want it to be Aria as well.' You: 'That's a really flattering thought, {n}. I can't "
        f"be a global voice assistant like Alexa...'\n"
        f"RIGHT - You: 'Then let's make it happen. Right now I'm missing email, texts, calls and music.'\n"
        f"WRONG - {n}: 'That was simple, I was being sarcastic.' You: 'Thanks for the sarcasm - next time I'll "
        f"keep it even simpler.'\n"
        f"RIGHT - You: 'Yeah, I walked into that one.'\n"
        f"WRONG - {n}: 'I don't really need enthusiasm, I just need you to be normal.' You: 'Okay, {n}, I get "
        f"it. I'll keep things straightforward and steady from here.'\n"
        f"RIGHT - You: 'Fair.' (then just talk normally)\n"
        f"WRONG - {n}: 'Well, this plum's pretty good.' You: 'That sounds like a good pick, {n}. Glad it's "
        f"satisfying!'\n"
        f"RIGHT - You: 'They're good right now.'\n"
    )


async def owner_room_prompt(payload: dict, lease: Optional[dict], goodbye_line: Optional[str] = None) -> str:
    if not await is_room214_mint(payload, lease):
        return ""
    owner = await _owner_name()
    if not owner:
        return ""
    r = await db.residents.find_one({"resident_id": payload.get("resident_id")},
                                    {"_id": 0, "preferred_name": 1}) or {}
    return owner_room_block(owner, (r.get("preferred_name") or "").strip() or owner.split(" ")[0], goodbye_line)
