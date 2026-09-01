/**
 * Re-enables the server's own auto-response (create_response:true) by
 * replaying caos.turn_detection unmodified. Shared by every place that
 * turns create_response back on after explicitly disabling it (the forced-
 * greeting window, the resting window) - kept in one place so the exact
 * session.update shape can't drift between call sites.
 */
export function reenableAutoResponse({ send, caos }) {
  if (!caos.turn_detection) return;
  send({
    type: "session.update",
    session: { type: "realtime", audio: { input: { turn_detection: caos.turn_detection } } },
  });
}

/**
 * Owns the forced-greeting create_response:false window's re-enable.
 * Normally fires on output_audio_buffer.stopped/cleared, once the
 * greeting's own audio actually finishes playing.
 *
 * FALLBACK (real incident, 2026-08-30, session
 * rt_p03xjbi2_1788110255978): if the greeting response completes WITHOUT
 * ever producing audio - interrupted by immediate mic pickup before
 * playback started, or an empty response - output_audio_buffer never
 * fires at all, so the normal re-enable never runs and create_response
 * stays permanently false, silencing Aria for the rest of the session.
 * Evidence: 15 further transcribed turns, VAD firing correctly every
 * time, zero further responses, zero output_audio_buffer events of any
 * kind. onResponseDone() is the safety net - response.done is the
 * correct completion signal here since there's no playback left to
 * wait for.
 */
export function createGreetingResponseGate({ send, caos, greetingCreateResponseOffRef }) {
  let audioStarted = false;
  const reenable = () => {
    greetingCreateResponseOffRef.current = false;
    reenableAutoResponse({ send, caos });
  };
  return {
    onAudioStarted() {
      if (greetingCreateResponseOffRef.current) audioStarted = true;
    },
    onAudioStopped() {
      if (greetingCreateResponseOffRef.current) reenable();
    },
    onResponseDone() {
      if (greetingCreateResponseOffRef.current && !audioStarted) reenable();
    },
  };
}
