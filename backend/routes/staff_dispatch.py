"""Durable staff page / dispatch contract (Level 1 directive, 2026-09-07).

When Aria says "a nurse has been paged", CAOSCare must be able to point at a
concrete, durable record. This is that record.

  PAGE REQUESTED
    -> ACCEPTED INTO DELIVERY PATH
    -> DELIVERED / ACKNOWLEDGED   (when the mechanism supports it)
    -> FAILED                     (if delivery failed)

For the current local pilot there is no external pager provider, so the
delivery path IS the staff dashboard's own alerts feed: a dispatch is
`accepted` the moment it is durably written and linked to the open
ResidentEvent (which StaffDashboard already polls), and `delivered` when a
staff member acknowledges that event. A real pager gateway later calls the
same /accept /delivered /fail endpoints from its own callbacks - the
contract does not change.

Collection: db.staff_dispatches   Receipt: routes.receipts (action_type="staff_page")
"""
import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps import db, get_current_user
from models import now_utc, uid
from routes.activation_log import alog

log = logging.getLogger(__name__)
router = APIRouter(prefix="/staff-dispatch", tags=["staff-dispatch"])

DELIVERY_MECHANISM = "local_dashboard_feed"
# Aria wording is derived from this, never from conversational guesswork.
WORDING = {"accepted": "paged", "delivered": "paged", "requested": "sent", "failed": "failed"}


def _test_hooks() -> bool:
    return bool(os.environ.get("CAOSCARE_TEST_HOOKS"))


async def request_nurse_page(
    *, alert_id: str, activation_id: Optional[str], resident_id: Optional[str],
    resident_name: Optional[str], room: Optional[str], severity: str, reason: str,
    department: str = "Care/Nursing", source: str = "ai_triage",
    session_id: Optional[str] = None, simulate: Optional[str] = None,
) -> dict:
    """Create the durable dispatch record and run the local delivery path.
    Returns the dispatch doc plus `wording_state` (paged | sent | failed)."""
    now = now_utc().isoformat()
    dsp = {
        "dispatch_id": uid("dsp"),
        "alert_id": alert_id,
        "activation_id": activation_id,
        "resident_id": resident_id,
        "resident_name": resident_name,
        "room": room,
        "department": department,
        "severity": severity,
        "reason": reason,
        "source": source,
        "session_id": session_id,
        "requested_at": now,
        "delivery_mechanism": DELIVERY_MECHANISM,
        "status": "requested",
        "accepted_at": None,
        "delivered_at": None,
        "failed_at": None,
        "failure_reason": None,
        "acknowledged_by": None,
        "receipt_id": None,
        "events": [{"at": now, "status": "requested", "detail": f"{department} page requested ({severity})"}],
    }
    try:
        from routes.receipts import create_receipt
        rcpt = await create_receipt(
            action_type="staff_page", related_object_type="alert", related_object_id=alert_id,
            source="aria_voice", resident_id=resident_id, room=room,
        )
        dsp["receipt_id"] = rcpt["receipt_id"]
    except Exception as e:
        log.warning(f"staff_page receipt creation failed for {alert_id}: {e}")

    await db.staff_dispatches.insert_one(dict(dsp))
    await alog("dispatch", "page_requested", activation_id=activation_id, room=room,
               resident_id=resident_id, alert_id=alert_id, session_id=session_id,
               data={"dispatch_id": dsp["dispatch_id"], "department": department,
                     "severity": severity, "reason": reason,
                     "delivery_mechanism": DELIVERY_MECHANISM})

    # ---- local delivery path -------------------------------------------
    if simulate == "fail" and _test_hooks():
        await _transition(dsp["dispatch_id"], "failed",
                          failure_reason="simulated delivery failure (CAOSCARE_TEST_HOOKS)",
                          detail="local delivery simulated as failed")
    else:
        # The dashboard feed is a durable local DB write already made above,
        # and the alert is linked - so the page is genuinely accepted into
        # the delivery path. No external provider to time out against.
        await _transition(dsp["dispatch_id"], "accepted",
                          detail="accepted into local staff dashboard feed")

    fresh = await db.staff_dispatches.find_one({"dispatch_id": dsp["dispatch_id"]}, {"_id": 0})
    fresh["wording_state"] = WORDING.get(fresh["status"], "sent")
    return fresh


async def _transition(dispatch_id: str, status: str, *, failure_reason: Optional[str] = None,
                      acknowledged_by: Optional[str] = None, detail: Optional[str] = None) -> Optional[dict]:
    now = now_utc().isoformat()
    setter = {"status": status}
    if status == "accepted":
        setter["accepted_at"] = now
    elif status == "delivered":
        setter["delivered_at"] = now
        if acknowledged_by:
            setter["acknowledged_by"] = acknowledged_by
    elif status == "failed":
        setter["failed_at"] = now
        setter["failure_reason"] = failure_reason or "unspecified delivery failure"
    r = await db.staff_dispatches.find_one_and_update(
        {"dispatch_id": dispatch_id},
        {"$set": setter,
         "$push": {"events": {"at": now, "status": status,
                              "detail": detail or f"status -> {status}"}}},
        return_document=True,
    )
    if not r:
        return None
    doc = await db.staff_dispatches.find_one({"dispatch_id": dispatch_id}, {"_id": 0})
    await alog("dispatch", f"page_{status}", activation_id=doc.get("activation_id"),
               room=doc.get("room"), resident_id=doc.get("resident_id"),
               alert_id=doc.get("alert_id"), session_id=doc.get("session_id"),
               data={"dispatch_id": dispatch_id, "failure_reason": failure_reason,
                     "acknowledged_by": acknowledged_by,
                     "delivery_mechanism": doc.get("delivery_mechanism")})
    # keep the linked alert's shown status current
    try:
        await db.alerts.update_one({"alert_id": doc["alert_id"]},
                                   {"$set": {"dispatch_status": status}})
    except Exception:
        pass
    try:
        if doc.get("receipt_id"):
            from routes.receipts import update_receipt_status
            await update_receipt_status("alert", doc["alert_id"],
                                        "completed" if status in ("accepted", "delivered") else "failed",
                                        result=f"{doc.get('department')} page {status}")
    except Exception:
        pass
    return doc


# ---- endpoints (a real pager gateway calls accept/delivered/fail) --------

class _CreateIn(BaseModel):
    alert_id: str
    reason: str
    severity: str = "assist"
    department: str = "Care/Nursing"
    session_id: Optional[str] = None
    simulate_delivery: Optional[str] = None


@router.post("")
async def create_dispatch(data: _CreateIn):
    a = await db.alerts.find_one({"alert_id": data.alert_id}, {"_id": 0})
    if not a:
        raise HTTPException(404, "alert not found")
    return await request_nurse_page(
        alert_id=a["alert_id"], activation_id=a.get("activation_id"),
        resident_id=a.get("resident_id"), resident_name=a.get("resident_name"),
        room=a.get("room"), severity=data.severity, reason=data.reason,
        department=data.department, session_id=data.session_id, simulate=data.simulate_delivery,
    )


class _AckIn(BaseModel):
    acknowledged_by: Optional[str] = None
    failure_reason: Optional[str] = None


@router.post("/{dispatch_id}/accept")
async def accept_dispatch(dispatch_id: str):
    d = await _transition(dispatch_id, "accepted", detail="accepted by delivery gateway")
    if not d:
        raise HTTPException(404, "dispatch not found")
    return d


@router.post("/{dispatch_id}/delivered")
async def deliver_dispatch(dispatch_id: str, data: _AckIn):
    d = await _transition(dispatch_id, "delivered", acknowledged_by=data.acknowledged_by,
                          detail="delivery confirmed")
    if not d:
        raise HTTPException(404, "dispatch not found")
    return d


@router.post("/{dispatch_id}/fail")
async def fail_dispatch(dispatch_id: str, data: _AckIn):
    d = await _transition(dispatch_id, "failed", failure_reason=data.failure_reason,
                          detail="delivery reported failed")
    if not d:
        raise HTTPException(404, "dispatch not found")
    return d


@router.get("/{dispatch_id}")
async def get_dispatch(dispatch_id: str, user=Depends(get_current_user)):
    d = await db.staff_dispatches.find_one({"dispatch_id": dispatch_id}, {"_id": 0})
    if not d:
        raise HTTPException(404, "dispatch not found")
    return d


@router.get("")
async def list_dispatches(alert_id: Optional[str] = None, limit: int = 100,
                          user=Depends(get_current_user)):
    q = {"alert_id": alert_id} if alert_id else {}
    return await db.staff_dispatches.find(q, {"_id": 0}).sort("requested_at", -1).to_list(min(limit, 500))
