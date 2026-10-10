/**
 * Ending state machine for one realtime connection (RQ-055).
 * LIVE -> ENDED, one way. endNow() cancels the in-flight response, then runs
 * the hook's real stop() (data channel, peer, mic tracks, timers, lease) and
 * the screen's onEndCall. Idempotent; after it runs the handler ignores all
 * further server events and tool calls, so nothing can resurrect the call.
 * A new conversation needs a new handler: a deliberate new wake or UI start.
 */
import { createEndCorroboration, transcriptIsOutOfScript, turnMayEnd } from "./endIntent";

export const GOODBYE_INSTRUCTIONS = "The resident just said goodbye. Say exactly one short warm sentence, for example: Goodbye, I'm right here when you call. Do not ask a question and do not offer anything else.";

export function createEndController({ send, stop, onEndCall, log }) {
  let ended = false;
  let ending = false;
  const corroboration = createEndCorroboration();
  return {
    get ended() { return ended; },
    /** True from the moment a spoken goodbye is being acknowledged until the connection closes. */
    get ending() { return ending || ended; },
    /** The model's own granted end_call is already speaking its goodbye: just mark the state. */
    markEnding() { ending = true; },
    /**
     * Local end intent with an AUDIBLE acknowledgement (owner, 2026-10-09: a silent cut-off
     * could not be told from a failure). Cancels whatever Aria is saying, asks for one short
     * goodbye, and returns true; the caller arms the hang-up scheduler, which closes after
     * that audio (or at its 7 s ceiling). Idempotent.
     */
    beginEnding(via, detail = {}) {
      if (ending || ended) return false;
      ending = true;
      log("local_end", { meta: { via, acknowledged: true, ...detail } });
      send({ type: "response.cancel" });
      send({ type: "output_audio_buffer.clear" });
      send({ type: "response.create", response: { instructions: GOODBYE_INSTRUCTIONS } });
      return true;
    },
    endNow(kind, via, detail = {}) {
      if (ended) return;
      ended = true;
      log("call_closed", { meta: { via, ...detail } });
      send({ type: "response.cancel" });
      send({ type: "output_audio_buffer.clear" });
      try { stop(kind); } catch { /* teardown is best-effort and must not throw */ }
      try { onEndCall?.(); } catch { /* ditto */ }
    },
    /** The model asked to end twice on usable turns but the transcript never said so: grant the second. */
    corroborate(reason, heardText) {
      // First attempt is enough when the transcript is out of script: the audio-native model heard an ending and the text is a mis-detection.
      const outOfScript = turnMayEnd(reason) && transcriptIsOutOfScript(heardText);
      if (!corroboration.onRefusedAttempt(reason) && !outOfScript) return null;
      log("end_call_corroborated", { meta: { reason, via: outOfScript ? "out_of_script_transcript" : "second_attempt" } });
      return { ok: true, message: "goodbye for now. I'm right here when you call.", corroborated: true };
    },
  };
}
