"""Was anyone actually told? (careops-routing-delivery-audit-001)

A routed request writes department notification records (notifications.py:
notify_department, linked by related_object_id = task_id). Before this, the
request card, the department board and the operations overview showed only
"Pending / Unassigned" - never whether the department was really reached.
This module reads those records and returns ONE truthful state per request.
Read-only; nothing is stored.

States, best evidence first:
  delivered  - the provider reported delivery
  sent       - handed to the provider (sent / queued / delayed), not yet confirmed
  simulated  - demo/simulated work: recorded, never sent (by design)
  not_sent   - recorded only: no email/SMS provider is configured
  failed     - every attempt failed or bounced
  none       - no notification record exists for this request
"""
from typing import Iterable

from deps import db

RANK = {"delivered": 5, "sent": 4, "queued": 4, "delayed": 4, "simulated": 3, "logged": 2,
        "failed": 1, "bounced": 1, "complained": 1}
STATE = {5: "delivered", 4: "sent", 3: "simulated", 2: "not_sent", 1: "failed"}
LABEL = {
    "delivered": "Department notified (delivery confirmed)",
    "sent": "Department notification sent, delivery not yet confirmed",
    "simulated": "Simulated request: notification recorded, not sent",
    "not_sent": "Department NOT notified: recorded only, no email/SMS provider is set up",
    "failed": "Department NOT notified: every notification attempt failed",
    "none": "No department notification on record",
}
REACHED = ("delivered", "sent")


def summarize(records: list) -> dict:
    best = max((RANK.get(r.get("status"), 0) for r in records), default=0)
    state = STATE.get(best, "none")
    return {"state": state, "label": LABEL[state], "reached": state in REACHED, "attempts": len(records),
            "to": sorted({r.get("to") for r in records if r.get("to")})[:5],
            "routes": sorted({r.get("route") for r in records if r.get("route")})}


async def delivery_for(task_ids: Iterable[str]) -> dict:
    ids = [t for t in task_ids if t]
    by: dict = {t: [] for t in ids}
    if ids:
        async for n in db.notifications.find({"related_object_type": "task", "related_object_id": {"$in": ids}},
                                             {"_id": 0, "related_object_id": 1, "status": 1, "to": 1, "route": 1}):
            by.setdefault(n["related_object_id"], []).append(n)
    return {t: summarize(recs) for t, recs in by.items()}
