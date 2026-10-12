"""Unclaimed Nursing request escalation (careops-nursing-unclaimed-escalation-001).

Part of the one escalation tick (escalation_tick.run_tick); no separate timer.
A Nursing request that is still pending and unassigned `nursing_unclaimed_seconds`
(EscalationRule) after it was raised is flagged ONCE for a supervisor:

  * one atomic claim (`unclaimed_claimed_at`), so repeated or concurrent ticks
    flag it once;
  * the flag and its history entry are written through task_lifecycle.transition
    with the system actor, so the receipt (`task_unclaimed_escalated`) chains
    to the request's origin; the request stays open and nothing else changes;
  * once someone is assigned (or it is closed) it is no longer listed as an
    exception, and an assigned or closed request is never flagged;
  * older-than-current records (operations_currency "review") are skipped,
    as stale alerts are;
  * nothing is sent outside CAOSCare (no SMS/email from this step).
"""
from datetime import datetime, timedelta

from deps import db
from routes.actor_context import actor_system
from routes.operations_currency import active_run, classify
from routes.ops_overview_util import parse_dt
from routes.task_history import task_event
from routes.task_lifecycle import LifecycleError, transition

DEPARTMENTS = ("nursing",)
ACTOR = actor_system("escalation")


async def escalate_unclaimed(now: datetime, rule: dict) -> dict:
    out = {"unclaimed_flagged": 0, "unclaimed_examined": 0}
    if not rule.get("enabled", True):
        return out
    threshold = int(rule.get("nursing_unclaimed_seconds", 600))
    cutoff = (now - timedelta(seconds=threshold)).isoformat()
    tasks = await db.staff_tasks.find(
        {"visibility_role": {"$in": list(DEPARTMENTS)}, "status": "pending",
         "assigned_to": None, "unclaimed_claimed_at": None, "created_at": {"$lte": cutoff},
         # planned for a later day (e.g. a recurring occurrence made ahead): not due yet
         "$or": [{"requested_for_date": None}, {"requested_for_date": {"$lte": now.date().isoformat()}}]},
        {"_id": 0}).to_list(500)
    out["unclaimed_examined"] = len(tasks)
    run = await active_run()
    rid = run["run_id"] if run else None
    for t in tasks:
        if classify(t, "task", rid, now)["bucket"] not in ("current", "sim_current"):
            continue
        claimed = await db.staff_tasks.update_one(
            {"task_id": t["task_id"], "status": "pending", "assigned_to": None, "unclaimed_claimed_at": None},
            {"$set": {"unclaimed_claimed_at": now.isoformat()}})
        if claimed.modified_count == 0:
            continue
        age_min = int((now - parse_dt(t["created_at"])).total_seconds() // 60)
        text = f"No one has claimed it after {age_min} min (rule: {threshold // 60} min); flagged for a supervisor"

        def build(task, rcpt, text=text):
            return ({"unclaimed_escalated_at": now.isoformat(), "unclaimed_minutes": age_min},
                    [task_event("unclaimed_escalated", by=ACTOR.actor_id, by_name="Escalation tick",
                                receipt_id=rcpt, text=text)])
        try:
            await transition(t["task_id"], ACTOR, None, action="unclaimed_escalate", build=build,
                             authority=f"escalation_rule:{rule.get('facility_id') or 'default'}:nursing_unclaimed",
                             action_type="task_unclaimed_escalated", status="created", result=text)
            out["unclaimed_flagged"] += 1
        except LifecycleError:
            pass   # legacy request with no origin: the refusal is recorded by the lifecycle; not retried
    return out
