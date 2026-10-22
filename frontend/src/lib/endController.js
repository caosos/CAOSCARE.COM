/**
 * Ending state machine for one realtime connection (RQ-055, RQ-058).
 * ACTIVE -> CLOSING -> ENDED, one way. CLOSING starts when the resident clearly
 * says goodbye (or the model's end_call is granted): Aria's current speech is
 * cancelled, ONE short spoken goodbye is requested (only after the response
 * that was in flight has finished, so the request cannot collide with it),
 * retried once only if THAT goodbye (marked by response metadata) finished
 * and no audio started within RETRY_GRACE_MS - a goodbye's response.done can
 * come before its audio (low-cost voice: Room 214 rt_lcnze2u9, 2026-10-17, the
 * early retry replaced the first goodbye and both were saved as said) - and
 * never while a goodbye is still open; the connection closes after that
 * audio (hang-up scheduler, 7 s ceiling). If no goodbye audio ever played, a
 * local "Goodbye." (browser speech) is spoken before closing. ENDED = the
 * hook's real stop() ran (data channel, peer, mic tracks, timers, lease).
 * While CLOSING/ENDED the handler ignores tools, transcripts and new speech.
 * A new conversation needs a new handler: a deliberate new wake or UI start.
 *
 * The response CUT by the goodbye is not something Aria said: the server's
 * auto-response to "Thanks, that will be all. Goodbye." had started before the
 * transcript arrived, the model was narrating its end_call ("Okay, thanks for
 * the chat - let me take care of that for you now."), ~200 ms of it played
 * before the clear, and its full text was still shown and saved as her turn
 * (scratch Room 214 rt_10s3ng43_1792142773769, aria-room-conversation-cleanup-002).
 * wasCut(responseId) lets the handler keep that text out of the conversation.
 *
 * Once CLOSING starts the server's own turn-taking is switched off (quietServer: server VAD
 * off, turn_detection null - create/interrupt false still let rt_d3ahe1bf clear the goodbye). rt_52ayqcen, 2026-10-21:
 * after "goodbye" the resident's next words made server VAD cancel "Okay, bye for
 * now" after "Okay," and auto-create a normal reply ("No worries... do you want to
 * just chat?"), which became her last words before the hang-up.
 */
import { createEndCorroboration, transcriptIsOutOfScript, turnMayEnd } from "./endIntent";

export const GOODBYE_LINE = "Okay, bye for now.";
// A room can carry its own closing words (caos.context.goodbye_line, owner room only: routes/owner_room_context.py).
export const goodbyeInstructions = (line = GOODBYE_LINE) => `The resident said goodbye and ended the conversation. Say exactly and only: "${line}" Say nothing else. No explanation, offer, question, or extra availability sentence.`;
export const GOODBYE_INSTRUCTIONS = goodbyeInstructions();
const FALLBACK_SPEECH_MS = 1500;
export const RETRY_GRACE_MS = 2500;   // a spoken goodbye starts well within this (low-cost voice: ~0.2-2.5 s)
export const GOODBYE_METADATA = { caos_goodbye: "1" };
const isGoodbye = (response) => response?.metadata?.caos_goodbye === "1";

export function createEndController({ send, stop, onEndCall, log, speak = defaultSpeak,
  setTimer = setTimeout, clearTimer = clearTimeout, quietServer = () => {}, goodbyeLine = GOODBYE_LINE }) {
  const instructions = goodbyeInstructions(goodbyeLine);
  let ended = false, ending = false, quieted = false;
  const quiet = () => { if (!quieted) { quieted = true; try { quietServer(); } catch { /* best-effort */ } } };
  let currentId = null;
  const cut = new Set();   // response ids cancelled because the call is ending
  let inFlight = false, pending = false, requested = false, retried = false, audioPlayed = false, fallbackUsed = false;
  let goodbyeOpen = false, retryT = null;   // a goodbye requested and not yet done; the delayed retry check
  const corroboration = createEndCorroboration();
  // Tool calls the model is still waiting on. Answered before the goodbye is requested, or the model
  // says "I'm still waiting on that to finish" (Room 214, 2026-10-12 12:56).
  const openCalls = new Set();
  const answerOpenCalls = () => {
    for (const callId of openCalls) {
      send({ type: "conversation.item.create", item: { type: "function_call_output", call_id: callId, output: JSON.stringify({ ok: true, message: "The call is ending." }) } });
    }
    openCalls.clear();
  };
  const requestGoodbye = () => {
    pending = false;
    if (goodbyeOpen || ended) return;      // one goodbye at a time
    requested = true; goodbyeOpen = true;
    answerOpenCalls();
    send({ type: "response.create", response: { instructions, metadata: GOODBYE_METADATA } });
  };
  const stopRetry = () => { if (retryT) { clearTimer(retryT); retryT = null; } };
  const endNow = (kind, via, detail = {}) => {
    if (ended) return;
    ended = true; stopRetry();
    log("call_closed", { meta: { via, goodbye_audio_played: audioPlayed, local_fallback_used: fallbackUsed, ...detail } });
    send({ type: "response.cancel" });
    send({ type: "output_audio_buffer.clear" });
    try { stop(kind); } catch { /* teardown is best-effort and must not throw */ }
    try { onEndCall?.(); } catch { /* ditto */ }
  };
  return {
    get ended() { return ended; },
    /** True from the moment a goodbye is being acknowledged until the connection closes. */
    get ending() { return ending || ended; },
    /** The model's own granted end_call is already speaking its goodbye: just mark the state. */
    /** speakingNow: her goodbye is already playing (it started before the end was granted). */
    markEnding(speakingNow = false) { ending = true; quiet(); if (speakingNow) audioPlayed = true; },
    beginEnding(via, detail = {}) {
      if (ending || ended) return false;
      ending = true; quiet();
      log("local_end", { meta: { via, acknowledged: true, ...detail } });
      if (inFlight) {
        pending = true;
        if (currentId) cut.add(currentId);
        send({ type: "response.cancel" }); send({ type: "output_audio_buffer.clear" });
      }
      else { send({ type: "output_audio_buffer.clear" }); requestGoodbye(); }
      return true;
    },
    noteCallOpened(callId) { if (callId) openCalls.add(callId); },
    noteCallAnswered(callId) { openCalls.delete(callId); },
    noteResponseCreated(id = null) { inFlight = true; currentId = id; },
    /** True for a response the goodbye cancelled: its words were cut, not said. */
    wasCut(responseId) { return Boolean(responseId) && cut.has(responseId); },
    noteResponseDone(response = null) {
      inFlight = false;
      if (!ending || ended) return;
      if (pending) return requestGoodbye();
      if (!isGoodbye(response)) return;    // another response ending (e.g. the one the goodbye cut) is not the goodbye
      goodbyeOpen = false;
      if (requested && !audioPlayed && !retried && !retryT) {
        retryT = setTimer(() => { retryT = null; if (!audioPlayed && !ended) { retried = true; requestGoodbye(); } }, RETRY_GRACE_MS);
      }
    },
    noteAudioStarted() { if (ending) { audioPlayed = true; stopRetry(); } },
    /** Close now; if the goodbye was never heard, say it locally first. */
    finish(kind, via, detail = {}) {
      if (ended) return;
      if (ending && !audioPlayed && !fallbackUsed) {
        fallbackUsed = true;
        let done = false;
        const go = () => { if (!done) { done = true; endNow(kind, via, detail); } };
        if (speak("Goodbye.", go)) { setTimeout(go, FALLBACK_SPEECH_MS); return; }
      }
      endNow(kind, via, detail);
    },
    endNow,
    /** The model asked to end twice on usable turns (or once on an out-of-script transcript) but the transcript never said so: grant. */
    corroborate(reason, heardText) {
      const outOfScript = turnMayEnd(reason) && transcriptIsOutOfScript(heardText);
      if (!corroboration.onRefusedAttempt(reason) && !outOfScript) return null;
      log("end_call_corroborated", { meta: { reason, via: outOfScript ? "out_of_script_transcript" : "second_attempt" } });
      return { ok: true, message: goodbyeLine, corroborated: true };
    },
  };
}

function defaultSpeak(text, onDone) {
  try {
    if (typeof window === "undefined" || !window.speechSynthesis || typeof SpeechSynthesisUtterance === "undefined") return false;
    const u = new SpeechSynthesisUtterance(text);
    u.onend = onDone; u.onerror = onDone;
    window.speechSynthesis.speak(u);
    return true;
  } catch { return false; }
}
