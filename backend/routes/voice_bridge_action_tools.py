"""Voice bridge tools that change something in the room or start a workflow:
room devices (room_device_tools: lights, TV, thermostat), transportation,
call for help. Each calls the same canonical service the room screen uses
(devices.execute_room_command, transportation.create_transport_request,
ai_escalation.ai_escalate); the result text says only what the service
confirmed."""
from fastapi import HTTPException

from routes.room_device_tools import ROOM_DEVICE_TOOLS, run_room_device_tool

ACTION_TOOLS = ROOM_DEVICE_TOOLS + ("request_transportation", "call_for_help")


async def run_action_tool(name: str, args: dict, ctx: dict) -> dict:
    if name in ROOM_DEVICE_TOOLS:
        return await run_room_device_tool(name, args, ctx)
    if name == "request_transportation":
        from routes.transportation import TransportRequestInput, create_transport_request
        try:
            r = await create_transport_request(TransportRequestInput(
                resident_id=ctx.get("resident_id"), room=ctx.get("room"), purpose=args.get("purpose") or "ride",
                requested_for_date=args.get("requested_for_date") or "",
                requested_for_time_label=args.get("requested_for_time_label"),
                source="aria_voice", conversation_session_id=ctx.get("session_id")))
        except HTTPException as e:
            return {"ok": False, "status": e.status_code, "detail": e.detail}
        task = r.get("task") or {}
        return {"ok": True, "task_id": r.get("task_id") or task.get("task_id"),
                "receipt_id": r.get("receipt_id"), "duplicate": bool(r.get("duplicate") or r.get("re_requested")),
                "booked": bool(r.get("booked")),
                "message": "ride booked" if r.get("booked") else
                "ride requested, not booked yet - staff will confirm; do not say it is booked"}
    if name == "call_for_help":
        from routes.ai_escalation import AiEscalateInput, ai_escalate
        try:
            r = await ai_escalate(AiEscalateInput(
                reason=args.get("reason") or "help requested by voice", severity=args.get("severity") or "assist",
                resident_id=ctx.get("resident_id"), kiosk_id=ctx.get("kiosk_id"), room=ctx.get("room"),
                session_id=ctx.get("session_id")))
        except HTTPException as e:
            return {"ok": False, "detail": e.detail}
        state = r.get("wording_state")
        return {"ok": state in ("paged", "sent"), "alert_id": r.get("alert_id"), "wording_state": state,
                "receipt_id": (r.get("dispatch") or {}).get("receipt_id"),
                "message": {"paged": "a nurse has been paged", "sent": "sent to the care team"}.get(
                    state, "could not reach the care team - tell them to press the call button")}
    return {"ok": False, "detail": f"tool {name} is not available on this endpoint"}
