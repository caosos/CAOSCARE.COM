"""Email setup readiness: what is still missing before real department email works.

Read-only and secret-free: reports whether each prerequisite is set (never the value), which active
departments have no inbox address, and which inbound lanes have no approved sender. It sends nothing.
Mirrors docs/PILOT1_COMMUNICATIONS.md section 1 "Configuration / runtime gaps".
"""
import os

from fastapi import APIRouter, Depends

from deps import db, require_admin
from routes.notification_delivery import provider_config

router = APIRouter(tags=["notifications"])

DEFAULT_FROM = "onboarding@resend.dev"
INBOUND_LANES = ("menu", "activities")


@router.get("/notifications/readiness")
async def email_readiness(user=Depends(require_admin)):
    cfg = provider_config()
    depts = await db.departments.find({"is_active": {"$ne": False}}, {"_id": 0, "slug": 1, "label": 1, "contact_email": 1}).to_list(100)
    missing_inbox = [{"slug": d["slug"], "label": d.get("label") or d["slug"]} for d in depts if not (d.get("contact_email") or "").strip()]
    lane_counts = {}
    for lane in INBOUND_LANES:
        lane_counts[lane] = await db.email_allowlist.count_documents({"lane": lane, "active": True})
    checks = [
        {"id": "resend_key", "ok": bool(cfg["resend_key"]), "fix": "Set RESEND_API_KEY in the backend environment"},
        {"id": "sending_domain", "ok": bool(cfg["resend_key"]) and cfg["resend_from"] != DEFAULT_FROM,
         "fix": "Verify a sending domain in Resend and set RESEND_FROM_EMAIL on it (the default can only reach the account owner)"},
        {"id": "webhook_secret", "ok": bool(os.environ.get("RESEND_WEBHOOK_SECRET")),
         "fix": "Create the Resend webhook to /api/email/inbound/resend and set RESEND_WEBHOOK_SECRET (inbound mail and delivery events are refused without it)"},
        {"id": "department_inboxes", "ok": not missing_inbox, "fix": "Set an inbox address on each department in Admin > Departments"},
        {"id": "inbound_menu_sender", "ok": lane_counts["menu"] > 0, "fix": "Approve the kitchen sender for the menu lane in Email & notifications"},
        {"id": "inbound_activities_sender", "ok": lane_counts["activities"] > 0, "fix": "Approve the activities sender for the activities lane in Email & notifications"},
    ]
    return {"ready": all(c["ok"] for c in checks), "checks": checks, "departments_missing_inbox": missing_inbox,
            "note": "Reports configuration only; nothing was sent. Real delivery is proven by the delivery log, not by this list."}
