/**
 * Device/environment/profile tool dispatch for the Realtime voice hook -
 * split out of useRealtimeVoice.js (2026-08-22) to keep that file from
 * growing further; same dispatch contract as realtimeOperationsTools.js's
 * executeOperationsTool(): returns a result object for names it handles.
 *
 * update_preferred_name is the one "authoritative mutation" tool live here
 * (durable resident-profile change) - it refuses to save when the calling
 * turn was flagged `turn_suspect` (the resident's speech onset overlapped
 * Aria's own audio, per useRealtimeVoice.js's echo/VAD-overlap tracking),
 * asking the resident to repeat themselves instead of trusting a possibly
 * phantom transcript. A false transcript must never silently become a
 * durable profile fact.
 */
import { API } from "./api";
import { nearestColorName, colorTempLabel, handleToggleLight } from "./realtimeLightControl";

// IMPORTANT: the backend `/devices/.../command` endpoint validates `action`
// against a strict enum (power | brightness | temperature | fan_speed |
// volume | channel | color | color_temp | position). The AI tools speak in
// human terms (state="on", target_f=72) so this layer translates between
// them. Mismatch = HTTP 422 = silent failure where CAOS promises an action
// that never ran.
async function postRoomCommand(room, action, value, kind, sessionId) {
  const r = await fetch(`${API}/devices/public/room/${encodeURIComponent(room)}/command`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, value, kind, session_id: sessionId || null }),
  });
  return r;
}

// Real, if reversible, room-state changes - gated the same way as staff
// requests so a noise-hallucinated turn can't move them either.
const CONSEQUENTIAL_DEVICE_TOOLS = new Set(["adjust_room_temperature", "toggle_light", "toggle_tv", "set_timer", "set_tv_input"]);

// 2026-08-30 (real live incident): mark_resting fired on "No, I can't." -
// a resident PROTESTING being left alone - and end_call fired on "It's
// gonna find me.", ending the whole session. Neither tool had any
// grounding requirement; the model verbally said one thing ("I'll give
// you some space to rest") with no tool call, then invoked the real tool
// one turn later against an utterance that doesn't support it. Same
// class of gap as update_preferred_name's guard above - the tool must be
// traceable to the resident's own words matching a real dismissal/ending
// phrase, not fire on an ambiguous or negatively-phrased turn.
const RESTING_PHRASES = /\b(be quiet|quiet down|let me rest|resting|give me\s*(some\s*)?space|don'?t talk|going to sleep|i'?m\s*(going to |gonna\s*)?sleep|take a nap|napping|i'?m tired|leave me alone|need\s*(some\s*)?(space|quiet))\b/i;
const ENDING_PHRASES = /\b(end the call|end (this |our )?conversation|hang up|good\s*bye|that'?s all( for now)?|that'?ll be all( for now)?|i'?m done|don'?t need you|go away)\b/i;

// 2026-08-30 (real live incident): "Hello Lab" (a garbled, nonsense
// transcript) led the model to call toggle_tv(volume=11) - the 11 wasn't
// grounded in the saved transcript text at all, most likely the model
// reacting to raw audio it heard as "channel 11" and substituting the
// only numeric TV control it actually has. Unlike RESTING_PHRASES/
// ENDING_PHRASES this isn't a fixed vocabulary - a resident can request
// any volume level in many ways - so this only requires the word "volume"
// (or an unambiguous loud/quiet/mute cue) to appear, not a specific phrase.
const VOLUME_PHRASES = /\b(volume|loud(er|ness)?|quiet(er)?|turn\s*(it|the\s*(tv|sound))?\s*(up|down)|mute|unmute)\b/i;

// One human-readable sentence per device, driven entirely by that device's
// OWN declared capabilities/state - not a hardcoded thermostat/TV special
// case - so a light, fan, or blinds device registered later is described
// correctly without a code change here. Shared logic for get_room_status
// (spoken) - the resident-facing device panel builds its own visual cards
// from the same raw device list, not this sentence.
export function describeDevice(d) {
  const s = d.state || {};
  const caps = d.capabilities || [];
  const name = d.room ? d.label.replace(`Room ${d.room} `, "") : d.label;
  if (d.online === false) return `the ${name} is offline`;
  const bits = [];
  if (caps.includes("power")) bits.push(s.power === "on" ? "on" : "off");
  if (caps.includes("temperature") && typeof s.temperature === "number") bits.push(`set to ${s.temperature} degrees`);
  if (caps.includes("input") && s.input) bits.push(`on ${s.input}`);
  if (caps.includes("volume") && typeof s.volume === "number" && s.power === "on") bits.push(`volume ${s.volume}`);
  if (caps.includes("brightness") && typeof s.brightness === "number" && s.power === "on") bits.push(`brightness ${s.brightness}`);
  if (caps.includes("color") && s.color && s.power === "on") {
    const name = nearestColorName(s.color);
    if (name) bits.push(name);
  }
  if (caps.includes("color_temp") && s.color_temp && s.power === "on") {
    const label = colorTempLabel(s.color_temp);
    if (label) bits.push(label);
  }
  if (caps.includes("fan_speed") && s.fan_speed != null) bits.push(`fan speed ${s.fan_speed}`);
  if (caps.includes("position") && s.position != null) bits.push(`position ${s.position}`);
  if (!bits.length) return null;
  return `the ${name} is ${bits.join(", ")}`;
}

// 2026-08-23: "echo_like" (short, resembles Aria's own speech) genuinely
// suggests mishearing - ask to repeat. Other suspect reasons (a short but
// non-echoing fragment) are less about mishearing and more about wanting
// a quick check before acting - phrased as confirmation, not "did I mishear".
function suspectMessage(ctx) {
  return ctx?.turn_suspect_reason === "echo_like"
    ? "I want to make sure I heard that right — could you say that again?"
    : "Just to double-check — is that what you'd like me to do?";
}

export async function executeDeviceTool({ name, args, ctx }) {
  const room = ctx?.room;
  const residentId = ctx?.resident_id;
  const kioskId = ctx?.kiosk_id;

  if (CONSEQUENTIAL_DEVICE_TOOLS.has(name) && ctx?.turn_suspect) {
    return { ok: false, message: suspectMessage(ctx) };
  }

  if (name === "get_room_status") {
    if (!room) return { ok: false, message: "no room context — I can't check the room devices here." };
    const r = await fetch(`${API}/devices/public/by-room/${encodeURIComponent(room)}`);
    if (!r.ok) return { ok: false, message: `couldn't reach the room devices (${r.status}).` };
    const list = await r.json();
    if (!list.length) return { ok: true, message: "there's nothing to read yet — no devices are set up in this room." };
    const parts = list.map(describeDevice).filter(Boolean);
    return { ok: true, message: parts.length ? parts.join("; ") + "." : "I don't have a reading for that yet." };
  }
  if (name === "adjust_room_temperature") {
    if (!room) return { ok: false, message: "no room context — I can't reach the climate control here." };
    const targetF = Math.max(60, Math.min(85, Number(args.target_f) || 72));
    const r = await postRoomCommand(room, "temperature", targetF, "thermostat");
    if (!r.ok) return { ok: false, message: `couldn't reach the AC (${r.status}). I'll let the nurse know.` };
    return { ok: true, message: `set the room to ${targetF} degrees.` };
  }
  if (name === "toggle_light") {
    if (!room) return { ok: false, message: "no room context — I can't reach the lights here." };
    return handleToggleLight(room, args, ctx, postRoomCommand);
  }
  if (name === "toggle_tv") {
    if (!room) return { ok: false, message: "no room context — I can't reach the TV here." };
    const r = await postRoomCommand(room, "power", args.state, "tv");
    if (!r.ok) return { ok: false, message: `couldn't reach the TV (${r.status}).` };
    // Structural grounding (2026-08-30) - see VOLUME_PHRASES above. A
    // volume change is a real, audible, potentially uncomfortable action -
    // don't apply one the resident's own words don't actually support,
    // even if the model supplied a number.
    const heard = (ctx?.last_user_text || "").trim();
    const volumeGrounded = args.state === "on" && typeof args.volume === "number" && VOLUME_PHRASES.test(heard);
    if (volumeGrounded) {
      await postRoomCommand(room, "volume", Math.max(0, Math.min(100, args.volume)), "tv");
    }
    return { ok: true, message: `turned the TV ${args.state}${volumeGrounded ? ` at volume ${args.volume}` : ""}.` };
  }
  if (name === "set_tv_input") {
    if (!room) return { ok: false, message: "no room context — I can't reach the TV here." };
    // Verify the device actually declares this input before calling -
    // per the tool's own instruction, a device that doesn't support it
    // should get an honest "not available", not a failed/ignored command.
    const listR = await fetch(`${API}/devices/public/by-room/${encodeURIComponent(room)}`);
    const list = listR.ok ? await listR.json() : [];
    const tv = list.find((d) => d.kind === "tv");
    if (!tv || !(tv.capabilities || []).includes("input")) {
      return { ok: false, message: "this TV doesn't support switching inputs." };
    }
    if (!(tv.inputs || []).some((i) => i.toLowerCase() === String(args.input).toLowerCase())) {
      return { ok: false, message: `this TV doesn't have a "${args.input}" input — it has: ${(tv.inputs || []).join(", ") || "none listed"}.` };
    }
    const r = await postRoomCommand(room, "input", args.input, "tv");
    if (!r.ok) return { ok: false, message: `couldn't switch the input (${r.status}).` };
    return { ok: true, message: `switched the TV to ${args.input}.` };
  }
  if (name === "call_for_help") {
    const r = await fetch(`${API}/alerts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kiosk_id: kioskId || null,
        resident_id: residentId || null,
        severity: args.severity === "emergency" ? "emergency" : "assist",
        message: args.reason || "AI-initiated call for help during conversation",
        triggered_by: "ai_triage",
      }),
    });
    if (!r.ok) return { ok: false, message: `I tried to call a nurse but the call didn't go through (${r.status}). Please press the red button.` };
    return { ok: true, message: "a nurse has been paged. I'm right here with you." };
  }
  if (name === "mark_resting") {
    // Structural grounding (2026-08-30) - see RESTING_PHRASES above. No
    // backend side-effect otherwise; the function existing (once granted)
    // tells the model to fall silent, and useRealtimeVoice.js disables
    // server auto-response for real.
    const heard = (ctx?.last_user_text || "").trim();
    if (!heard || !RESTING_PHRASES.test(heard)) {
      return { ok: false, message: "Just to make sure — would you like me to go quiet for a bit?" };
    }
    return { ok: true, message: "going quiet now. I'll be right here when you need me." };
  }
  if (name === "get_current_time") {
    const tz = ctx?.facility_tz || "America/New_York";
    const label = ctx?.facility_label || "the facility";
    try {
      const d = new Date();
      const fmt = new Intl.DateTimeFormat("en-US", {
        timeZone: tz,
        weekday: "long", month: "long", day: "numeric", year: "numeric",
        hour: "numeric", minute: "2-digit",
      });
      return { ok: true, message: `it's ${fmt.format(d)} at ${label}.` };
    } catch {
      return { ok: true, message: `it's ${new Date().toLocaleString()}.` };
    }
  }
  if (name === "get_weather") {
    const qs = args.location ? `?label=${encodeURIComponent(args.location)}` : "";
    const r = await fetch(`${API}/weather/current${qs}`);
    if (!r.ok) return { ok: false, message: `couldn't reach the weather service (${r.status}).` };
    const w = await r.json();
    return { ok: true, message: w.narrative || `${w.temperature_f}° and ${w.condition}.` };
  }
  if (name === "research_topic") {
    const r = await fetch(`${API}/research`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: args.question || "" }),
    });
    if (!r.ok) return { ok: false, message: `couldn't reach the research service (${r.status}).` };
    const j = await r.json();
    return { ok: true, message: j.answer || "I didn't find anything useful on that.", source: j.source, citations: j.citations || [] };
  }
  if (name === "set_timer") {
    const minutes = Math.max(0.1, Math.min(720, Number(args.minutes) || 5));
    const label = (args.label || "your reminder").toString().slice(0, 200);
    const r = await fetch(`${API}/timers/public`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ minutes, label, resident_id: residentId || null, room: room || null, kiosk_id: kioskId || null }),
    });
    if (!r.ok) return { ok: false, message: `couldn't set the timer (${r.status}).` };
    return { ok: true, message: `okay, I'll remind you in ${minutes < 1 ? `${Math.round(minutes * 60)} seconds` : `${minutes} minutes`}.` };
  }
  if (name === "update_preferred_name") {
    if (ctx?.turn_suspect) {
      // Echo/VAD-overlap risk on the turn that triggered this - do not save.
      return { ok: false, message: ctx.turn_suspect_reason === "echo_like" ? "I want to make sure I heard that right over the background noise — could you say your name again for me?" : "Just to double-check — is that the name you'd like me to use?" };
    }
    const newName = (args.preferred_name || "").toString().trim().slice(0, 60);
    if (!newName) return { ok: false, message: "I didn't catch the name." };
    // TSB-001: ground the claimed correction in what the resident actually
    // said, not just the model's self-reported args - a challenge question
    // ("Why do you call me Ellie?", "Who told you to call me Ellie?") can
    // mention the name too, so also reject turns that read as a question
    // rather than a stated correction. Both real TSB-001 failures were
    // interrogative turns; this rejects both without touching a genuine
    // "my name is X, not Y" / "call me X" correction.
    const heard = (ctx?.last_user_text || "").trim();
    const looksLikeQuestion = /^\s*(why|who|what|when|where|how)\b/i.test(heard);
    if (!heard || !heard.toLowerCase().includes(newName.toLowerCase()) || looksLikeQuestion) {
      return { ok: false, message: "Sorry, I want to make sure I have that right — could you tell me again what you'd like me to call you?" };
    }
    if (!residentId) return { ok: true, message: `okay, I'll call you ${newName} from now on.` };
    const r = await fetch(`${API}/residents/${residentId}/preferred-name`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ preferred_name: newName, room: ctx?.room || null, session_id: ctx?.session_id || null }),
    });
    if (!r.ok) return { ok: false, message: `I'll call you ${newName} from now on (didn't quite save it though).` };
    return { ok: true, message: `okay, ${newName} it is. Saved.` };
  }
  if (name === "end_call" || name === "end_conversation") {
    // 2026-08-22 (real bug, confirmed live): a phantom echo turn ("and")
    // reached this tool and hung up on the resident mid-session. Ending
    // the call is NOT an emergency action, so a suspect turn gets a
    // natural confirmation instead of silent compliance -
    // handleFunctionCall (realtimeMessageHandler.js) only tears down the
    // connection when ok:true comes back from here.
    if (ctx?.turn_suspect) {
      return { ok: false, message: "Just to double-check — did you want me to end our conversation?" };
    }
    // Structural grounding (2026-08-30) - see ENDING_PHRASES above. A real
    // live session ended on the transcript "It's gonna find me." - nothing
    // about that utterance supports ending the call.
    const heard = (ctx?.last_user_text || "").trim();
    if (!heard || !ENDING_PHRASES.test(heard)) {
      return { ok: false, message: "Sorry, I want to make sure — did you want to end our conversation?" };
    }
    // The actual hang-up happens in the calling layer (handleFunctionCall)
    // because it needs access to the peer connection. Returning here just
    // gives the model its short verbal goodbye to speak.
    return { ok: true, message: name === "end_call" ? "goodbye for now. I'm right here when you call." : "sounds good, talk soon." };
  }
  return undefined;
}
