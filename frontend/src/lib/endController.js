/**
 * Ending state machine for one realtime connection (RQ-055, RQ-058).
 * ACTIVE -> CLOSING -> ENDED, one way. CLOSING starts when the resident clearly
 * says goodbye (or the model's end_call is granted): Aria's current speech is
 * cancelled, ONE short spoken goodbye is requested (only after the response
 * that was in flight has finished, so the request cannot collide with it),
 * retried once if it produced no audio, and the connection closes after that
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
 */
import { createEndCorroboration, transcriptIsOutOfScript, turnMayEnd } from "./endIntent";

export const GOODBYE_INSTRUCTIONS = "The resident said goodbye and ended the conversation. Say exactly and only: \"Okay, bye for now.\" Say nothing else. No explanation, offer, question, or extra availability sentence.";
const FALLBACK_SPEECH_MS = 1500;

export function createEndController({ send, stop, onEndCall, log, speak = defaultSpeak }) {
  let ended = false, ending = false;
  let currentId = null;
  const cut = new Set();   // response ids cancelled because the call is ending
  let inFlight = false, pending = false, requested = false, retried = false, audioPlayed = false, fallbackUsed = false;
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
    pending = false; requested = true;
    answerOpenCalls();
    send({ type: "response.create", response: { instructions: GOODBYE_INSTRUCTIONS } });
  };
  const endNow = (kind, via, detail = {}) => {
    if (ended) return;
    ended = true;
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
    markEnding(speakingNow = false) { ending = true; if (speakingNow) audioPlayed = true; },
    beginEnding(via, detail = {}) {
      if (ending || ended) return false;
      ending = true;
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
    noteResponseDone() {
      inFlight = false;
      if (!ending || ended) return;
      if (pending) requestGoodbye();
      else if (requested && !audioPlayed && !retried) { retried = true; requestGoodbye(); }
    },
    noteAudioStarted() { if (ending) audioPlayed = true; },
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
      return { ok: true, message: "Okay, bye for now.", corroborated: true };
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
