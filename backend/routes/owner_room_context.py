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
from typing import Optional

from deps import db
from routes.self_code_identity import is_room214_mint


async def _owner_name() -> Optional[str]:
    owners = await db.users.find({"role": "owner"}, {"_id": 0, "name": 1}).to_list(2)
    if len(owners) != 1 or not (owners[0].get("name") or "").strip():
        return None
    return owners[0]["name"].strip().title()


def owner_room_block(owner_name: str, spoken_name: str) -> str:
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
    )


async def owner_room_prompt(payload: dict, lease: Optional[dict]) -> str:
    if not await is_room214_mint(payload, lease):
        return ""
    owner = await _owner_name()
    if not owner:
        return ""
    r = await db.residents.find_one({"resident_id": payload.get("resident_id")},
                                    {"_id": 0, "preferred_name": 1}) or {}
    return owner_room_block(owner, (r.get("preferred_name") or "").strip() or owner.split(" ")[0])
