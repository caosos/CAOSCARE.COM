/**
 * RQ-050: fail-closed claim INTERRUPTER (default OFF).
 *
 * claimGuard.js only logs a false sentence after it is heard. This watches the
 * assistant transcript as it streams (response.output_audio_transcript.delta),
 * and when a COMPLETE sentence claims an action / weather fact / live lookup
 * that no ok tool result in the same resident turn supports, it sends
 *   response.cancel (this response)  ->  output_audio_buffer.clear
 * and then ONE corrective response.create that states only what happened.
 *
 * Honest limits (docs/reports/2026-10-09-claim-enforcement-feasibility.md):
 *  - it cannot stop the words already played before the sentence ended
 *    (it waits for the sentence terminator so a trailing "if you like" is seen);
 *  - cancelling a response that was about to emit a tool call drops that call;
 *    the corrective turn then tells the truth (nothing was sent) and offers a
 *    staff request, so the failure is honest, not silent.
 *
 * Modes (REACT_APP_CLAIM_INTERRUPTER): "off" (default, nothing observes),
 * "shadow" (logs claim_interrupter_would_cut with timing, sends nothing),
 * "on" (cuts). Never during emergency / live-line tools. Once per resident turn.
 */
import { ACTION_CLAIM, LOOKUP_CLAIM } from "./claimGuard";

export function claimInterrupterMode() {
  const v = (process.env.REACT_APP_CLAIM_INTERRUPTER || "off").toLowerCase();
  return v === "on" || v === "shadow" ? v : "off";
}

const ACTION_TOOL = /^(request_|toggle_|set_|adjust_|update_|cancel_|change_|confirm_|transfer_)/;
const EMERGENCY_TOOL = /^(call_for_help|request_live_staff|end_call|end_conversation|mark_resting)$/;
// Stricter than claimGuard's bare "weather" word: a stated condition.
const WEATHER_STATED = /\b(?:it(?:'s| is)|weather[^.!?]*\bis|will be|tonight is)\b[^.!?]*\b(?:cool|cold|warm|hot|clear|sunny|rain\w*|cloud\w*|\d+\s*degrees?)\b/i;
const CONDITIONAL = /\b(?:if you|would you like|do you want|should I|shall I|want me to|can I|may I)\b/i;
const CORRECTIVE =
  "Your last sentence claimed something no tool result confirms, and it was cut off. " +
  "State plainly and briefly: nothing has been sent or done yet, you could not confirm it. " +
  "Do not say anyone was told, notified or is coming. Offer to send a staff request, and call request_staff_help only if the resident says yes.";

function sentenceWithClaim(text) {
  const parts = text.match(/[^.!?]+[.!?]+/g) || []; // complete sentences only
  for (const s of parts) {
    if (CONDITIONAL.test(s) || s.trim().endsWith("?")) continue;
    if (ACTION_CLAIM.test(s)) return { kind: "action", sentence: s.trim() };
    if (LOOKUP_CLAIM.test(s)) return { kind: "lookup", sentence: s.trim() };
    if (WEATHER_STATED.test(s)) return { kind: "weather", sentence: s.trim() };
  }
  return null;
}

export function createClaimInterrupter({ send, log, mode = claimInterrupterMode(), now = Date.now }) {
  const text = new Map();      // response_id -> accumulated transcript
  const started = new Map();   // response_id -> ms of response.created
  const cut = new Set();       // responses already cancelled
  let okAction = false, okWeather = false, okLive = false;
  let pending = 0;             // tool calls in flight
  let exempt = false;          // emergency / live-line tool seen this turn
  let usedThisTurn = false;
  let nextIsCorrective = false;
  const correctiveIds = new Set();

  const evaluate = (responseId) => {
    if (mode === "off" || usedThisTurn || cut.has(responseId) || correctiveIds.has(responseId)) return;
    if (exempt || pending > 0) return;
    const hit = sentenceWithClaim(text.get(responseId) || "");
    if (!hit) return;
    if (hit.kind === "action" && okAction) return;
    if (hit.kind === "weather" && okWeather) return;
    if (hit.kind === "lookup" && okLive) return;
    usedThisTurn = true;
    const ms = started.has(responseId) ? now() - started.get(responseId) : null;
    if (mode === "shadow") {
      log("claim_interrupter_would_cut", { text: hit.sentence, meta: { kind: hit.kind, ms_since_response_created: ms } });
      return;
    }
    cut.add(responseId);
    send({ type: "response.cancel", response_id: responseId });
    send({ type: "output_audio_buffer.clear" });
    nextIsCorrective = true;
    send({ type: "response.create", response: { instructions: CORRECTIVE } });
    log("claim_interrupter_cut", { text: hit.sentence, meta: { kind: hit.kind, ms_since_response_created: ms } });
  };

  return {
    onUserTurn() { okAction = okWeather = okLive = exempt = usedThisTurn = false; pending = 0; },
    onToolStart(name) { if (EMERGENCY_TOOL.test(name)) exempt = true; pending += 1; },
    onToolResult(name, result) {
      pending = Math.max(0, pending - 1);
      if (!result || result.ok !== true) return;
      if (name === "get_weather") okWeather = true;
      else if (name === "research_topic") { if (result.live === true) okLive = true; }
      else if (ACTION_TOOL.test(name)) okAction = true;
    },
    onResponseCreated(responseId) {
      started.set(responseId, now());
      if (nextIsCorrective) { correctiveIds.add(responseId); nextIsCorrective = false; }
    },
    onTranscriptDelta(msg) {
      const id = msg?.response_id;
      if (!id || cut.has(id)) return;
      text.set(id, (text.get(id) || "") + (msg.delta || ""));
      evaluate(id);
    },
    onResponseDone(response) {
      const id = response?.id;
      if (id) { text.delete(id); started.delete(id); }
    },
  };
}

/**
 * (b)(2) structural alternative: after an ok action tool result, ask for the
 * spoken confirmation with the verified message carried in the instructions,
 * instead of a bare response.create the model may improvise on.
 */
export function verifiedConfirmationEvent(name, result) {
  if (!result || result.ok !== true || !result.message) return null;
  if (!ACTION_TOOL.test(name)) return null;
  return {
    type: "response.create",
    response: {
      instructions: "Confirm to the resident in one or two warm sentences, saying only this and nothing more " +
        "(no extra promises, no one is 'on the way' unless it says so): " + String(result.message),
    },
  };
}
