"""Server-side resident tools for the voice bridge (spike).

The browser realtime path runs these tools in JavaScript and calls the
same backend functions over HTTP. A Home Assistant conversation agent has
no browser, so the bridge runs them here — every one calls the canonical
CAOSCare service in-process (menu, schedule, the resident request bus with
its dedup/receipts/notifications, request status). Nothing here writes a
task, receipt or workflow state on its own.

Tool schemas come from the realtime tool list (`_build_tools`), so the
model sees the same definitions on both paths.
"""
from fastapi import HTTPException

from routes.menu import public_today as menu_today
from routes.schedule import public_today as schedule_today
from routes.realtime_facility import _facility_now
from routes.realtime_tools import _build_tools
from routes.resident_requests import (
    ResidentRequestInput, create_resident_request,
    resident_request_status, resident_request_history,
)

from routes.voice_bridge_action_tools import ACTION_TOOLS, run_action_tool

BRIDGE_TOOLS = ("get_menu", "get_todays_schedule", "request_staff_help",
                "check_request_status", "check_request_history",
                "get_current_time", "end_call") + ACTION_TOOLS
ENDING_TOOLS = ("end_call",)


async def bridge_tool_schemas() -> list:
    """Chat-completions form of the realtime schemas for the bridge tools."""
    out = []
    for t in await _build_tools():
        if t.get("name") in BRIDGE_TOOLS:
            out.append({"type": "function", "function": {
                "name": t["name"], "description": t.get("description", ""),
                "parameters": t.get("parameters") or {"type": "object", "properties": {}}}})
    return out


async def run_bridge_tool(name: str, args: dict, ctx: dict) -> dict:
    """ctx: resident_id, room, session_id, last_user_text (server-resolved)."""
    if name == "get_menu":
        items = await menu_today(date=args.get("date"), meal_period=args.get("meal_period"))
        return {"ok": True, "items": [{"meal_period": i.get("meal_period"), "item": i.get("item_name"),
                                       "availability": i.get("availability")} for i in items],
                "note": None if items else "no published menu for that"}
    if name == "get_todays_schedule":
        items = await schedule_today(date=None, category=None)
        return {"ok": True, "items": [{"time": i.get("time_label"), "title": i.get("title"),
                                       "location": i.get("location")} for i in items],
                "note": None if items else "nothing is listed on today's schedule"}
    if name == "request_staff_help":
        data = ResidentRequestInput(
            category=args.get("category") or "nursing",
            resident_id=ctx.get("resident_id"), room=ctx.get("room"),
            resident_words=ctx.get("last_user_text") or args.get("summary"),
            summary=args.get("summary") or "Resident request",
            priority=args.get("priority") or "normal", source="aria_voice",
            conversation_session_id=ctx.get("session_id"),
        )
        try:
            res = await create_resident_request(data, origin_authority=ctx.get("origin_authority"))
        except HTTPException as e:
            return {"ok": False, "status": e.status_code, "detail": e.detail}
        if res.get("duplicate"):
            msg = (f"there's already an open {data.category} request on file; staff were told again. "
                   + (res.get("spoken") or ""))
        else:
            msg = (f"request created ({res.get('status')}) and sent to {data.category}. "
                   "No one has picked it up yet - do not say anyone is coming or on the way.")
        return {"ok": True, "message": msg.strip(), "task_id": res.get("task_id"),
                "receipt_id": res.get("receipt_id"), "duplicate": bool(res.get("duplicate"))}
    if name in ("check_request_status", "check_request_history"):
        fn = resident_request_history if name == "check_request_history" else resident_request_status
        kw = {"resident_id": ctx.get("resident_id"), "room": None if ctx.get("resident_id") else ctx.get("room"),
              "conversation_session_id": None, "category": args.get("category")}
        return {"ok": True, **await fn(**kw)}
    if name == "get_current_time":
        return {"ok": True, **(await _facility_now())}
    if name in ACTION_TOOLS:
        return await run_action_tool(name, args, ctx)
    if name in ENDING_TOOLS:
        return {"ok": True, "ended": True}
    return {"ok": False, "detail": f"tool {name} is not available on this endpoint"}
