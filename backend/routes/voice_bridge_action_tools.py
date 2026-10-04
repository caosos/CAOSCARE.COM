"""Voice bridge tools that change something in the room or start a workflow:
lights, temperature, transportation, call for help. Each calls the same
canonical service the room screen uses (devices.execute_room_command,
transportation.create_transport_request, ai_escalation.ai_escalate); the
result text says only what the service confirmed."""
from fastapi import HTTPException

from deps import db
from models import DeviceCommandInput

ACTION_TOOLS = ("toggle_light", "adjust_room_temperature", "request_transportation", "call_for_help")


async def _room_command(ctx, action, value, kind=None) -> dict:
    from routes.devices import execute_room_command
    try:
        r = await execute_room_command(ctx["room"], DeviceCommandInput(
            action=action, value=value, kind=kind, session_id=ctx.get("session_id")))
    except HTTPException as e:
        return {"ok": False, "detail": e.detail}
    return {"ok": bool(r.get("verified")), "state": r.get("state"),
            "message": "done and confirmed by the device" if r.get("verified")
            else "sent, but the device did not confirm it - do not say it is done"}


async def _climate_target(ctx, args):
    if args.get("target_f") is not None:
        return float(args["target_f"])
    if args.get("delta_f") is not None:
        dev = await db.smart_devices.find_one(
            {"room": ctx["room"], "capabilities": "temperature", "online": {"$ne": False}}, {"_id": 0, "state": 1})
        cur = ((dev or {}).get("state") or {}).get("temperature")
        if cur is None:
            return None
        return float(cur) + float(args["delta_f"])
    return None


async def run_action_tool(name: str, args: dict, ctx: dict) -> dict:
    if name == "toggle_light":
        out = {"ok": True}
        if args.get("state") in ("on", "off"):
            out = await _room_command(ctx, "power", args["state"], "light")
        if out.get("ok") and args.get("brightness") is not None:
            out = await _room_command(ctx, "brightness", int(args["brightness"]), "light")
        return out if (args.get("state") or args.get("brightness") is not None) else \
            {"ok": False, "detail": "say on, off or a brightness"}
    if name == "adjust_room_temperature":
        if args.get("state") in ("on", "off"):
            out = await _room_command(ctx, "power", args["state"], "thermostat")
            if not out.get("ok"):
                return out
        target = await _climate_target(ctx, args)
        if target is None:
            return {"ok": False, "detail": "no temperature given"} if not args.get("state") else {"ok": True}
        return await _room_command(ctx, "temperature", round(target), "thermostat")
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
