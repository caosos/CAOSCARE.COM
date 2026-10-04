"""Receipts for the voice bridge (receipt law: no action without a receipt,
no receipt without provenance).

One receipt per bridge turn, chained per session: the session's first
receipt is its origin (correlation_id = its own id), every later turn's
parent is the previous turn's receipt. Workflow objects a turn touched (a
staff request) keep their own lifecycle receipts; the turn receipt names
them and their receipt ids. Refusals (unknown device, conversation bound to
another room) are recorded on the device, outside any session chain.
"""
from typing import Optional

from models import uid
from routes.actor_context import actor_resident_claim
from routes.receipts import create_receipt
from routes.task_lifecycle import result_label_for


def _actor(ident: dict):
    return actor_resident_claim(ident.get("resident_id"), ident.get("room"), "voice_bridge",
                                synthetic=ident.get("synthetic", False))


def authority_for(ident: dict) -> str:
    return f"registered_voice_device:{ident['device_id']}->{ident['kiosk_id']}"


def workflow_objects(results: list) -> list:
    out = []
    for name, r in results:
        if isinstance(r, dict) and r.get("task_id"):
            out.append({"type": "task", "id": r["task_id"], "receipt_id": r.get("receipt_id"),
                        "tool": name, "duplicate": bool(r.get("duplicate"))})
        elif isinstance(r, dict) and r.get("alert_id"):
            out.append({"type": "alert", "id": r["alert_id"], "receipt_id": r.get("receipt_id"),
                        "tool": name, "duplicate": False})
    return out


async def turn_receipt(*, session: dict, ident: dict, ha_conversation_id: str, utterance: str,
                       action_type: str, before: dict, after: dict, tools: list, results: list,
                       reply: str, next_state: str, status: str = "completed",
                       failure_reason: Optional[str] = None, extra: Optional[dict] = None) -> dict:
    actor = _actor(ident)
    rid = uid("rcpt")
    parent = session.get("last_receipt_id")
    evidence = {
        "device_id": ident["device_id"], "kiosk_id": ident["kiosk_id"],
        "facility_id": ident.get("facility_id"), "facility_name": ident.get("facility_name"),
        "ha_conversation_id": ha_conversation_id, "utterance": utterance,
        "authorization": {"bridge_credential": "valid", "device_mapping": ident["kiosk_id"],
                          "identity_basis": actor.identity_basis},
        "tools": tools, "workflow_objects": workflow_objects(results), "response_text": reply,
        **(extra or {}),
    }
    return await create_receipt(
        action_type=action_type, related_object_type="voice_session",
        related_object_id=session["session_id"], source="aria_voice",
        resident_id=ident["resident_id"], room=ident["room"],
        conversation_session_id=session["session_id"], status=status,
        result=reply[:300] if status == "completed" else None, failure_reason=failure_reason,
        receipt_id=rid,
        provenance={**actor.receipt_fields(), "authority": authority_for(ident),
                    "parent_receipt_id": parent,
                    "correlation_id": session.get("origin_receipt_id") or rid,
                    "before_state": before, "after_state": after,
                    "result_label": "failed" if status == "failed" else result_label_for(actor),
                    "next_state": next_state, "evidence": evidence})


async def refusal_receipt(*, device_ids: list, ha_conversation_id: Optional[str], utterance: str,
                          reason: str, ident: Optional[dict] = None) -> dict:
    """A turn CAOSCare would not serve. Nothing was executed."""
    device = next((d for d in device_ids if d), None) or "unknown"
    return await create_receipt(
        action_type="voice_turn_refused", related_object_type="voice_device",
        related_object_id=device, source="aria_voice",
        resident_id=(ident or {}).get("resident_id"), room=(ident or {}).get("room"),
        status="failed", failure_reason=reason,
        provenance={"actor_id": f"voice_device:{device}", "actor_type": "external-provider",
                    "identity_basis": "unverified_device", "channel": "voice_bridge",
                    "authority": "none", "result_label": "failed", "next_state": "refused",
                    "evidence": {"device_ids": device_ids, "ha_conversation_id": ha_conversation_id,
                                 "utterance": utterance}})
