"""NotificationService - logs every notification; real providers activate when keys are set."""
import os
from typing import Optional, List
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends

from models import Notification, NotificationTest, FamilyContact, FamilyContactCreate, now_utc
from deps import db, get_current_user

router = APIRouter(tags=["notifications"])


# Feature flags - flip these by adding keys to backend/.env
TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM = os.environ.get("TWILIO_FROM_NUMBER", "")
RESEND_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM = os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev")


async def _log_notification(doc: dict) -> dict:
    doc.setdefault("created_at", now_utc().isoformat())
    await db.notifications.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def send_sms(to: str, body: str, *, alert_id: str | None = None, resident_id: str | None = None) -> dict:
    """Send SMS via Twilio if configured; otherwise log only."""
    n = Notification(
        channel="sms",
        to=to,
        body=body[:1500],
        alert_id=alert_id,
        resident_id=resident_id,
    )
    doc = n.model_dump()
    if not (TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM):
        doc["status"] = "logged"
        doc["provider_response"] = "Twilio not configured — logged only (ready to activate when keys are provided)"
        doc["created_at"] = doc["created_at"].isoformat()
        return await _log_notification(doc)
    try:
        import httpx
        resp = await httpx.AsyncClient(timeout=10).post(
            f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json",
            auth=(TWILIO_SID, TWILIO_TOKEN),
            data={"From": TWILIO_FROM, "To": to, "Body": body[:1500]},
        )
        doc["status"] = "sent" if resp.status_code < 300 else "failed"
        doc["provider_response"] = resp.text[:500]
    except Exception as e:
        doc["status"] = "failed"
        doc["provider_response"] = f"exception: {e}"
    doc["created_at"] = doc["created_at"].isoformat()
    return await _log_notification(doc)


async def send_email(to: str, subject: str, body: str, *, alert_id: str | None = None, resident_id: str | None = None) -> dict:
    n = Notification(
        channel="email",
        to=to,
        subject=subject,
        body=body[:4000],
        alert_id=alert_id,
        resident_id=resident_id,
    )
    doc = n.model_dump()
    if not RESEND_KEY:
        doc["status"] = "logged"
        doc["provider_response"] = "Resend not configured — logged only (ready to activate when keys are provided)"
        doc["created_at"] = doc["created_at"].isoformat()
        return await _log_notification(doc)
    try:
        import httpx
        resp = await httpx.AsyncClient(timeout=10).post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_KEY}"},
            json={"from": RESEND_FROM, "to": [to], "subject": subject, "text": body},
        )
        doc["status"] = "sent" if resp.status_code < 300 else "failed"
        doc["provider_response"] = resp.text[:500]
    except Exception as e:
        doc["status"] = "failed"
        doc["provider_response"] = f"exception: {e}"
    doc["created_at"] = doc["created_at"].isoformat()
    return await _log_notification(doc)


async def notify_department(visibility_role: str, subject: str, body: str) -> None:
    """Email a department. Three-tier fallback, in order:
    1. The department's own Department.contact_email, if set - for a
       department that's a shared inbox (e.g. kitchen@facility) rather
       than individual staff logins.
    2. Every staff User whose .department matches this slug - the
       original mechanism, still the default for departments with real
       staff accounts.
    3. admin/owner - so a request is never silently un-notified, even for
       a brand-new department nobody's been assigned to yet.
    send_email() already degrades gracefully to a logged-only record when
    no provider key is configured - this never blocks the caller. Shared
    by resident_requests.py, tasks.py, and transportation.py - one
    notification path, not one per lane."""
    dept = await db.departments.find_one({"slug": visibility_role}, {"_id": 0, "contact_email": 1})
    if dept and dept.get("contact_email"):
        await send_email(dept["contact_email"], subject, body)
        return
    recipients = await db.users.find(
        {"department": visibility_role}, {"_id": 0, "email": 1}
    ).to_list(50)
    if not recipients:
        recipients = await db.users.find(
            {"role": {"$in": ["admin", "owner"]}}, {"_id": 0, "email": 1}
        ).to_list(50)
    for u in recipients:
        if u.get("email"):
            await send_email(u["email"], subject, body)


async def notify_family_for_alert(alert: dict):
    """Fan out to family contacts based on their notify_on prefs."""
    rid = alert.get("resident_id")
    if not rid:
        return
    severity = alert.get("severity", "assist")
    resident_name = alert.get("resident_name", "Your loved one")
    room = alert.get("room", "")
    zone = alert.get("zone", "")
    msg_sub = f"CAOS Care update: {resident_name}"
    is_wander = alert.get("triggered_by") == "geofence"
    key = "wander" if is_wander else severity
    body = (
        f"{resident_name} (Room {room}) — {severity} alert. "
        f"Location: {zone or 'unknown'}. "
        f"Staff have been paged. You'll receive a follow-up when this is resolved."
    )
    contacts = await db.family_contacts.find(
        {"resident_id": rid, "notify_on": key},
        {"_id": 0},
    ).to_list(50)
    for c in contacts:
        if c.get("phone"):
            await send_sms(c["phone"], body, alert_id=alert.get("alert_id"), resident_id=rid)
        if c.get("email"):
            await send_email(c["email"], msg_sub, body, alert_id=alert.get("alert_id"), resident_id=rid)


# -------- API routes --------
@router.get("/notifications")
async def list_notifications(limit: int = 50, user=Depends(get_current_user)):
    items = await db.notifications.find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return items


@router.post("/notifications/test")
async def notifications_test(data: NotificationTest, user=Depends(get_current_user)):
    if data.channel == "sms":
        return await send_sms(data.to, data.body)
    if data.channel == "email":
        return await send_email(data.to, data.subject or "CAOS Care test", data.body)
    return await _log_notification({
        "notification_id": f"notif_log",
        "channel": data.channel,
        "to": data.to,
        "subject": data.subject,
        "body": data.body,
        "status": "logged",
        "provider_response": f"Channel {data.channel} is in-app only for now.",
        "created_at": now_utc().isoformat(),
    })


@router.get("/notifications/status")
async def notifications_status(user=Depends(get_current_user)):
    return {
        "twilio_configured": bool(TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM),
        "resend_configured": bool(RESEND_KEY),
        "twilio_from": TWILIO_FROM if (TWILIO_SID and TWILIO_TOKEN) else None,
        "resend_from": RESEND_FROM if RESEND_KEY else None,
    }


# -------- Family contacts --------
@router.get("/family-contacts")
async def list_family(user=Depends(get_current_user)):
    items = await db.family_contacts.find({}, {"_id": 0}).sort("name", 1).to_list(500)
    for it in items:
        ca = it.get("created_at")
        if ca and not isinstance(ca, str):
            it["created_at"] = ca.isoformat()
    return items


@router.post("/family-contacts")
async def create_family(data: FamilyContactCreate, user=Depends(get_current_user)):
    fc = FamilyContact(**data.model_dump())
    doc = fc.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.family_contacts.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.delete("/family-contacts/{contact_id}")
async def delete_family(contact_id: str, user=Depends(get_current_user)):
    r = await db.family_contacts.delete_one({"contact_id": contact_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"ok": True}
