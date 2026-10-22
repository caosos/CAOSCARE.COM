/**
 * The model chooses on/off from the raw audio; the transcript of the same
 * sentence comes from a separate pipeline. Before a power change runs, the
 * two must not contradict each other (Room 214: "Turn on my overhead light"
 * -> off on 2026-10-10 and 10-12; a false wake heard as "Overhead line"
 * turned the light off at 02:04 on 10-12). On disagreement, or a power
 * change with nothing in the sentence asking for one, ask instead of acting.
 * A turn with no transcript at all is not blocked (no evidence either way).
 */
const ON = /\bon\b/i;
const OFF = /\b(off|shut|darken|dark)\b|\blights? out\b/i;
const NEGATED = /\b(don'?t|do not|never|not)\b/i;
const POWER_WORDS = /\b(turn|switch|shut|put|light|lights|lamp|on|off|bright|dim|dark|darken)\b/i;
// A plain yes to Aria's own question ("Turn off the overhead light?" - "Yes.") carries no on/off but asks for it.
const CONFIRM = /\b(yes|yeah|yep|sure|okay|ok|please|do it|go ahead|pick one)\b/i;

export function heardPowerDirection(text) {
  const t = String(text || "");
  if (NEGATED.test(t)) return null;
  const on = ON.test(t), off = OFF.test(t);
  return on === off ? null : on ? "on" : "off";
}

// A short refusal message for the model, or null when the action may run.
// answering = the turn replies to Aria's own "which one?" question, so it need not repeat on/off.
export function powerDirectionMismatch(state, text, label = "light", { answering = false } = {}) {
  if (state !== "on" && state !== "off") return null;
  const words = String(text || "").trim();
  if (!words) return null;   // no transcript for the turn: no evidence either way
  const heard = heardPowerDirection(words);
  const contradicts = heard && heard !== state;
  const unasked = !answering && !heard && !POWER_WORDS.test(words) && !CONFIRM.test(words);
  if (!contradicts && !unasked) return null;
  return `I want to be sure I heard you right - did you want the ${label} on or off? (Nothing was changed.)`;
}

// A direct, unambiguous spoken light command ("Turn on the desk lamp, please.", "Switch the overhead light
// off"). Room 214 rt_3bfuhkov 07:11 and rt_tbfytpqr 15:52 CDT, 2026-10-21 (as on 10-10 and 10-12): the
// transcript said ON, the model sent OFF from its own reading of the audio, the guard refused, and the model
// retried OFF. The refusal stays; for a command this plain it names the heard direction (realtimeLightControl.js).
const DIRECT = /\b(turn|switch|shut)\b/i;
const LIGHT_WORD = /\b(light|lights|lamp|lamps)\b/i;
export function spokenLightCommand(text) {
  const t = String(text || "").trim();
  if (!t || t.split(/\s+/).length > 10 || !DIRECT.test(t) || !LIGHT_WORD.test(t) || /\?|\b(if|when|should|maybe)\b/i.test(t)) return null;
  return heardPowerDirection(t);
}
