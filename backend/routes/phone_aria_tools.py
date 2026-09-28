"""Tools Aria has on a handset call (server-side; the room kiosk's tools run
in the browser). Pilot 1 set only. Each calls the same backend functions the
room path uses - no parallel request model.

Truth rules: a transfer or family call is "requested" when the tool returns;
whether it rang or connected comes later from Asterisk events. Aria never
dials 911 - the resident hangs up and dials it (docs/PILOT1_COMMUNICATIONS.md D6).
"""
import os
import re
from typing import Awaitable, Callable, Optional

from deps import db
from routes.call_lifecycle import advance, create_call
from routes.telephony_endpoints import front_desk_extension

# Mirrors ENDING_PHRASES in frontend/src/lib/realtimeDeviceTools.js (the room
# path's grounding guard): hang up only when the resident actually said so.
ENDING_PHRASES = re.compile(
    r"\b(end the call|end (this |our )?conversation|hang up|good\s*bye|that'?s all( for now)?|"
    r"that'?ll be all( for now)?|i'?m done|don'?t need you|go away)\b", re.IGNORECASE)

OpenAIPost = Callable[[str, dict], Awaitable[int]]


async def approved_family_contacts(resident_id: Optional[str]) -> list[dict]:
    if not resident_id:
        return []
    return await db.family_contacts.find(
        {"resident_id": resident_id, "allow_calls": True, "phone": {"$nin": [None, ""]}},
        {"_id": 0, "contact_id": 1, "name": 1, "relationship": 1},
    ).to_list(20)


def build_phone_tools(family: list[dict], categories: list[str]) -> list[dict]:
    tools = [
        {"type": "function", "name": "request_staff_help",
         "description": "File a request for staff (maintenance, nursing, kitchen, front desk...). Use the resident's own words. Filing is not the same as someone coming.",
         "parameters": {"type": "object", "properties": {
             "category": {"type": "string", "enum": categories},
             "summary": {"type": "string", "description": "What the resident asked for, in their words. Never add a time they did not say."},
             "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"]}},
             "required": ["category", "summary"]}},
        {"type": "function", "name": "check_request_status",
         "description": "Current status of the resident's open request, from the real record.",
         "parameters": {"type": "object", "properties": {"category": {"type": "string", "enum": categories}}}},
        {"type": "function", "name": "transfer_to_front_desk",
         "description": "Connect this phone call to the front desk. Say you are connecting them first. You leave the call.",
         "parameters": {"type": "object", "properties": {}}},
        {"type": "function", "name": "end_call",
         "description": "Hang up, only when the resident has said goodbye or asked to end the call.",
         "parameters": {"type": "object", "properties": {}}},
    ]
    if family:
        tools.append({
            "type": "function", "name": "call_family_contact",
            "description": "Call one of the resident's approved family contacts. Only these people can be called; the number is on file, never ask for one.",
            "parameters": {"type": "object", "properties": {"contact_id": {
                "type": "string", "enum": [c["contact_id"] for c in family],
                "description": "; ".join(f"{c['contact_id']} = {c['name']} ({c.get('relationship') or 'family'})" for c in family)}},
                "required": ["contact_id"]}})
    return tools


def refer_uri(token: str) -> str:
    return f"sip:77{token}@{os.environ.get('CAOS_REFER_HOST', 'caoscare-pbx')}"


async def _transfer(call: dict, kind: str, openai_post: OpenAIPost, **fields) -> dict:
    """Create the outbound CallSession with a one-time token, then ask OpenAI
    to REFER the handset back to Asterisk, which dials the resolved target.
    The REFER is sent after Aria finishes speaking (see sideband)."""
    child = await create_call(kind, with_token=True, receipt_source="aria_voice", parent_call_id=call["call_id"],
                              room=call.get("room"), resident_id=call.get("resident_id"),
                              conversation_session_id=call.get("conversation_session_id"), **fields)

    async def do_refer():
        status = await openai_post(f"/realtime/calls/{call['openai_call_id']}/refer",
                                   {"target_uri": refer_uri(child["dial_token"])})
        if status >= 300:
            await advance(child["call_id"], "failed", source="openai", detail=f"refer rejected ({status})")
    return {"child": child, "after_speech": do_refer}


async def run_phone_tool(name: str, args: dict, call: dict, last_user_text: str,
                         openai_post: OpenAIPost) -> dict:
    """Returns {"output": dict for the model, "after_speech": optional coroutine fn}."""
    from routes.resident_requests import ResidentRequestInput, create_resident_request, resident_request_status
    session = call.get("conversation_session_id")
    if name == "request_staff_help":
        try:
            r = await create_resident_request(ResidentRequestInput(
                category=args.get("category", ""), summary=args.get("summary", ""),
                resident_words=last_user_text or None, priority=args.get("priority") or "normal",
                resident_id=call.get("resident_id"), room=call.get("room"),
                source="aria_voice", conversation_session_id=session))
        except Exception as e:
            detail = getattr(e, "detail", str(e))
            return {"output": {"ok": False, "detail": detail}}
        return {"output": {"ok": True, "filed": True, **{k: r.get(k) for k in ("status", "duplicate", "spoken") if k in r}}}
    if name == "check_request_status":
        try:
            r = await resident_request_status(resident_id=call.get("resident_id"), room=call.get("room"),
                                              conversation_session_id=session, category=args.get("category"))
        except Exception as e:
            return {"output": {"ok": False, "detail": getattr(e, "detail", str(e))}}
        return {"output": r}
    if name == "transfer_to_front_desk":
        ext = await front_desk_extension()
        if not ext:
            return {"output": {"ok": False, "message": "No front desk phone is set up. Offer to file a front desk request instead."}}
        t = await _transfer(call, "front_desk", openai_post, target_extension=ext, target_label="the front desk")
        return {"output": {"ok": True, "message": "Connecting to the front desk now. Nobody has answered yet."},
                "after_speech": t["after_speech"]}
    if name == "call_family_contact":
        approved = {c["contact_id"]: c for c in await approved_family_contacts(call.get("resident_id"))}
        contact = approved.get(args.get("contact_id"))
        if not contact:
            return {"output": {"ok": False, "message": "That person is not on the approved call list."}}
        label = f"{contact['name']} ({contact.get('relationship') or 'family'})"
        t = await _transfer(call, "family", openai_post, family_contact_id=contact["contact_id"], target_label=label)
        return {"output": {"ok": True, "message": f"Calling {contact['name']} now. It has not rung yet."},
                "after_speech": t["after_speech"]}
    if name == "end_call":
        if not ENDING_PHRASES.search(last_user_text or ""):
            return {"output": {"ok": False, "message": "Just to check - would you like to hang up?"}}

        async def hangup():
            await openai_post(f"/realtime/calls/{call['openai_call_id']}/hangup", {})
        return {"output": {"ok": True, "message": "Say goodbye."}, "after_speech": hangup}
    return {"output": {"ok": False, "message": f"Unknown tool {name}"}}
