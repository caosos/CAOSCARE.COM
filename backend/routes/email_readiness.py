"""Email setup readiness: what is still missing before real department email works.

Read-only and secret-free: reports whether each prerequisite is set (never the value), which active
departments have no inbox address, and which inbound lanes have no approved sender. It sends nothing.
Mirrors docs/PILOT1_COMMUNICATIONS.md section 1 "Configuration / runtime gaps".
"""
import os
import re

from fastapi import APIRouter, Depends

from deps import db, require_admin
from routes.notification_delivery import provider_config

router = APIRouter(tags=["notifications"])

DEFAULT_FROM = "onboarding@resend.dev"
INBOUND_LANES = ("menu", "activities")
_ADDR = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")


def sender_state(raw: str) -> str:
    """missing | default | invalid | configured, from the configured RESEND_FROM_EMAIL (name <addr> or bare addr)."""
    raw = (raw or "").strip()
    if not raw:
        return "missing"
    m = re.search(r"<([^<>]+)>\s*$", raw)
    addr = (m.group(1) if m else raw).strip()
    if not _ADDR.match(addr):
        return "invalid"
    return "default" if addr.lower() == DEFAULT_FROM else "configured"


def _c(cid, state, fix=None):
    # state: configured | missing | default | invalid | unknown. Only "configured" is ok; "unknown" is never ok.
    return {"id": cid, "state": state, "ok": state == "configured", "fix": None if state == "configured" else fix}


@router.get("/notifications/readiness")
async def email_readiness(user=Depends(require_admin)):
    cfg = provider_config()
    depts = await db.departments.find({"is_active": {"$ne": False}}, {"_id": 0, "slug": 1, "label": 1, "contact_email": 1}).to_list(100)
    missing_inbox = [{"slug": d["slug"], "label": d.get("label") or d["slug"]} for d in depts if not (d.get("contact_email") or "").strip()]
    lane_counts = {}
    for lane in INBOUND_LANES:
        lane_counts[lane] = await db.email_allowlist.count_documents({"lane": lane, "active": True})
    sender = sender_state(cfg.get("resend_from", ""))
    checks = [
        _c("resend_key", "configured" if cfg["resend_key"] else "missing", "Set RESEND_API_KEY in the backend environment"),
        _c("sender_address", sender, "Set RESEND_FROM_EMAIL to a real address on your own domain (blank, invalid, or the Resend default "
           "address cannot be used for facility mail)"),
        _c("sending_domain_verified", "unknown", "Not checked here. Verify the domain inside Resend; a configured sender does not prove it is verified"),
        _c("webhook_secret", "configured" if os.environ.get("RESEND_WEBHOOK_SECRET") else "missing",
           "Create the Resend webhook to /api/email/inbound/resend and set RESEND_WEBHOOK_SECRET (inbound mail and delivery events are refused without it)"),
        _c("webhook_reachable", "unknown", "Not checked here. Resend must be able to reach the public webhook URL; prove it with a real delivery event"),
        _c("department_inboxes", "missing" if missing_inbox else "configured", "Set an inbox address on each department in Admin > Departments"),
        _c("inbound_menu_sender", "configured" if lane_counts["menu"] > 0 else "missing", "Approve the kitchen sender for the menu lane in Email & notifications"),
        _c("inbound_activities_sender", "configured" if lane_counts["activities"] > 0 else "missing", "Approve the activities sender for the activities lane in Email & notifications"),
    ]
    unchecked = [c["id"] for c in checks if c["state"] == "unknown"]
    return {"configuration_complete": all(c["ok"] for c in checks if c["state"] != "unknown"), "verified": False,
            "unverified_items": unchecked, "checks": checks, "departments_missing_inbox": missing_inbox,
            "note": "Reports configuration only; nothing was sent and no provider was contacted. Provider, domain and webhook working are "
                    "UNKNOWN until the delivery log shows a real delivered message."}
