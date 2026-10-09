/**
 * Blinds, TV channel and TV volume-step tools (RQ-021). Same rules as the
 * light/TV tools in realtimeDeviceTools.js:
 *  - nothing is sent unless the resident's own words (ctx.last_user_text)
 *    support the action - a garbled turn that the model turns into a tool
 *    call changes nothing (2026-08-30 "Hello Lab" -> volume 11 incident);
 *  - one command path: POST /devices/public/room/{room}/command, which
 *    validates against the device's own capabilities;
 *  - the spoken result comes from the state the backend read back, never
 *    from what was requested, and says "simulated" when the backend says so.
 */
import { findDeviceGuarded } from "./deviceAmbiguity";

// A volume request has many valid forms, so this only requires a volume cue.
export const VOLUME_PHRASES = /\b(volume|loud(er|ness)?|quiet(er)?|turn\s*(it|the\s*(tv|sound))?\s*(up|down)|mute|unmute)\b/i;
const BLINDS_PHRASES = /\b(blinds?|shades?|curtains?|drapes?)\b/i;
const CHANNEL_WORD = /\bchannel\b/i;

const ONES = { zero: 0, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10,
  eleven: 11, twelve: 12, thirteen: 13, fourteen: 14, fifteen: 15, sixteen: 16, seventeen: 17, eighteen: 18, nineteen: 19 };
const TENS = { twenty: 20, thirty: 30, forty: 40, fifty: 50, sixty: 60, seventy: 70, eighty: 80, ninety: 90 };

// Numbers the resident said, as digits ("channel 11") or words ("eleven",
// "twenty one") - transcripts use either.
export function numbersIn(text) {
  const out = new Set();
  const lower = String(text || "").toLowerCase();
  for (const m of lower.matchAll(/\d+/g)) out.add(Number(m[0]));
  const words = lower.split(/[^a-z]+/).filter(Boolean);
  for (let i = 0; i < words.length; i++) {
    if (words[i] in TENS) {
      const next = ONES[words[i + 1]];
      out.add(TENS[words[i]] + (next > 0 && next < 10 ? next : 0));
    } else if (words[i] in ONES) {
      out.add(ONES[words[i]]);
    }
  }
  return out;
}

const heardText = (ctx) => (ctx?.last_user_text || "").trim();
const labelOf = (data) => (data?.simulated ? " (simulated device)" : "");

async function sendCommand(deps, room, action, value, kind, ctx, device) {
  const r = await deps.postRoomCommand(room, action, value, kind, ctx?.session_id, device.device_id);
  if (!r.ok) {
    const detail = await r.json().then((j) => j?.detail).catch(() => null);
    return { error: typeof detail === "string" ? detail : `status ${r.status}` };
  }
  const data = await r.json().catch(() => null);
  // No state in the answer means nothing was read back - never claim success.
  if (!data || typeof data.state !== "object" || data.state === null) return { error: "no confirmation came back" };
  return { data };
}

async function findDevice(tool, args, ctx, room, kind, noun) {
  const f = await findDeviceGuarded({ room, kind, noun, tool, args, ctx });
  if (f.fail) return { fail: f.fail };
  if (!f.device) return { fail: { ok: false, message: `there's no ${noun} set up in this room.` } };
  return { device: f.device };
}

async function setBlinds({ args, ctx, deps }) {
  const room = ctx?.room;
  if (!room) return { ok: false, message: "no room context — I can't reach the blinds here." };
  if (!BLINDS_PHRASES.test(heardText(ctx))) {
    return { ok: false, message: "Just to make sure — did you want me to change the blinds?" };
  }
  let target;
  if (args.action === "open") target = 100;
  else if (args.action === "close") target = 0;
  else if (typeof args.percent === "number") target = Math.max(0, Math.min(100, Math.round(args.percent)));
  else return { ok: false, message: "how far open would you like the blinds?" };
  const found = await findDevice("set_blinds", args, ctx, room, "blinds", "blinds");
  if (found.fail) return found.fail;
  if (!(found.device.capabilities || []).includes("position")) {
    return { ok: false, message: "these blinds can't be moved from here." };
  }
  const res = await sendCommand(deps, room, "position", target, "blinds", ctx, found.device);
  if (res.error) return { ok: false, message: `the blinds didn't change (${res.error}).` };
  const pos = res.data.state.position;
  const words = pos <= 0 ? "closed" : pos >= 100 ? "fully open" : `${pos}% open`;
  return { ok: true, message: `the blinds are now ${words}${labelOf(res.data)}.` };
}

async function tvDevice(tool, args, ctx, capability) {
  const room = ctx?.room;
  if (!room) return { fail: { ok: false, message: "no room context — I can't reach the TV here." } };
  const found = await findDevice(tool, args, ctx, room, "tv", "TV");
  if (found.fail) return found;
  if (!(found.device.capabilities || []).includes(capability)) {
    return { fail: { ok: false, message: `this TV doesn't have ${capability} control.` } };
  }
  return { room, device: found.device };
}

async function setTvChannel({ args, ctx, deps }) {
  const heard = heardText(ctx);
  const channel = Math.round(Number(args.channel));
  if (!heard || !CHANNEL_WORD.test(heard) || !numbersIn(heard).has(channel)) {
    return { ok: false, message: "Which channel would you like?" };
  }
  const tv = await tvDevice("set_tv_channel", args, ctx, "channel");
  if (tv.fail) return tv.fail;
  let poweredOn = false;
  if (tv.device.state?.power !== "on") {
    const p = await sendCommand(deps, tv.room, "power", "on", "tv", ctx, tv.device);
    if (p.error) return { ok: false, message: `couldn't turn the TV on (${p.error}).` };
    poweredOn = true;
  }
  const res = await sendCommand(deps, tv.room, "channel", channel, "tv", ctx, tv.device);
  if (res.error) return { ok: false, message: `the channel didn't change (${res.error}).` };
  return { ok: true, message: `${poweredOn ? "turned the TV on and " : ""}the TV is on channel ${res.data.state.channel}${labelOf(res.data)}.` };
}

async function adjustTvVolume({ args, ctx, deps }) {
  if (!VOLUME_PHRASES.test(heardText(ctx))) {
    return { ok: false, message: "Just to make sure — did you want the TV volume changed?" };
  }
  const tv = await tvDevice("adjust_tv_volume", args, ctx, "volume");
  if (tv.fail) return tv.fail;
  if (tv.device.state?.power !== "on") return { ok: false, message: "the TV is off right now, so there's no volume to change." };
  const current = typeof tv.device.state?.volume === "number" ? tv.device.state.volume : 20;
  const step = Math.max(1, Math.min(50, Math.round(Number(args.amount) || 10)));
  const next = Math.max(0, Math.min(100, current + (args.direction === "down" ? -step : step)));
  const res = await sendCommand(deps, tv.room, "volume", next, "tv", ctx, tv.device);
  if (res.error) return { ok: false, message: `the volume didn't change (${res.error}).` };
  return { ok: true, message: `the TV volume is now ${res.data.state.volume}${labelOf(res.data)}.` };
}

const HANDLERS = { set_blinds: setBlinds, set_tv_channel: setTvChannel, adjust_tv_volume: adjustTvVolume };
export const ROOM_CONTROL_TOOLS = new Set(Object.keys(HANDLERS));

// deps = { postRoomCommand } from realtimeDeviceTools.js
export function executeRoomControlTool(name, args, ctx, deps) {
  const h = HANDLERS[name];
  return h ? h({ args: args || {}, ctx, deps }) : undefined;
}
