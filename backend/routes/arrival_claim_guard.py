"""Never tell a resident help is on the way unless movement is proven.

The voice bridge's text model said "It's on its way!" right after filing a
request nobody had picked up (2026-10-03 spike), even when the tool result
said otherwise. Wording in a tool result is not enforcement, so the reply is
checked here before it is spoken.

Michael, 2026-10-04: acknowledgement, a claim, an assignment or the start of
work does NOT mean anyone is moving toward the resident. A reply that says
help is coming / on its way / en route / will be there is allowed only when
every request it can refer to has movement evidence in BOTH the canonical
workflow state and a receipt. Today that exists only for transportation: an
open ride on a run that departed, with an authenticated
`transportation_departed` receipt. CAOSCare has no "on the way" state for
nursing or maintenance requests, so such claims are always removed for them.

Removed sentences are replaced with the strongest true statement for the
least advanced request (all of them are at least this far):
  created       "I've requested help."
  acknowledged  "Your request has been acknowledged."
  assigned      "A staff member has accepted your request."
  started       "Work on your request has started."

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
OPEN = ("pending", "in_progress")
STAGES = ("created", "acknowledged", "assigned", "started")
STAGE_TEXT = {
    "created": "I've requested help.",
    "acknowledged": "Your request has been acknowledged.",
    "assigned": "A staff member has accepted your request.",
    "started": "Work on your request has started.",
}
NOTHING_OPEN = "I don't have anyone confirmed for that yet."


def stage(task: dict) -> str:
    """How far an open request has actually got (canonical task fields)."""
    if task.get("status") == "in_progress":
        return "started"
    if task.get("assigned_to"):
        return "assigned"
    if task.get("acknowledged_by"):
        return "acknowledged"
    return "created"


async def en_route(task: dict) -> bool:
    """Movement toward the resident, proven by workflow state AND a receipt.
    Only a departed transportation run qualifies today."""
    if task.get("status") != "in_progress" or not task.get("transport_run_id"):
        return False
    run = await db.transport_runs.find_one({"run_id": task["transport_run_id"]}, {"_id": 0})
    if not run or run.get("status") != "in_progress" or not run.get("departed_at"):
        return False
    proof = await db.receipts.find_one({
        "related_object_type": "task", "related_object_id": task["task_id"],
        "action_type": "transportation_departed", "identity_basis": "authenticated",
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
    is made or every referenced request is proven to be en route."""
    if not reply or not ARRIVAL.search(reply):
        return reply, []
    tasks = [t for t in [await db.staff_tasks.find_one({"task_id": i}, {"_id": 0}) for i in task_ids] if t]
    open_tasks = [t for t in tasks if t.get("status") in OPEN]
    if task_ids and len(open_tasks) == len(task_ids) and all([await en_route(t) for t in open_tasks]):
        return reply, []
    sentences = re.split(r"(?<=[.!?])\s+", reply.strip())
    kept = [s for s in sentences if not ARRIVAL.search(s)]
    removed = [s for s in sentences if ARRIVAL.search(s)]
    if open_tasks:
        least = min((stage(t) for t in open_tasks), key=STAGES.index)
        kept.append(STAGE_TEXT[least])
    else:
        kept.append(NOTHING_OPEN)
    return " ".join(kept), removed
