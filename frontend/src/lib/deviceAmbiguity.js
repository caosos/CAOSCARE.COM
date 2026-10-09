/**
 * One shared "which device?" guard for every Realtime device tool
 * (RQ-040, generalising RQ-038's light-only retry guard).
 *
 * When a room has more than one device of the kind a tool targets and
 * nothing the resident said or the model passed picks one, the tool
 * returns { ok:false, ambiguous:true, choices } and sends nothing. The
 * refusal is remembered per session + tool together with the resident
 * utterance it answered; the same utterance is refused locally (no
 * network) until a NEW utterance arrives, so the model cannot loop on it
 * (RQ-038 saw 16 refused light calls in 8 s).
 */
import { API } from "./api";

const refusals = new Map(); // `${session}|${tool}` -> { text, noun, choices }
const keyOf = (ctx, tool) => `${ctx?.session_id || "_"}|${tool}`;
const heardOf = (ctx) => (ctx?.last_user_text || "").trim();

export function resetDeviceAmbiguity() { refusals.clear(); }

export function ambiguousResult(noun, choices) {
  return {
    ok: false, ambiguous: true, choices,
    message: `this room has more than one ${noun} — did you mean the ${choices.join(" or the ")}? Ask the resident which one, then call again with device set to the exact choice.`,
  };
}

/** The remembered refusal for this utterance, or null (a new utterance clears the way). */
export function priorAmbiguity(ctx, tool) {
  const prior = refusals.get(keyOf(ctx, tool));
  return prior && prior.text === heardOf(ctx) ? ambiguousResult(prior.noun, prior.choices) : null;
}

export function recordAmbiguity(ctx, tool, noun, choices) {
  refusals.set(keyOf(ctx, tool), { text: heardOf(ctx), noun, choices });
  return ambiguousResult(noun, choices);
}

export function clearAmbiguity(ctx, tool) { refusals.delete(keyOf(ctx, tool)); }

export function shortLabel(d, room) {
  const label = String(d.label || d.device_id || "");
  return (room ? label.replace(`Room ${room} `, "") : label).toLowerCase();
}

/** Pick one of several devices by the model's `device` argument (exact label,
 *  short label or device_id), else by a unique first-word match in what the
 *  resident said. Returns null when it cannot tell. */
export function pickDevice(candidates, named, heard, room) {
  const want = String(named || "").trim().toLowerCase();
  if (want) {
    const hit = candidates.filter((d) => String(d.device_id || "").toLowerCase() === want || String(d.label || "").toLowerCase() === want || shortLabel(d, room) === want);
    if (hit.length === 1) return hit[0];
  }
  const lower = String(heard || "").toLowerCase();
  const matches = candidates.filter((d) => lower.includes(shortLabel(d, room).split(" ")[0]));
  return matches.length === 1 ? matches[0] : null;
}

/**
 * Look up the room's online devices of `kind` and resolve to one.
 * Returns { device } (device may be null when the room has none) or
 * { fail } with the structured ambiguity refusal.
 */
export async function findDeviceGuarded({ room, kind, noun, tool, args, ctx }) {
  const prior = priorAmbiguity(ctx, tool);
  if (prior) return { fail: prior };
  const r = await fetch(`${API}/devices/public/by-room/${encodeURIComponent(room)}`);
  const list = r.ok ? await r.json() : [];
  const matches = list.filter((d) => d.kind === kind && d.online !== false);
  if (matches.length <= 1) {
    clearAmbiguity(ctx, tool);
    return { device: matches[0] || null };
  }
  const chosen = pickDevice(matches, args?.device, heardOf(ctx), room);
  if (chosen) {
    clearAmbiguity(ctx, tool);
    return { device: chosen };
  }
  return { fail: recordAmbiguity(ctx, tool, noun, matches.map((d) => shortLabel(d, room))) };
}
