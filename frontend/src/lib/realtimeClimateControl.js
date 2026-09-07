/**
 * adjust_room_temperature's full implementation - split out the same way
 * realtimeLightControl.js was (2026-09-05, real Midea AC work), and for
 * the same reason: a room can genuinely have more than one climate-capable
 * device (Room 214 has both a mock thermostat and the real AC), so this
 * needs real disambiguation, not just "assume there's one."
 */
import { API } from "./api";

const AC_WORDS = /\b(ac|a\/?c|air\s*condition(er|ing)?|cooling)\b/i;
const THERMOSTAT_WORDS = /\b(thermostat|heater?|heat(ing)?)\b/i;

function pickClimateDevice(candidates, heard) {
  if (candidates.length <= 1) return { device: candidates[0], ambiguous: false };
  const wantsAc = AC_WORDS.test(heard);
  const wantsThermostat = THERMOSTAT_WORDS.test(heard);
  if (wantsAc && !wantsThermostat) {
    const d = candidates.find((c) => c.kind === "ac");
    if (d) return { device: d, ambiguous: false };
  }
  if (wantsThermostat && !wantsAc) {
    const d = candidates.find((c) => c.kind === "thermostat");
    if (d) return { device: d, ambiguous: false };
  }
  return { device: null, ambiguous: true };
}

export async function handleAdjustRoomTemperature(room, args, ctx, postRoomCommand) {
  const sessionId = ctx?.session_id;
  const hasAny = args.state || args.mode || args.target_f != null || args.delta_f != null;
  if (!hasAny) return { ok: false, message: "I didn't catch what you'd like me to change." };

  const listR = await fetch(`${API}/devices/public/by-room/${encodeURIComponent(room)}`);
  const list = listR.ok ? await listR.json() : [];
  const candidates = list.filter((d) => (d.capabilities || []).includes("temperature") && d.online !== false);
  if (!candidates.length) return { ok: false, message: "there's no climate control set up in this room yet." };

  const { device, ambiguous } = pickClimateDevice(candidates, (ctx?.last_user_text || "").trim());
  if (ambiguous) {
    return { ok: false, message: "this room has more than one climate control — did you mean the air conditioner or the thermostat?" };
  }
  const kind = device.kind;
  const caps = device.capabilities || [];
  const currentlyOn = device.state?.power === "on";

  const state = args.state || (args.state == null && hasAny && !currentlyOn ? "on" : null);
  if (state) {
    const r = await postRoomCommand(room, "power", state, kind, sessionId);
    if (!r.ok) return { ok: false, message: `couldn't reach the ${kind === "ac" ? "AC" : "thermostat"} (${r.status}). I'll let the nurse know.` };
    if (state === "off") return { ok: true, message: `turned the ${kind === "ac" ? "AC" : "thermostat"} off.` };
  }

  const done = [];
  if (args.mode) {
    if (!caps.includes("hvac_mode")) {
      done.push("this device doesn't support changing modes");
    } else {
      const r = await postRoomCommand(room, "hvac_mode", args.mode, kind, sessionId);
      done.push(r.ok ? `set to ${args.mode}` : (await r.json().catch(() => null))?.detail || `couldn't set the mode (${r.status})`);
    }
  }
  if (args.target_f != null || args.delta_f != null) {
    const current = typeof device.state?.temperature === "number" ? device.state.temperature : 72;
    const target = args.target_f != null
      ? Math.max(60, Math.min(85, Math.round(args.target_f)))
      : Math.max(60, Math.min(85, Math.round(current + args.delta_f)));
    const r = await postRoomCommand(room, "temperature", target, kind, sessionId);
    done.push(r.ok ? `${target} degrees` : `couldn't set the temperature (${r.status})`);
  }
  if (!done.length) return { ok: true, message: `turned the ${kind === "ac" ? "AC" : "thermostat"} on.` };
  return { ok: true, message: `set the ${kind === "ac" ? "AC" : "thermostat"} to ${done.join(", ")}.` };
}
