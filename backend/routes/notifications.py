"""Notification routing - who gets told about what. Provider delivery and
delivery truth live in routes/notification_delivery.py; send_email/send_sms
are re-exported here because existing callers import them from this module."""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from models import NotificationTest, FamilyContact, FamilyContactCreate, now_utc
from deps import db, get_current_user
from routes.notification_delivery import (  # noqa: F401 - send_* re-exported
    send_email, send_sms, record_undeliverable, provider_config, _save as _log_notification,
)

router = APIRouter(tags=["notifications"])


async def notify_department(visibility_role: str, subject: str, body: str, *,
                            related_object_type: Optional[str] = None,
                            related_object_id: Optional[str] = None) -> list[dict]:
    """Email a department and return every notification record produced.
    Routes, in order, falling through when a tier has no address OR every
    send in it failed at the provider:
    1. the department's own Department.contact_email (a shared inbox);
    2. every staff User whose .department matches this slug;
    3. admin/owner, so a request is never silently un-notified.
    "logged" (no provider configured) is not a failure to fall through on -
    it would be logged identically at every tier. If no tier has any
    address, one failed record says so. Shared by resident_requests.py,
    tasks.py, and transportation*.py - one notification path, not one per
    lane."""
    ctx = {"department": visibility_role, "related_object_type": related_object_type,
           "related_object_id": related_object_id}
    dept = await db.departments.find_one({"slug": visibility_role}, {"_id": 0, "contact_email": 1})
    staff = await db.users.find({"department": visibility_role}, {"_id": 0, "email": 1}).to_list(50)
    admins = await db.users.find({"role": {"$in": ["admin", "owner"]}}, {"_id": 0, "email": 1}).to_list(50)
    tiers = [
        ("department_contact", [dept.get("contact_email")] if dept else []),
        ("department_staff", [u.get("email") for u in staff]),
        ("admin_fallback", [u.get("email") for u in admins]),
    ]
    records: list[dict] = []
    for route, addrs in tiers:
        addrs = list(dict.fromkeys(a for a in addrs if a))
        if not addrs:
            continue
        tier = [await send_email(a, subject, body, route=route, **ctx) for a in addrs]
        records.extend(tier)
        if any(r["status"] != "failed" for r in tier):
            return records
    if not records:
        records.append(await record_undeliverable(
            "email", f"No email address for department '{visibility_role}', its staff, or any admin/owner", **ctx))
    return records


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
async def list_notifications(limit: int = 50, related_object_id: Optional[str] = None,
                             department: Optional[str] = None, status: Optional[str] = None,
                             user=Depends(get_current_user)):
    q = {k: v for k, v in (("related_object_id", related_object_id), ("department", department),
                           ("status", status)) if v}
    return await db.notifications.find(q, {"_id": 0}).sort("created_at", -1).to_list(min(limit, 500))


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
    cfg = provider_config()
    twilio = bool(cfg["twilio_sid"] and cfg["twilio_token"] and cfg["twilio_from"])
    return {
        "twilio_configured": twilio,
        "resend_configured": bool(cfg["resend_key"]),
        "twilio_from": cfg["twilio_from"] if twilio else None,
        "resend_from": cfg["resend_from"] if cfg["resend_key"] else None,
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
