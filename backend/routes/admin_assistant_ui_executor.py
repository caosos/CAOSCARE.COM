"""Executes the semantic UI-guidance tools (admin_assistant_ui_tools.py) -
resolves each target against REAL current data, then returns an ordered
list of PRIMITIVE ui_actions for the frontend to replay
(frontend/src/lib/adminAriaActions.js). Read-only: never calls a mutating
domain endpoint. "Navigation does not imply configuration success" - these
functions only ever report navigated/focused/highlighted/not_found, never
"configured".

Addressing targets by the SAME data-testid values the Admin tab components
already render for every row (res-row-{id}, dev-row-{id}) - no new DOM
attributes needed anywhere, per "other Admin components can register
semantic targets without bespoke Aria code": any component already
following this codebase's existing data-testid convention is already a
valid target.
"""
from deps import db


def _ok(ui_actions: list[dict], **extra) -> dict:
    return {"status": "focused" if ui_actions else "not_found", "ui_actions": ui_actions, **extra}


def _navigate(section: str) -> dict:
    return {"type": "navigate", "section": section}


def _scroll(targets: list[str]) -> dict:
    return {"type": "scroll_to", "targets": targets}


def _highlight(targets: list[str], label: str) -> dict:
    return {"type": "highlight", "targets": targets, "label": label}


async def navigate_admin_section(admin_user: dict, args: dict) -> dict:
    section = args["section"]
    return _ok([_navigate(section)], section=section)


async def focus_resident(admin_user: dict, args: dict) -> dict:
    resident = None
    if args.get("resident_id"):
        resident = await db.residents.find_one({"resident_id": args["resident_id"]}, {"_id": 0})
    elif args.get("name"):
        name = args["name"].strip().lower()
        resident = await db.residents.find_one(
            {"$or": [{"name": {"$regex": name, "$options": "i"}}, {"preferred_name": {"$regex": name, "$options": "i"}}]},
            {"_id": 0},
        )
    if not resident:
        return {"status": "not_found", "ui_actions": [], "detail": "No matching resident found."}
    target = f"resident:{resident['resident_id']}"
    ui_actions = [_navigate("residents"), _scroll([target]), _highlight([target], resident.get("preferred_name") or resident["name"])]
    return _ok(ui_actions, resident=resident)


async def focus_room(admin_user: dict, args: dict) -> dict:
    room = args["room"]
    devices = await db.smart_devices.find({"room": room}, {"_id": 0}).to_list(50)
    if not devices:
        # Still navigate so the admin can see the room is genuinely empty -
        # that's a real, honest answer, not a failure to report.
        return _ok([_navigate("devices")], room=room, device_count=0)
    targets = [f"device:{d['device_id']}" for d in devices]
    ui_actions = [_navigate("devices"), _scroll(targets), _highlight(targets, f"Room {room}")]
    return _ok(ui_actions, room=room, device_count=len(devices))


async def focus_device(admin_user: dict, args: dict) -> dict:
    device = await db.smart_devices.find_one({"device_id": args["device_id"]}, {"_id": 0})
    if not device:
        return {"status": "not_found", "ui_actions": [], "detail": "No matching device found."}
    target = f"device:{device['device_id']}"
    ui_actions = [_navigate("devices"), _scroll([target]), _highlight([target], device.get("label"))]
    return _ok(ui_actions, device=device)


async def _resolve_target(target_type: str, target_id: str):
    if target_type == "resident":
        return await db.residents.find_one({"resident_id": target_id}, {"_id": 0})
    if target_type == "device":
        return await db.smart_devices.find_one({"device_id": target_id}, {"_id": 0})
    return None


async def highlight_admin_target(admin_user: dict, args: dict) -> dict:
    obj = await _resolve_target(args["target_type"], args["target_id"])
    if not obj:
        return {"status": "not_found", "ui_actions": [], "detail": "No matching item found."}
    target = f"{args['target_type']}:{args['target_id']}"
    label = obj.get("label") or obj.get("preferred_name") or obj.get("name")
    return _ok([_scroll([target]), _highlight([target], label)])


async def scroll_to_admin_target(admin_user: dict, args: dict) -> dict:
    obj = await _resolve_target(args["target_type"], args["target_id"])
    if not obj:
        return {"status": "not_found", "ui_actions": [], "detail": "No matching item found."}
    target = f"{args['target_type']}:{args['target_id']}"
    return _ok([_scroll([target])])


async def open_item(admin_user: dict, args: dict) -> dict:
    item_type, item_id = args["item_type"], args["item_id"]
    if item_type in ("resident", "device"):
        return await highlight_admin_target(admin_user, {"target_type": item_type, "target_id": item_id})
    return {"status": "not_available", "ui_actions": [], "detail": f"No detail view registered for '{item_type}' yet."}


async def close_item(admin_user: dict, args: dict) -> dict:
    # No modal/dialog state is currently driven by the admin assistant -
    # nothing to close yet. Honest no-op, not a fabricated success.
    return {"status": "not_available", "ui_actions": [], "detail": "Nothing is currently open to close."}


UI_TOOL_FUNCTIONS = {
    "navigate_admin_section": navigate_admin_section,
    "focus_resident": focus_resident,
    "focus_room": focus_room,
    "focus_device": focus_device,
    "highlight_admin_target": highlight_admin_target,
    "scroll_to_admin_target": scroll_to_admin_target,
    "open_item": open_item,
    "close_item": close_item,
}
