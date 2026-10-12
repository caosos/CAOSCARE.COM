"""Alert deliveries that did not go out (careops-frontdesk-failed-deliveries-001).

Read model for the front desk "Needs attention" view: notifications about an
alert - escalation SMS / live-line calls (notify_alert_phone) and family alert
updates (notify_family_for_alert) - whose status says they were not sent or
failed, opened within STALE_ALERT_HOURS. Request-linked deliveries are already
in /ops/routing-exceptions and are not repeated here.

Resident-safe by construction: no subject or message text, recipients masked
and labelled (family relationship, supervisor / on-call phone), provider
internals reduced to a plain status. The full delivery log stays admin-only
(GET /notifications). Nothing here sends or retries; each row links to its
alert and its delivery receipt.
"""
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

from deps import db, require_front_desk_or_admin
from routes.ops_overview_util import STALE_ALERT_HOURS

router = APIRouter(prefix="/ops", tags=["ops"])

_STATE = {"logged": "not_sent", "failed": "failed", "bounced": "failed", "complained": "failed"}


def _label(n: dict) -> str:
    s = n.get("status")
    if s == "logged":
        return ("Not sent - no message provider is set up" if "not configured" in (n.get("provider_response") or "")
                else "Not sent")
    return {"failed": "Failed - the provider did not accept it", "bounced": "Bounced - the address did not accept it",
            "complained": "Marked as unwanted by the recipient"}.get(s, s)


def _mask(channel: str, to: str) -> str:
    if channel in ("sms", "call", "voice"):
        digits = re.sub(r"\D", "", to or "")
        return f"phone ending {digits[-4:]}" if digits else "phone"
    local, _, domain = (to or "").partition("@")
    return f"{local[:1]}…@{domain}" if domain else "email"


async def _recipient(n: dict, family: dict, receipts: dict) -> str:
    fc = family.get((n.get("resident_id"), (n.get("to") or "").lower()))
    if fc:
        return f"Family: {fc.get('name')}" + (f" ({fc['relationship']})" if fc.get("relationship") else "")
    authority = (receipts.get(n.get("receipt_id")) or {}).get("authority") or ""
    who = "On-call" if authority.endswith("level_3") else "Supervisor" if authority.endswith("level_2") else None
    masked = _mask(n.get("channel"), n.get("to"))
    return f"{who} {masked}" if who else masked.capitalize()


@router.get("/delivery-exceptions")
async def delivery_exceptions(user=Depends(require_front_desk_or_admin)):
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=STALE_ALERT_HOURS)).isoformat()
    notes = await db.notifications.find(
        {"status": {"$in": list(_STATE)}, "alert_id": {"$nin": [None, ""]}, "task_id": None,
         "related_object_type": {"$in": [None, "alert"]}, "created_at": {"$gte": cutoff}},
        {"_id": 0, "body": 0, "subject": 0}).sort("created_at", -1).to_list(200)
    rids = list({n.get("resident_id") for n in notes if n.get("resident_id")})
    aids = list({n["alert_id"] for n in notes})
    family = {(c["resident_id"], (c.get(k) or "").lower()): c
              async for c in db.family_contacts.find({"resident_id": {"$in": rids}}, {"_id": 0})
              for k in ("email", "phone") if c.get(k)}
    receipts = {r["receipt_id"]: r async for r in db.receipts.find(
        {"receipt_id": {"$in": [n["receipt_id"] for n in notes if n.get("receipt_id")]}}, {"_id": 0, "receipt_id": 1, "authority": 1})}
    alerts = {a["alert_id"]: a async for a in db.alerts.find(
        {"alert_id": {"$in": aids}}, {"_id": 0, "alert_id": 1, "resident_name": 1, "room": 1, "severity": 1, "status": 1})}
    items, counts = [], {"not_sent": 0, "failed": 0}
    for n in notes:
        a = alerts.get(n["alert_id"], {})
        state = _STATE[n["status"]]
        counts[state] += 1
        items.append({
            "notification_id": n["notification_id"], "alert_id": n["alert_id"], "channel": n.get("channel"),
            "recipient": await _recipient(n, family, receipts), "state": state, "label": _label(n),
            "resident_name": a.get("resident_name"), "room": a.get("room"),
            "alert_severity": a.get("severity"), "alert_status": a.get("status"),
            "receipt_id": n.get("receipt_id"), "created_at": n.get("created_at"),
        })
    return {"items": items, "counts": counts, "total": len(items)}
