"""Receipts for resident-facing content changes (menu and activities).

Every create / edit / publish / supersede / delete of menu or schedule
content writes one durable receipt through the existing create_receipt():
who changed it (the authenticated user, or the named inbound-email process),
under what authority, a before/after summary, and the ingest / batch id that
ties it to the calendar or menu it came from. Reads never call this.

Receipts chain per content object: each one points at the object's previous
receipt (parent) and shares the first one's id as the workflow id, so a
dish or calendar row's whole history can be read with
GET /receipts?correlation_id=. Nothing is rewritten.
"""
import dataclasses
from typing import Optional

from deps import db
from models import uid
from routes.actor_context import ActorContext, actor_from_user, actor_system
from routes.receipts import create_receipt
from routes.service_content_access import MENU_DEPARTMENTS, SCHEDULE_DEPARTMENTS

_MENU_FIELDS = ("date", "meal_period", "item_name", "description", "availability", "status")
_SCHEDULE_FIELDS = ("date", "time_label", "title", "category", "description", "status")


def summarize(kind: str, doc: Optional[dict]) -> Optional[dict]:
    """The few fields a reader needs to see what changed - not the whole
    document (staff-only notes are left out)."""
    if not doc:
        return None
    fields = _MENU_FIELDS if kind == "menu" else _SCHEDULE_FIELDS
    return {k: doc.get(k) for k in fields if doc.get(k) is not None}


def staff_actor(user: dict) -> ActorContext:
    return actor_from_user(user)


def inbound_email_actor() -> ActorContext:
    """The inbound-email process: it only ever makes draft batches; a person
    still publishes them."""
    return dataclasses.replace(actor_system("inbound_email"), channel="email")


def _authority(actor: ActorContext, kind: str) -> str:
    if actor.actor_type == "system":
        return "system:inbound_email"
    if actor.role in ("owner", "admin"):
        return f"admin_override:{actor.role}"
    allowed = MENU_DEPARTMENTS if kind == "menu" else SCHEDULE_DEPARTMENTS
    return f"acts_for:{actor.department}" if actor.department in allowed else "content_editor"


async def record_content_change(
    *, kind: str, action: str, object_type: str, object_id: str, actor: ActorContext,
    before: Optional[dict] = None, after: Optional[dict] = None,
    ingest_id: Optional[str] = None, detail: Optional[dict] = None,
) -> dict:
    """kind is "menu" or "schedule"; action e.g. "created", "edited",
    "published", "deleted"; before/after are summarize() outputs (or small
    batch summaries)."""
    earlier = await db.receipts.find(
        {"related_object_type": object_type, "related_object_id": object_id},
        {"_id": 0, "receipt_id": 1, "correlation_id": 1},
    ).sort("created_at", -1).to_list(1)
    parent = earlier[0]["receipt_id"] if earlier else None
    receipt_id = uid("rcpt")
    correlation = (earlier[0].get("correlation_id") or parent) if earlier else receipt_id
    after_state = dict(after or {})
    if ingest_id:
        after_state["ingest_id"] = ingest_id
    if detail:
        after_state.update(detail)
    return await create_receipt(
        action_type=f"{kind}_content_{action}",
        related_object_type=object_type,
        related_object_id=object_id,
        source="system" if actor.actor_type == "system" else "staff",
        status="completed",
        receipt_id=receipt_id,
        result=f"{kind} {action}",
        provenance={
            **actor.receipt_fields(),
            "authority": _authority(actor, kind),
            "before_state": before,
            "after_state": after_state or None,
            "result_label": "verified",
            "parent_receipt_id": parent,
            "correlation_id": correlation,
        },
    )
