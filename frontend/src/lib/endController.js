/**
 * Ending state machine for one realtime connection (RQ-055).
 * LIVE -> ENDED, one way. endNow() cancels the in-flight response, then runs
 * the hook's real stop() (data channel, peer, mic tracks, timers, lease) and
 * the screen's onEndCall. Idempotent; after it runs the handler ignores all
 * further server events and tool calls, so nothing can resurrect the call.
 * A new conversation needs a new handler: a deliberate new wake or UI start.
 */
import { createEndCorroboration } from "./endIntent";

export function createEndController({ send, stop, onEndCall, log }) {
  let ended = false;
  const corroboration = createEndCorroboration();
  return {
    get ended() { return ended; },
    endNow(kind, via, detail = {}) {
      if (ended) return;
      ended = true;
      log("local_end", { meta: { via, ...detail } });
      send({ type: "response.cancel" });
      send({ type: "output_audio_buffer.clear" });
      try { stop(kind); } catch { /* teardown is best-effort and must not throw */ }
      try { onEndCall?.(); } catch { /* ditto */ }
    },
    /** The model asked to end twice on usable turns but the transcript never said so: grant the second. */
    corroborate(reason) {
      if (!corroboration.onRefusedAttempt(reason)) return null;
      log("end_call_corroborated", { meta: { reason } });
      return { ok: true, message: "goodbye for now. I'm right here when you call.", corroborated: true };
    },
  };
}
