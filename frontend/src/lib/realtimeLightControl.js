/**
 * toggle_light's full implementation - split out of realtimeDeviceTools.js
 * (2026-09-05, real Matter light work) once brightness/color/color_temp
 * support pushed that file over the repo's 300-line cap. Same generic
 * device contract as every other tool there: speaks capability/action/
 * value, never a vendor entity_id or protocol detail - a real Matter bulb
 * and a future non-Matter light both go through the exact same path.
 */
import { API } from "./api";
import { priorAmbiguity, recordAmbiguity, clearAmbiguity, pickDevice, shortLabel, resetDeviceAmbiguity } from "./deviceAmbiguity";

// Color vocabulary shared both directions: naming a color for a command
// (toggle_light's `color` arg -> RGB the adapter sends to the real device)
// and describing a verified read-back RGB back in human terms
// (get_room_status / the resident screen, via realtimeDeviceTools.js's
// describeDevice). One table, not two, so the spoken vocabulary and the
// command vocabulary can never drift apart. Generic to any RGB light -
// not a Tapo-specific palette.
const NAMED_COLORS = {
  red: [255, 0, 0], orange: [255, 140, 0], yellow: [255, 220, 0],
  green: [0, 200, 0], blue: [0, 80, 255], purple: [160, 0, 220],
  pink: [255, 105, 180], white: [255, 255, 255],
};
export function nearestColorName(rgb) {
  if (!Array.isArray(rgb) || rgb.length !== 3) return null;
  let best = null, bestDist = Infinity;
  for (const [name, ref] of Object.entries(NAMED_COLORS)) {
    const d = ref.reduce((sum, c, i) => sum + (c - rgb[i]) ** 2, 0);
    if (d < bestDist) { bestDist = d; best = name; }
  }
  return best;
}
const COLOR_TEMP_KELVIN = { warm: 2700, neutral: 4000, cool: 6500 };
export function colorTempLabel(kelvin) {
  if (typeof kelvin !== "number") return null;
  return kelvin <= 3200 ? "warm white" : kelvin <= 5000 ? "neutral white" : "cool white";
}

// Rooms can hold more than one light (Room 214's desk + overhead bulbs):
// disambiguation and the no-retry-loop refusal are the shared guard in
// deviceAmbiguity.js (RQ-040), so every device tool behaves the same way.
const TOOL = "toggle_light";
export function resetLightAmbiguity() { resetDeviceAmbiguity(); }

// `postRoomCommand` is passed in from realtimeDeviceTools.js (the one
// place every tool posts device commands through) rather than duplicated
// here, so there is exactly one network call site to reason about.
export async function handleToggleLight(room, args, ctx, postRoomCommand) {
  const sessionId = ctx?.session_id;
  const heardNow = (ctx?.last_user_text || "").trim();
  const prior = priorAmbiguity(ctx, TOOL);
  if (prior) return prior;
  const hasAny = args.state || args.brightness != null || args.brightness_delta != null || args.color || args.color_temp;
  if (!hasAny) return { ok: false, message: "I didn't catch what you'd like me to change about the light." };

  const listR = await fetch(`${API}/devices/public/by-room/${encodeURIComponent(room)}`);
  const list = listR.ok ? await listR.json() : [];
  const lights = list.filter((d) => d.kind === "light" && d.online !== false);
  if (!lights.length) return { ok: false, message: "there's no light set up in this room yet." };

  const light = lights.length === 1 ? lights[0] : pickDevice(lights, args.device, heardNow, room);
  if (!light) return recordAmbiguity(ctx, TOOL, "light", lights.map((d) => shortLabel(d, room)));
  clearAmbiguity(ctx, TOOL);
  const deviceId = light.device_id;
  const caps = light.capabilities || [];
  // Only name the light in speech when there's more than one to tell
  // apart - "turned the light off" reads better than "turned the desk
  // light off" in the single-light case every other room still has.
  const name = lights.length > 1 ? `${shortLabel(light, room).split(" ")[0]} light` : "light";

  // SC-10: check every requested attribute against the light's declared
  // capabilities BEFORE anything is sent. One unsupported attribute refuses
  // the whole request and changes nothing - an off light asked to "go
  // green" stays off, and the result says plainly why (ok:false, so Aria
  // cannot imply success; the refusal is logged as this tool's result).
  const unsupported = [];
  if ((args.brightness != null || args.brightness_delta != null) && !caps.includes("brightness")) unsupported.push("brightness");
  if (args.color && !caps.includes("color")) unsupported.push("color");
  if (args.color_temp && !caps.includes("color_temp")) unsupported.push("color temperature");
  if (unsupported.length) {
    return { ok: false, unsupported, message: `this ${name} doesn't support ${unsupported.join(" or ")}, so I left it as it was.` };
  }

  // A color/brightness/color_temp request with no explicit state implies
  // turning it on ONLY if it isn't already on - asking "make it green"
  // about an off light plainly means "and turn it on", but asking it about
  // an already-on light shouldn't re-send a redundant power command (and
  // its own real-device round trip/receipt) on every single tweak.
  const currentlyOn = light.state?.power === "on";
  const state = args.state || (args.state == null && hasAny && !currentlyOn ? "on" : null);
  if (state) {
    const r = await postRoomCommand(room, "power", state, "light", sessionId, deviceId);
    if (!r.ok) return { ok: false, message: `couldn't reach the ${name} (${r.status}).` };
    if (state === "off") return { ok: true, message: `turned the ${name} off.` };
  }

  const done = [];
  if (args.brightness != null || args.brightness_delta != null) {
    const current = typeof light.state?.brightness === "number" ? light.state.brightness : 100;
    const target = args.brightness != null
      ? Math.max(1, Math.min(100, Math.round(args.brightness)))
      : Math.max(1, Math.min(100, current + Math.round(args.brightness_delta)));
    const r = await postRoomCommand(room, "brightness", target, "light", sessionId, deviceId);
    done.push(r.ok ? `brightness ${target} percent` : `couldn't set brightness (${r.status})`);
  }
  if (args.color) {
    const r = await postRoomCommand(room, "color", NAMED_COLORS[args.color], "light", sessionId, deviceId);
    done.push(r.ok ? args.color : `couldn't set the color (${r.status})`);
  }
  if (args.color_temp) {
    const r = await postRoomCommand(room, "color_temp", COLOR_TEMP_KELVIN[args.color_temp], "light", sessionId, deviceId);
    done.push(r.ok ? `${args.color_temp} white` : `couldn't set the color temperature (${r.status})`);
  }
  if (!done.length) return { ok: true, message: `turned the ${name} on.` };
  return { ok: true, message: `set the ${name} to ${done.join(", ")}.` };
}
