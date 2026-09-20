"""Real inbound email adapter - ONE shared webhook for every department
address (menu@inbound.caoscare.com, activities@inbound.caoscare.com, and
any future department address added to _RECIPIENT_LANES below - no new
infrastructure needed per additional address).

Architecture rule (per the task that created this module): email is
transport/provenance only, never the domain model. This file does no
parsing itself - it verifies the request is genuinely from Resend,
deduplicates retried deliveries, resolves which department the message
was addressed to, checks that department's sender allowlist, and then
calls the exact same internal ingestion functions the dev-test endpoints
call (menu_ingest.create_menu_upload / schedule_ingest.create_schedule_items).
There is no separate parsing implementation here.

Resend's own webhook payload is METADATA ONLY (from/to/subject/attachment
list) - the actual text/html body is fetched separately via Resend's
receiving API using RESEND_API_KEY, immediately after signature
verification passes. This was confirmed against Resend's own docs/skills
reference before writing this, not guessed - see the final report for
this task.

Every inbound email produces exactly one InboundEmailMessage record
(db.inbound_emails, unique on provider_message_id) regardless of outcome -
duplicate, unrecognized recipient, quarantined, routed, or error - so
"what happened to this email" is always answerable from one place.
"""
import html as _html
import os
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request, Depends

from deps import db, require_admin
from models import InboundEmailMessage, now_utc
from routes.email_inbound_signature import verify_resend_webhook, WebhookVerificationError
from routes.email_inbound_allowlist import check_sender_allowed
from routes.menu_ingest import create_menu_upload
from routes.schedule_ingest import create_schedule_items
from routes.realtime_facility import today_facility_date
from routes.receipts import create_receipt

router = APIRouter(prefix="/email/inbound", tags=["email-inbound"])

# Local-part (before "@", lowercase) -> department lane. Adding a future
# department address is one new entry here, nothing else - the domain
# (inbound.caoscare.com or otherwise) is whatever Resend is configured to
# deliver for, so this table intentionally does not hardcode a domain.
_RECIPIENT_LANES = {"menu": "menu", "activities": "activities"}

_DATE_LINE_RE = re.compile(r"(?im)^\s*(?:service\s*)?date\s*:\s*(\d{4}-\d{2}-\d{2})\s*$")
_ADDR_RE = re.compile(r"<([^<>@\s]+@[^<>@\s]+)>|([^\s<>,]+@[^\s<>,]+)")


def _extract_addresses(raw: object) -> list[str]:
    """Resend's JSON normally already gives plain addresses in a list, but
    this defensively also accepts a single string or "Name <addr>" form."""
    if raw is None:
        return []
    values = raw if isinstance(raw, list) else [raw]
    out = []
    for v in values:
        v = str(v)
        m = _ADDR_RE.search(v)
        if m:
            out.append((m.group(1) or m.group(2)).strip().lower())
    return out


def _resolve_lane(to_addresses: list[str]) -> Optional[str]:
    for addr in to_addresses:
        local = addr.split("@", 1)[0].lower()
        if local in _RECIPIENT_LANES:
            return _RECIPIENT_LANES[local]
    return None


def _html_to_text(html_body: str) -> str:
    """Minimal, dependency-free HTML->text fallback for when a sender's
    mail client didn't include a plain-text part. Deliberately simple -
    strip tags, unescape entities, collapse blank lines - not a rendering
    engine. Good enough for the same "meal section headers as short
    lines" bodies the plain-text parser already expects; anything more
    elaborate stays needs_review via the existing parser, per the
    directive not to build a document-processing project here."""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", html_body)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = _html.unescape(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


async def _fetch_received_email(email_id: str) -> dict:
    """Calls Resend's receiving API for the full body/attachments the
    webhook itself doesn't carry. Isolated as its own function (module-
    level, not inlined) specifically so tests can monkeypatch it without
    needing a real RESEND_API_KEY or network access."""
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        raise RuntimeError("RESEND_API_KEY is not configured")
    resp = await httpx.AsyncClient(timeout=15).get(
        f"https://api.resend.com/emails/receiving/{email_id}",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    resp.raise_for_status()
    return resp.json()


def _extract_service_date(text_body: str) -> str:
    """An explicit "Date: YYYY-MM-DD" (or "Service date: ...") line in the
    body, matching this project's standing "never guess a date from free
    text" rule (schedule_ingest.py's day headers make the same choice).
    Falls back to the facility's own today - the common real case is a
    kitchen emailing the day's menu same-day or the evening before."""
    m = _DATE_LINE_RE.search(text_body or "")
    return m.group(1) if m else today_facility_date()


async def _save_message(msg: InboundEmailMessage) -> dict:
    doc = msg.model_dump()
    for k in ("received_at", "created_at"):
        if doc.get(k) is not None:
            doc[k] = doc[k].isoformat()
    await db.inbound_emails.insert_one(dict(doc))
    doc.pop("_id", None)
    return doc


async def _record_outcome(inbound_id: str, **patch) -> None:
    await db.inbound_emails.update_one({"inbound_id": inbound_id}, {"$set": patch})
    await create_receipt(
        action_type=f"inbound_email.{patch.get('status', 'received')}",
        related_object_type="inbound_email", related_object_id=inbound_id,
        source="system", result=patch.get("error_message") or patch.get("parse_notes"),
    )


@router.post("/resend")
async def resend_inbound_webhook(request: Request):
    """The one real inbound-email entry point. Verifies the request is a
    genuine, fresh Resend delivery before doing anything else - an
    unverified request is rejected outright, never processed."""
    secret = os.environ.get("RESEND_WEBHOOK_SECRET", "")
    if not secret:
        # Fails closed, not open: with no secret configured this endpoint
        # simply cannot be used yet - it never falls back to trusting an
        # unsigned request. The rest of the application is unaffected by
        # this var being absent (see the router registration in server.py).
        raise HTTPException(status_code=503, detail="Inbound email is not configured on this server yet")

    raw_body = await request.body()
    try:
        verify_resend_webhook(
            secret=secret,
            svix_id=request.headers.get("svix-id"),
            svix_timestamp=request.headers.get("svix-timestamp"),
            svix_signature=request.headers.get("svix-signature"),
            body=raw_body,
        )
    except WebhookVerificationError as e:
        raise HTTPException(status_code=401, detail=f"Webhook verification failed: {e}")

    payload = await request.json()
    event_type = payload.get("type")
    data = payload.get("data") or {}
    provider_message_id = data.get("email_id")
    svix_id = request.headers.get("svix-id")
    if not provider_message_id:
        raise HTTPException(status_code=400, detail="Missing data.email_id in webhook payload")

    # Dedup: the real email's own identity (provider_message_id), not the
    # webhook delivery attempt (svix_id) - a real retried delivery of the
    # same email must never process twice, per the task's explicit rule.
    existing = await db.inbound_emails.find_one({"provider_message_id": provider_message_id}, {"_id": 0})
    if existing:
        return {"ok": True, "status": "duplicate", "inbound_id": existing["inbound_id"]}

    from_address = (_extract_addresses(data.get("from")) or [""])[0]
    to_addresses = _extract_addresses(data.get("to"))
    received_at = None
    created_at_raw = payload.get("created_at")
    if created_at_raw:
        try:
            received_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
        except ValueError:
            received_at = None

    msg = InboundEmailMessage(
        provider_message_id=provider_message_id,
        provider_event_id=svix_id,
        provider_event_type=event_type,
        from_address=from_address,
        to_addresses=to_addresses,
        subject=data.get("subject") or "",
        received_at=received_at,
        attachments=[
            {"filename": a.get("filename"), "content_type": a.get("content_type")}
            for a in (data.get("attachments") or [])
        ],
    )
    saved = await _save_message(msg)
    inbound_id = saved["inbound_id"]

    lane = _resolve_lane(to_addresses)
    if not lane:
        await _record_outcome(inbound_id, status="unrecognized_recipient")
        return {"ok": True, "status": "unrecognized_recipient", "inbound_id": inbound_id}

    # Fetch the real body (the webhook itself never carries it) BEFORE the
    # allowlist check - a quarantined message still preserves its body so
    # staff reviewing it can actually see what it said, not just
    # from/to/subject. Only an unrecognized-recipient message (no lane at
    # all - nobody would review it as "for the kitchen") skips this.
    try:
        full = await _fetch_received_email(provider_message_id)
    except Exception as e:
        await _record_outcome(inbound_id, status="error", routed_lane=lane,
                               error_message=f"could not fetch email body from Resend: {e}")
        raise HTTPException(status_code=502, detail="Could not retrieve the email body from the provider") from e

    text_body = full.get("text") or ""
    html_body = full.get("html") or ""
    if not text_body.strip() and html_body.strip():
        text_body = _html_to_text(html_body)
    await db.inbound_emails.update_one(
        {"inbound_id": inbound_id}, {"$set": {"text_body": text_body[:16000], "html_body": bool(html_body)}},
    )

    if not await check_sender_allowed(lane, from_address):
        await _record_outcome(inbound_id, status="quarantined", routed_lane=lane, sender_trust="quarantined")
        return {"ok": True, "status": "quarantined", "inbound_id": inbound_id}

    try:
        if lane == "menu":
            service_date = _extract_service_date(text_body)
            result = await create_menu_upload(
                raw_text=text_body, service_date=service_date, source="email",
                source_ref=inbound_id, created_by=None,
            )
            linked_type, linked_id = "menu_upload", result["upload_id"]
            parse_status, parse_notes = result.get("parse_status"), result.get("parse_notes")
        else:  # "activities"
            result = await create_schedule_items(
                raw_text=text_body, source="email", source_ref=inbound_id, created_by=None,
            )
            linked_type, linked_id = "schedule_items", None
            parse_status = "parsed" if result["created_count"] else "needs_review"
            parse_notes = "; ".join(result.get("notes") or []) or None
            if result.get("skipped_lines"):
                parse_notes = (parse_notes + "; " if parse_notes else "") + \
                    f"{len(result['skipped_lines'])} line(s) skipped - see skipped_lines."
    except HTTPException as e:
        # A malformed real email (e.g. no day headers at all) - permanent,
        # a retry from Resend would not fix it. Record and ack (200), do
        # not raise, so Resend does not retry-storm an email that will
        # never parse.
        await _record_outcome(inbound_id, status="error", routed_lane=lane, sender_trust="approved",
                               error_message=str(e.detail))
        return {"ok": True, "status": "error", "inbound_id": inbound_id, "detail": e.detail}

    await _record_outcome(
        inbound_id, status="routed", routed_lane=lane, sender_trust="approved",
        parse_status=parse_status, parse_notes=parse_notes,
        linked_object_type=linked_type, linked_object_id=linked_id,
    )
    return {"ok": True, "status": "routed", "inbound_id": inbound_id, "routed_lane": lane,
            "linked_object_type": linked_type, "linked_object_id": linked_id}


@router.get("/messages")
async def list_inbound_messages(limit: int = 100, user=Depends(require_admin)):
    """Read-only provenance list - who emailed what, when, parse status,
    and what it produced. Admin-only, same tier as /receipts and /events -
    this is the backend data an Admin UI provenance panel would read from
    (see the final report for what's still needed on the frontend)."""
    items = await db.inbound_emails.find({}, {"_id": 0, "text_body": 0, "html_body": 0}) \
        .sort("created_at", -1).to_list(min(limit, 500))
    return items
