"""Server-side room device tools: lights, TV, thermostat, room status.

The one server executor for resident device tools (the Voice PE bridge now;
the room page can move onto it later). Same behaviour as the room page's
browser tools (realtimeLightControl.js, realtimeDeviceTools.js,
realtimeRoomControls.js, deviceAmbiguity.js):
- every command goes through devices.execute_room_command (room-scoped,
  capability-checked, receipted, device_commands logged);
- nothing is sent unless the resident's words support it (device_grounding);
- a room with several devices of a kind asks "which one?" and refuses to
  repeat the same call until the resident answers;
- the spoken result follows the device's read-back: a one-way (infrared)
  TV's command is "sent", never "done".
ctx: room, session_id, last_user_text (all server-resolved).
"""
from typing import Optional

from fastapi import HTTPException

from deps import db
from models import DeviceCommandInput
from routes.device_grounding import (CHANNEL_WORD, VOLUME_PHRASES, numbers_in,
                                     power_direction_mismatch, tv_power_grounded)

NAMED_COLORS = {"red": [255, 0, 0], "orange": [255, 140, 0], "yellow": [255, 220, 0],
                "green": [0, 200, 0], "blue": [0, 80, 255], "purple": [160, 0, 220],
                "pink": [255, 105, 180], "white": [255, 255, 255]}
COLOR_TEMP_KELVIN = {"warm": 2700, "neutral": 4000, "cool": 6500}

ROOM_DEVICE_TOOLS = ("toggle_light", "toggle_tv", "adjust_tv_volume", "set_tv_channel",
                     "adjust_room_temperature", "get_room_status")

# session|tool -> (utterance, noun, choices). Per process: a refused
# ambiguous call is not re-sent for the same utterance (RQ-038/RQ-040).
_refusals: dict = {}


def _heard(ctx) -> str:
    return (ctx.get("last_user_text") or "").strip()


def _key(ctx, tool) -> str:
    return f"{ctx.get('session_id') or '_'}|{tool}"


def _ambiguous(noun, choices) -> dict:
    return {"ok": False, "ambiguous": True, "choices": choices,
            "message": f"this room has more than one {noun} - did you mean the {' or the '.join(choices)}? "
                       "Ask the resident which one, then call again with device set to the exact choice."}


def short_label(d: dict, room: str) -> str:
    label = str(d.get("label") or d.get("device_id") or "")
    return (label.replace(f"Room {room} ", "") if room else label).lower()


def pick_device(candidates: list, named: Optional[str], heard: str, room: str) -> Optional[dict]:
    want = (named or "").strip().lower()
    if want:
        hit = [d for d in candidates if want in (str(d.get("device_id", "")).lower(),
                                                 str(d.get("label", "")).lower(), short_label(d, room))]
        if len(hit) == 1:
            return hit[0]
    lower = (heard or "").lower()
    hits = [d for d in candidates if short_label(d, room).split(" ")[0] in lower]
    return hits[0] if len(hits) == 1 else None


async def find_device(ctx, tool, kind, noun, named=None) -> dict:
    """{"device": dev|None} or {"fail": refusal}."""
    room, k = ctx["room"], _key(ctx, tool)
    prior = _refusals.get(k)
    if prior and prior[0] == _heard(ctx):
        return {"fail": _ambiguous(prior[1], prior[2])}
    devices = await db.smart_devices.find({"room": room, "kind": kind, "online": {"$ne": False}},
                                          {"_id": 0}).sort("label", 1).to_list(20)
    chosen = devices[0] if len(devices) == 1 else pick_device(devices, named, _heard(ctx), room) if devices else None
    if len(devices) > 1 and not chosen:
        choices = [short_label(d, room) for d in devices]
        _refusals[k] = (_heard(ctx), noun, choices)
        return {"fail": _ambiguous(noun, choices)}
    _refusals.pop(k, None)
    return {"device": chosen, "count": len(devices)}


async def send(ctx, dev: dict, action: str, value, kind: str) -> dict:
    """{"result": adapter result} or {"error": detail}."""
    from routes.devices import execute_room_command
    try:
        r = await execute_room_command(ctx["room"], DeviceCommandInput(
            action=action, value=value, kind=kind, session_id=ctx.get("session_id"), device_id=dev["device_id"]))
    except HTTPException as e:
        return {"error": e.detail if isinstance(e.detail, str) else str(e.detail)}
    return {"result": r}


def _done(res: dict, did: str, sent: str) -> str:
    return did if (res.get("result") or {}).get("verified") else sent


async def toggle_light(args, ctx) -> dict:
    tool = "toggle_light"
    pending = _key(ctx, tool) in _refusals
    if not (args.get("state") or args.get("brightness") is not None or args.get("brightness_delta") is not None
            or args.get("color") or args.get("color_temp")):
        return {"ok": False, "message": "I didn't catch what you'd like me to change about the light."}
    mismatch = power_direction_mismatch(args.get("state"), _heard(ctx), args.get("device") or "light", pending)
    if mismatch:
        return {"ok": False, "message": mismatch}
    found = await find_device(ctx, tool, "light", "light", args.get("device"))
    if "fail" in found:
        return found["fail"]
    light = found["device"]
    if not light:
        return {"ok": False, "message": "there's no light set up in this room yet."}
    caps = light.get("capabilities") or []
    name = f"{short_label(light, ctx['room']).split(' ')[0]} light" if found["count"] > 1 else "light"
    unsupported = [n for n, want, cap in (
        ("brightness", args.get("brightness") is not None or args.get("brightness_delta") is not None, "brightness"),
        ("color", args.get("color"), "color"), ("color temperature", args.get("color_temp"), "color_temp"))
        if want and cap not in caps]
    if unsupported:
        return {"ok": False, "message": f"this {name} doesn't support {' or '.join(unsupported)}, so I left it as it was."}
    is_on = (light.get("state") or {}).get("power") == "on"
    state = args.get("state") or (None if is_on else "on")
    if state:
        res = await send(ctx, light, "power", state, "light")
        if "error" in res:
            return {"ok": False, "message": f"couldn't reach the {name} ({res['error']})."}
        if state == "off":
            return {"ok": True, "message": _done(res, f"turned the {name} off.",
                                                 f"sent off to the {name}; it did not confirm.")}
    done = []
    if args.get("brightness") is not None or args.get("brightness_delta") is not None:
        cur = (light.get("state") or {}).get("brightness")
        cur = cur if isinstance(cur, (int, float)) else 100
        target = args["brightness"] if args.get("brightness") is not None else cur + int(args["brightness_delta"])
        target = max(1, min(100, round(target)))
        res = await send(ctx, light, "brightness", target, "light")
        done.append(f"brightness {target} percent" if "result" in res else f"couldn't set brightness ({res['error']})")
    if args.get("color") in NAMED_COLORS:
        res = await send(ctx, light, "color", NAMED_COLORS[args["color"]], "light")
        done.append(args["color"] if "result" in res else f"couldn't set the color ({res['error']})")
    if args.get("color_temp") in COLOR_TEMP_KELVIN:
        res = await send(ctx, light, "color_temp", COLOR_TEMP_KELVIN[args["color_temp"]], "light")
        done.append(f"{args['color_temp']} white" if "result" in res else f"couldn't set the color temperature ({res['error']})")
    if not done:
        return {"ok": True, "message": f"turned the {name} on."}
    return {"ok": True, "message": f"set the {name} to {', '.join(done)}."}


async def _tv(ctx, tool, args, capability=None) -> dict:
    found = await find_device(ctx, tool, "tv", "TV", args.get("device"))
    if "fail" in found:
        return found
    if not found["device"]:
        return {"fail": {"ok": False, "message": "there's no TV set up in this room yet."}}
    if capability and capability not in (found["device"].get("capabilities") or []):
        return {"fail": {"ok": False, "message": f"this TV doesn't have {capability} control."}}
    return found


async def toggle_tv(args, ctx) -> dict:
    heard = _heard(ctx)
    power = tv_power_grounded(heard, args.get("state"))
    volume = isinstance(args.get("volume"), (int, float)) and bool(VOLUME_PHRASES.search(heard))
    if not power and not volume:
        return {"ok": False, "message": "I didn't hear a clear TV power or volume request, so I didn't change the TV."}
    tv = await _tv(ctx, "toggle_tv", args)
    if "fail" in tv:
        return tv["fail"]
    msgs = []
    if power:
        res = await send(ctx, tv["device"], "power", args["state"], "tv")
        if "error" in res:
            return {"ok": False, "message": f"couldn't reach the TV ({res['error']})."}
        msgs.append(_done(res, f"turned the TV {args['state']}",
                          f"sent the TV {args['state']} command; this TV does not confirm changes"))
    if volume:
        level = max(0, min(100, int(args["volume"])))
        res = await send(ctx, tv["device"], "volume", level, "tv")
        if "error" in res:
            return {"ok": False, "message": f"couldn't reach the TV volume ({res['error']})."}
        msgs.append(_done(res, f"the volume is at {level}",
                          f"sent volume {level}; this TV does not report its level"))
    return {"ok": True, "message": " and ".join(msgs) + "."}


async def adjust_tv_volume(args, ctx) -> dict:
    if not VOLUME_PHRASES.search(_heard(ctx)):
        return {"ok": False, "message": "Just to make sure - did you want the TV volume changed?"}
    tv = await _tv(ctx, "adjust_tv_volume", args, "volume")
    if "fail" in tv:
        return tv["fail"]
    dev, down = tv["device"], args.get("direction") == "down"
    if "volume_step" in (dev.get("capabilities") or []):
        presses = max(1, min(20, int(args.get("amount") or 3)))
        res = await send(ctx, dev, "volume_step", -presses if down else presses, "tv")
        if "error" in res:
            return {"ok": False, "message": f"the volume didn't change ({res['error']})."}
        return {"ok": True, "message": f"sent {presses} volume-{'down' if down else 'up'} presses to the TV. "
                "This TV can't report its volume, so ask if that's better - don't name a level."}
    st = dev.get("state") or {}
    if st.get("power") != "on":
        return {"ok": False, "message": "the TV is off right now, so there's no volume to change."}
    cur = st.get("volume") if isinstance(st.get("volume"), (int, float)) else 20
    step = max(1, min(50, int(args.get("amount") or 10)))
    res = await send(ctx, dev, "volume", max(0, min(100, cur + (-step if down else step))), "tv")
    if "error" in res:
        return {"ok": False, "message": f"the volume didn't change ({res['error']})."}
    return {"ok": True, "message": f"the TV volume is now {res['result'].get('state', {}).get('volume')}."}


async def set_tv_channel(args, ctx) -> dict:
    heard = _heard(ctx)
    try:
        channel = round(float(args.get("channel")))
    except (TypeError, ValueError):
        channel = None
    if channel is None or not CHANNEL_WORD.search(heard) or channel not in numbers_in(heard):
        return {"ok": False, "message": "Which channel would you like?"}
    tv = await _tv(ctx, "set_tv_channel", args, "channel")
    if "fail" in tv:
        return tv["fail"]
    res = await send(ctx, tv["device"], "channel", channel, "tv")
    if "error" in res:
        return {"ok": False, "message": f"the channel didn't change ({res['error']})."}
    return {"ok": True, "message": _done(res, f"the TV is on channel {channel}.",
                                         f"sent channel {channel}; this TV does not confirm changes.")}


async def adjust_room_temperature(args, ctx) -> dict:
    found = await find_device(ctx, "adjust_room_temperature", "thermostat", "thermostat", args.get("device"))
    if "fail" in found:
        return found["fail"]
    dev = found["device"]
    if not dev:
        return {"ok": False, "message": "there's no climate control set up in this room yet."}
    if args.get("target_f") is not None:
        target = float(args["target_f"])
    elif args.get("delta_f") is not None and isinstance((dev.get("state") or {}).get("temperature"), (int, float)):
        target = dev["state"]["temperature"] + float(args["delta_f"])
    else:
        return {"ok": False, "message": "what temperature would you like?"}
    target = max(60, min(85, round(target)))
    res = await send(ctx, dev, "temperature", target, "thermostat")
    if "error" in res:
        return {"ok": False, "message": f"couldn't reach the climate control ({res['error']})."}
    return {"ok": True, "message": _done(res, f"set the room to {target} degrees.",
                                         f"sent {target} degrees; it did not confirm.")}


async def get_room_status(args, ctx) -> dict:
    devices = await db.smart_devices.find({"room": ctx["room"]}, {"_id": 0}).sort("label", 1).to_list(50)
    parts = []
    for d in devices:
        st, caps, name = d.get("state") or {}, d.get("capabilities") or [], short_label(d, ctx["room"])
        if d.get("online") is False:
            parts.append(f"the {name} is offline")
        elif "power" in caps and d.get("protocol") != "ir_blaster":
            parts.append(f"the {name} is {'on' if st.get('power') == 'on' else 'off'}")
    return {"ok": True, "message": "; ".join(parts) + "." if parts else "no device readings in this room."}


_HANDLERS = {"toggle_light": toggle_light, "toggle_tv": toggle_tv, "adjust_tv_volume": adjust_tv_volume,
             "set_tv_channel": set_tv_channel, "adjust_room_temperature": adjust_room_temperature,
             "get_room_status": get_room_status}


async def run_room_device_tool(name: str, args: dict, ctx: dict) -> dict:
    if not ctx.get("room"):
        return {"ok": False, "message": "no room context - I can't reach the room devices here."}
    return await _HANDLERS[name](args or {}, ctx)
