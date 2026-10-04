"""Never tell a resident help is coming unless a receipt proves it.

The voice bridge's text model said "It's on its way!" right after filing a
request nobody had picked up (2026-10-03 spike), even when the tool result
said otherwise. Wording in a tool result is not enforcement, so the reply is
checked here before it is spoken:

- a reply that says help is coming / on its way / will be there is allowed
  only when every request it can refer to is still open AND an
  authenticated staff member's receipt shows they acknowledged, claimed or
  started it (and the request still shows that owner/acknowledgement);
- otherwise those sentences are removed and replaced with the truthful
  state: recorded and waiting for a staff member to pick it up.

The requests considered are the ones this turn's tools returned; if none,
the resident's open requests.
"""
import re
from typing import Iterable, Optional

from deps import db

ARRIVAL = re.compile(
    r"\b(on (its|their|the|her|his|my) way|(is|are|'s|'re) (coming|headed|heading)|"
    r"will be (here|there|right there|right over|with you|by|over|up)|"
    r"(will|'ll) (come|stop|swing|head|be over|be right)|"
    r"(help|someone|staff|they)('s| is| are)? (coming|underway|en route)|underway|en route|"
    r"heading (your|over|to you)|be right (there|over|with you))",
    re.I)
CLAIM_ACTIONS = ("task_assigned", "task_acknowledged", "task_in_progress", "transportation_departed")
OPEN = ("pending", "in_progress")
TRUTHFUL = "Your request is recorded and waiting for a staff member to pick it up."
NOTHING_OPEN = "I don't have anyone confirmed for that yet."


async def _claimed(task_id: str) -> bool:
    task = await db.staff_tasks.find_one({"task_id": task_id}, {"_id": 0})
    if not task or task.get("status") not in OPEN:
        return False
    if not (task.get("assigned_to") or task.get("acknowledged_by") or task.get("status") == "in_progress"):
        return False
    proof = await db.receipts.find_one({
        "related_object_type": "task", "related_object_id": task_id,
        "action_type": {"$in": list(CLAIM_ACTIONS)}, "identity_basis": "authenticated",
        "status": {"$ne": "failed"}}, {"_id": 1})
    return bool(proof)


async def candidate_tasks(tool_results: Iterable[dict], resident_id: Optional[str]) -> list:
    ids = [r["task_id"] for r in tool_results if isinstance(r, dict) and r.get("task_id")]
    if ids or not resident_id:
        return ids
    rows = await db.staff_tasks.find({"resident_id": resident_id, "status": {"$in": list(OPEN)}},
                                     {"_id": 0, "task_id": 1}).to_list(50)
    return [r["task_id"] for r in rows]


async def guard_reply(reply: str, task_ids: list) -> tuple:
    """(reply_to_speak, removed_sentences). Unchanged when no arrival claim
    is made or every referenced request is proven claimed."""
    if not reply or not ARRIVAL.search(reply):
        return reply, []
    if task_ids and all([await _claimed(t) for t in task_ids]):
        return reply, []
    sentences = re.split(r"(?<=[.!?])\s+", reply.strip())
    kept = [s for s in sentences if not ARRIVAL.search(s)]
    removed = [s for s in sentences if ARRIVAL.search(s)]
    kept.append(TRUTHFUL if task_ids else NOTHING_OPEN)
    return " ".join(kept), removed
