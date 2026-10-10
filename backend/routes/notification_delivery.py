"""Outbound provider delivery - the one place CAOSCare hands a message to
an external provider (Resend email, Twilio SMS) and records what actually
happened. Every attempt produces exactly one db.notifications record whose
`status` states only what is known (see NotificationStatus in models.py):
"logged" when no provider is configured, "failed" when the provider rejected
it, "sent" when the provider accepted it, and later "delivered"/"bounced"/
"delayed"/"complained" when Resend's delivery webhook reports the outcome
(apply_resend_delivery_event, called from routes/email_inbound.py - Resend
signs every event type for one webhook endpoint with one secret).

Routing (who gets notified) lives in routes/notifications.py; this module
does not decide recipients.
"""
import os
from typing import Optional
from xml.sax.saxutils import escape as xml_escape

import httpx

from models import Notification, now_utc
from deps import db

# Provider event type -> NotificationStatus. email.sent is omitted on
# purpose: our own record is already "sent" from the API response.
RESEND_EVENT_STATUS = {
    "email.delivered": "delivered",
    "email.delivery_delayed": "delayed",
    "email.bounced": "bounced",
    "email.complained": "complained",
    "email.failed": "failed",
    "email.suppressed": "failed",
}
# A later, weaker event must never overwrite a terminal outcome
# (e.g. a late "delivery_delayed" arriving after "delivered").
_TERMINAL = {"delivered", "bounced", "complained", "failed"}


SIMULATED_RESPONSE = "simulated request - recorded only, never sent to a provider"


def _simulated(doc: dict, simulation: dict) -> dict:
    """SC-16: a simulated request's notification is evidence, not a delivery.
    Status "simulated" plus task/receipt/run linkage; never reaches a provider."""
    doc.update({k: v for k, v in simulation.items() if v is not None})
    doc.update(simulated=True, status="simulated", provider_response=SIMULATED_RESPONSE)
    return doc


def provider_config() -> dict:
    """Read at call time, not import time, so a key added to the running
    environment and a restarted process are the only things needed."""
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    return {
        "resend_key": os.environ.get("RESEND_API_KEY", ""),
        "resend_from": os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev"),
        "twilio_sid": sid,
        "twilio_token": token,
        # TWILIO_FROM_PHONE is the older name some deployments set; accepted as an alias.
        "twilio_from": os.environ.get("TWILIO_FROM_NUMBER") or os.environ.get("TWILIO_FROM_PHONE", ""),
    }


async def _save(doc: dict) -> dict:
    if not isinstance(doc.get("created_at"), str):
        doc["created_at"] = (doc.get("created_at") or now_utc()).isoformat()
    await db.notifications.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def record_undeliverable(channel: str, reason: str, *, simulation: Optional[dict] = None, **context) -> dict:
    """A notification that had nowhere to go (e.g. a department with no
    reachable address) is recorded as failed, never silently skipped."""
    doc = Notification(channel=channel, to="", body=reason, status="failed",
                       provider_response=reason, **context).model_dump()
    if simulation:
        _simulated(doc, simulation)
    return await _save(doc)


async def send_email(to: str, subject: str, body: str, *, simulation: Optional[dict] = None, **context) -> dict:
    """context: alert_id, resident_id, department, route,
    related_object_type, related_object_id, receipt_id (all optional)."""
    cfg = provider_config()
    doc = Notification(channel="email", to=to, subject=subject, body=body[:4000], **context).model_dump()
    if simulation:
        return await _save(_simulated(doc, simulation))
    if not cfg["resend_key"]:
        doc["status"] = "logged"
        doc["provider_response"] = "Resend not configured - recorded only, not sent"
        return await _save(doc)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {cfg['resend_key']}"},
                json={"from": cfg["resend_from"], "to": [to], "subject": subject, "text": body},
            )
        doc["status"] = "sent" if resp.status_code < 300 else "failed"
        doc["provider_response"] = resp.text[:500]
        if resp.status_code < 300:
            doc["provider_message_id"] = (resp.json() or {}).get("id")
    except Exception as e:
        doc["status"] = "failed"
        doc["provider_response"] = f"exception: {e}"
    return await _save(doc)


async def _twilio_post(doc: dict, path: str, data: dict) -> dict:
    """Hand one request to Twilio's REST API (httpx; no twilio package) and
    set doc status from what actually happened. Caller has checked config."""
    cfg = provider_config()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{cfg['twilio_sid']}/{path}",
                auth=(cfg["twilio_sid"], cfg["twilio_token"]),
                data={"From": cfg["twilio_from"], **data},
            )
        doc["status"] = "sent" if resp.status_code < 300 else "failed"
        doc["provider_response"] = resp.text[:500]
        if resp.status_code < 300:
            doc["provider_message_id"] = (resp.json() or {}).get("sid")
    except Exception as e:
        doc["status"] = "failed"
        doc["provider_response"] = f"exception: {e}"
    return await _save(doc)


def _twilio_ready(cfg: dict) -> bool:
    return bool(cfg["twilio_sid"] and cfg["twilio_token"] and cfg["twilio_from"])


async def send_sms(to: str, body: str, *, simulation: Optional[dict] = None, **context) -> dict:
    cfg = provider_config()
    doc = Notification(channel="sms", to=to, body=body[:1500], **context).model_dump()
    if simulation:
        return await _save(_simulated(doc, simulation))
    if not _twilio_ready(cfg):
        doc["status"] = "logged"
        doc["provider_response"] = "Twilio not configured - recorded only, not sent"
        return await _save(doc)
    return await _twilio_post(doc, "Messages.json", {"To": to, "Body": body[:1500]})


async def place_call(to: str, message: str, *, simulation: Optional[dict] = None, **context) -> dict:
    """One outbound Twilio voice call that speaks `message`. Same recording
    rules as send_sms: logged without a provider, sent only when Twilio
    accepted the call (not that anyone answered), failed otherwise."""
    cfg = provider_config()
    doc = Notification(channel="voice", to=to, body=message[:500], **context).model_dump()
    if simulation:
        return await _save(_simulated(doc, simulation))
    if not _twilio_ready(cfg):
        doc["status"] = "logged"
        doc["provider_response"] = "Twilio not configured - recorded only, not called"
        return await _save(doc)
    twiml = f"<Response><Say>{xml_escape(message[:500])}</Say></Response>"
    return await _twilio_post(doc, "Calls.json", {"To": to, "Twiml": twiml})


_RESULT_LABEL = {"sent": "unverified", "logged": "unverified", "failed": "failed", "simulated": "simulated"}


async def notify_alert_phone(kind: str, to: str, message: str, alert: dict, *,
                             actor_id: str, authority: str, simulation: Optional[dict] = None) -> dict:
    """SMS ("sms") or voice call ("call") about one alert, with its receipt.

    Used by the escalation tick and the live-line request, so both go through
    the one provider path above. The notification record is linked to the
    alert; the receipt (a NEW one per attempt) names the actor and authority
    and cites the notification. Provider acceptance is "unverified" - it
    does not prove the phone rang or the text arrived."""
    from routes.receipts import create_receipt  # lazy: receipts imports models only, avoid cycles
    link = dict(alert_id=alert.get("alert_id"), resident_id=alert.get("resident_id"),
                related_object_type="alert", related_object_id=alert.get("alert_id"))
    if kind == "call":
        note = await place_call(to, message, simulation=simulation, **link)
    else:
        note = await send_sms(to, message, simulation=simulation, **link)
    status = note["status"]
    receipt = await create_receipt(
        action_type=f"alert_{kind}_attempt",
        related_object_type="alert",
        related_object_id=alert.get("alert_id"),
        source="system",
        resident_id=alert.get("resident_id"),
        room=alert.get("room"),
        zone=alert.get("zone"),
        status="failed" if status == "failed" else "completed",
        result=f"{kind} to {to}: {status}",
        failure_reason=note.get("provider_response") if status == "failed" else None,
        provenance={
            "actor_id": actor_id, "actor_type": "system", "actor_name": actor_id,
            "authority": authority, "channel": kind,
            "simulated": bool(simulation),
            "simulation_run_id": (simulation or {}).get("simulation_run_id"),
            "after_state": {"notification_id": note["notification_id"], "notification_status": status},
            "result_label": _RESULT_LABEL.get(status, "unverified"),
            "provider_refs": [r for r in (note.get("provider_message_id"),) if r],
            "next_state": "awaiting_staff_acknowledgement",
        },
    )
    await db.notifications.update_one({"notification_id": note["notification_id"]},
                                      {"$set": {"receipt_id": receipt["receipt_id"]}})
    note["receipt_id"] = receipt["receipt_id"]
    return note


async def alert_provenance_flag(alert: dict) -> Optional[dict]:
    """SC-16 for alerts: an alert is simulated if it says so or belongs to a
    synthetic resident (server-set marker); never decided by a caller."""
    synthetic = bool(alert.get("simulated"))
    if not synthetic and alert.get("resident_id"):
        r = await db.residents.find_one({"resident_id": alert["resident_id"]}, {"_id": 0, "synthetic": 1})
        synthetic = bool(r and r.get("synthetic"))
    if not synthetic:
        return None
    return {"simulated": True, "simulation_scope": alert.get("simulation_scope") or "demo_room",
            "simulation_run_id": alert.get("simulation_run_id")}


async def apply_resend_delivery_event(event_type: str, data: dict, occurred_at: Optional[str]) -> dict:
    """Attach a Resend delivery event to the notification it concerns.
    Always appends to delivery_events (full history); only advances
    `status` when the event maps to one and the current status isn't
    already terminal."""
    email_id = data.get("email_id")
    note = None
    if event_type == "email.bounced":
        b = data.get("bounce") or {}
        note = " / ".join(x for x in (b.get("type"), b.get("subType"), b.get("message")) if x) or None
    event = {"type": event_type, "at": occurred_at or now_utc().isoformat(), "detail": note}
    existing = await db.notifications.find_one(
        {"provider_message_id": email_id}, {"_id": 0, "notification_id": 1, "status": 1},
    ) if email_id else None
    if not existing:
        return {"matched": False, "email_id": email_id}
    nid = existing["notification_id"]
    # History first, unconditionally: every received event is kept whatever happens to the status.
    await db.notifications.update_one({"notification_id": nid}, {"$push": {"delivery_events": event}})
    # The terminal-status guard lives IN the update filter, so it is evaluated atomically against the stored status.
    # (Reading the status first and writing by id alone let a concurrent late "delayed" overwrite "delivered".)
    new_status = RESEND_EVENT_STATUS.get(event_type)
    if new_status:
        await db.notifications.update_one(
            {"notification_id": nid, "status": {"$nin": sorted(_TERMINAL)}}, {"$set": {"status": new_status}})
    current = await db.notifications.find_one({"notification_id": nid}, {"_id": 0, "status": 1})
    return {"matched": True, "notification_id": existing["notification_id"],
            "notification_status": (current or {}).get("status")}
