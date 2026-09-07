"""AI-triage escalation onto an open ResidentEvent (Level 1 directive,
2026-09-07).

The defect this fixes (found live, Room 214 bleeding test): Aria's
`call_for_help` did `POST /alerts`, which resident-scoped coalescing merged
into Helen's open pendant event - correctly keeping ONE event, but:
  * it incremented the human press_count and pushed a `presses[]` entry as
    if a second physical button had been pressed;
  * it dropped the requested `emergency` severity and the new reason;
  * nothing durable recorded that nursing was actually paged, yet Aria said
    "a nurse has been paged".

This endpoint replaces that path:
  1. ONE resident = ONE open event - reuse the existing open event, never
     mint a duplicate just because severity/reason changed.
  2. AI triage is NOT a human press - no press_count increment, no
     presses[] entry. It appends a separate `escalations[]` history entry.
  3. New information ENRICHES the event: reason, source=ai_triage,
     timestamp, requested department + severity. Severity escalates UP only
     (assist -> emergency), never silently down; `original_severity` is
     preserved so staff can see why it escalated.
  4. A real, durable nursing dispatch is created (routes/staff_dispatch).
  5. The response carries the dispatch's delivery state so Aria's wording
     is derived from reality, not conversation.
"""
import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from deps import db
from models import Alert, now_utc
from routes.activation_log import alog, new_activation_id
from routes.staff_dispatch import request_nurse_page

log = logging.getLogger(__name__)
router = APIRouter(prefix="/alerts", tags=["alerts"])

_SEV_RANK = {"comfort": 0, "assist": 1, "emergency": 2}


def _escalate(current: Optional[str], requested: Optional[str]) -> str:
    c, r = _SEV_RANK.get(current or "assist", 1), _SEV_RANK.get(requested or "assist", 1)
    return (current or "assist") if c >= r else (requested or "assist")


class AiEscalateInput(BaseModel):
    reason: str
    severity: str = "assist"                 # requested severity
    department: str = "Care/Nursing"
    resident_id: Optional[str] = None
    kiosk_id: Optional[str] = None
    room: Optional[str] = None
    alert_id: Optional[str] = None
    activation_id: Optional[str] = None
    session_id: Optional[str] = None
    simulate_delivery: Optional[str] = None  # test hook only (CAOSCARE_TEST_HOOKS)


@router.post("/ai-escalate")
async def ai_escalate(data: AiEscalateInput):
    now = now_utc().isoformat()

    # 1. find the resident's OPEN event (by alert_id, else resident, else room)
    q = {"status": {"$in": ["active", "acknowledged"]}}
    if data.alert_id:
        q["alert_id"] = data.alert_id
    elif data.resident_id:
        q["resident_id"] = data.resident_id
    elif data.room:
        q["room"] = data.room
    open_alert = await db.alerts.find_one(q, {"_id": 0}, sort=[("created_at", -1)])

    opened_new = False
    if not open_alert:
        # No open event - AI opens one. NOT a human press: press_count 0.
        open_alert = await _open_ai_event(data, now)
        opened_new = True
        effective = data.severity
        from_sev = None
    else:
        from_sev = open_alert.get("severity", "assist")
        effective = _escalate(from_sev, data.severity)
        esc_entry = {
            "at": now, "source": "ai_triage", "reason": data.reason,
            "requested_department": data.department, "requested_severity": data.severity,
            "effective_severity": effective, "session_id": data.session_id,
        }
        setter = {
            "severity": effective,
            "requested_staff": True,
            "latest_escalation_reason": data.reason,
            "escalated_at": now,
            "escalation_source": "ai_triage",
            "resident_stated_reason": open_alert.get("resident_stated_reason") or data.reason,
        }
        if not open_alert.get("original_severity"):
            setter["original_severity"] = from_sev
        if effective == "emergency" and (open_alert.get("escalation_level") or 0) < 1:
            setter["escalation_level"] = 1
        await db.alerts.update_one(
            {"alert_id": open_alert["alert_id"]},
            {"$set": setter,
             "$push": {
                 "escalations": esc_entry,
                 "event_log": {"at": now, "field": "ai_escalation", "reason": data.reason,
                               "from_severity": from_sev, "to_severity": effective,
                               "session_id": data.session_id,
                               "activation_id": open_alert.get("activation_id")},
             }},
            # NOTE: deliberately no $inc press_count, no $push presses.
        )
        open_alert = await db.alerts.find_one({"alert_id": open_alert["alert_id"]}, {"_id": 0})

    await alog("resident_event", "severity_escalated",
               activation_id=open_alert.get("activation_id"), room=open_alert.get("room"),
               resident_id=open_alert.get("resident_id"), alert_id=open_alert["alert_id"],
               session_id=data.session_id,
               data={"from_severity": from_sev, "to_severity": effective,
                     "reason": data.reason, "source": "ai_triage",
                     "department": data.department, "opened_new_event": opened_new,
                     "human_press_count": open_alert.get("press_count", 0)})

    # 4. real, durable nursing dispatch
    disp = await request_nurse_page(
        alert_id=open_alert["alert_id"], activation_id=open_alert.get("activation_id"),
        resident_id=open_alert.get("resident_id"), resident_name=open_alert.get("resident_name"),
        room=open_alert.get("room"), severity=effective, reason=data.reason,
        department=data.department, source="ai_triage", session_id=data.session_id,
        simulate=data.simulate_delivery,
    )
    await db.alerts.update_one(
        {"alert_id": open_alert["alert_id"]},
        {"$set": {"dispatch_id": disp["dispatch_id"], "dispatch_status": disp["status"]}},
    )

    return {
        "alert_id": open_alert["alert_id"],
        "activation_id": open_alert.get("activation_id"),
        "effective_severity": effective,
        "opened_new_event": opened_new,
        "human_press_count": open_alert.get("press_count", 0),
        "escalation_count": len(open_alert.get("escalations", [])) or (1 if opened_new else 0),
        "dispatch": {k: disp.get(k) for k in (
            "dispatch_id", "status", "delivery_mechanism", "department", "severity",
            "requested_at", "accepted_at", "delivered_at", "failure_reason", "receipt_id")},
        "wording_state": disp["wording_state"],
    }


async def _open_ai_event(data: AiEscalateInput, now: str) -> dict:
    """No open event existed - open one, AI-initiated, zero human presses."""
    resident_name = None
    room = data.room
    if data.resident_id:
        r = await db.residents.find_one({"resident_id": data.resident_id}, {"_id": 0})
        if r:
            resident_name = r.get("name")
            room = room or r.get("room")
    alert = Alert(
        kiosk_id=data.kiosk_id, resident_id=data.resident_id, resident_name=resident_name,
        room=room, severity=data.severity, message="AI triage escalation",
        triggered_by="ai_triage", auto_voice=False, press_count=0,
    )
    doc = alert.model_dump()
    doc["created_at"] = now
    doc["acknowledged_at"] = None
    doc["resolved_at"] = None
    doc["presses"] = []
    doc["press_count"] = 0
    doc["activation_id"] = data.activation_id or new_activation_id()
    doc["original_severity"] = data.severity
    doc["latest_escalation_reason"] = data.reason
    doc["resident_stated_reason"] = data.reason
    doc["requested_staff"] = True
    doc["escalation_source"] = "ai_triage"
    doc["escalated_at"] = now
    doc["escalations"] = [{
        "at": now, "source": "ai_triage", "reason": data.reason,
        "requested_department": data.department, "requested_severity": data.severity,
        "effective_severity": data.severity, "session_id": data.session_id,
    }]
    doc["event_log"] = [{"at": now, "field": "ai_escalation", "reason": data.reason,
                         "from_severity": None, "to_severity": data.severity,
                         "session_id": data.session_id, "activation_id": doc["activation_id"]}]
    if data.resident_id:
        doc["open_event_key"] = f"resident:{data.resident_id}"
    elif room:
        doc["open_event_key"] = f"room:{room}"
    try:
        from routes.receipts import create_receipt
        rcpt = await create_receipt(
            action_type="resident_assistance_event", related_object_type="alert",
            related_object_id=doc["alert_id"], source="aria_voice",
            resident_id=data.resident_id, room=room)
        doc["receipt_id"] = rcpt["receipt_id"]
    except Exception as e:
        log.warning(f"receipt creation failed for AI-opened alert {doc['alert_id']}: {e}")
    await db.alerts.insert_one(dict(doc))
    doc.pop("_id", None)
    await alog("resident_event", "event_opened", activation_id=doc["activation_id"],
               room=room, resident_id=data.resident_id, alert_id=doc["alert_id"],
               data={"cause": "ai_triage_no_open_event", "press_count_before": 0,
                     "press_count_after": 0, "semantic_class": "ai_triage",
                     "source": "ai_triage", "severity": data.severity})
    return doc
