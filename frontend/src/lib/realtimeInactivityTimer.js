/**
 * Resident Aria companion timeout — an INACTIVITY timer, not a session-age
 * timer (Level 1 directive, 2026-09-07; Room 214 forensics: session
 * rt_mkqn5z8x was cut off at ~302s mid-song by a one-shot 300s timer armed
 * at dc.onopen).
 *
 * EXACT INVARIANT
 *
 *   ACTIVE SPEECH ⇒ NO INACTIVITY TIMER EXISTS.
 *
 *   The window measures only a *continuous* period during which BOTH sides
 *   are silent:  residentSpeaking === false  AND  ariaSpeaking === false.
 *
 *   dc.onopen (nobody speaking yet) ......... arm the window
 *   resident speech_started ................. cancel the window (none pending
 *                                             while the resident speaks)
 *   resident speech_stopped ................. mark resident silent; arm ONLY
 *                                             IF Aria is also silent
 *   Aria output_audio_buffer.started ....... cancel the window
 *   Aria output_audio_buffer.stopped/cleared  mark Aria silent; arm ONLY IF
 *                                             the resident is also silent
 *   overlap ................................ the window is not armed until
 *                                             BOTH have stopped
 *   response.done is NOT used — the output-audio lifecycle is authoritative.
 *
 *   `seconds` continuous with both silent ⇒ onTimeout() (companion_timeout,
 *   per the existing aria-event lifecycle policy). Any new speech cancels a
 *   pending window; when both go silent again a brand-new full window begins.
 *
 * `setTimeoutFn` / `clearTimeoutFn` are injectable for tests.
 */
export function createInactivityTimer({
  seconds = 300,
  onTimeout,
  setTimeoutFn = (typeof setTimeout !== "undefined" ? setTimeout : null),
  clearTimeoutFn = (typeof clearTimeout !== "undefined" ? clearTimeout : null),
} = {}) {
  const ms = Math.max(1, seconds) * 1000;
  let handle = null;
  let residentSpeaking = false;
  let ariaSpeaking = false;

  const cancel = () => {
    if (handle != null) {
      try { clearTimeoutFn(handle); } catch { /* ignore */ }
      handle = null;
    }
  };

  // Arm ONLY when both sides are silent, and only if no window is already
  // running (a genuine active→silent transition, not a flapping stop event).
  const armIfBothSilent = () => {
    if (residentSpeaking || ariaSpeaking) return;
    if (handle != null) return;
    handle = setTimeoutFn(() => {
      handle = null;
      try { onTimeout?.(); } catch { /* never let the callback throw into a timer */ }
    }, ms);
  };

  return {
    // dc.onopen — the room is silent until the greeting plays.
    open() { residentSpeaking = false; ariaSpeaking = false; cancel(); armIfBothSilent(); },

    residentSpeechStarted() { residentSpeaking = true; cancel(); },
    residentSpeechStopped() { residentSpeaking = false; armIfBothSilent(); },
    ariaSpeechStarted() { ariaSpeaking = true; cancel(); },
    ariaSpeechStopped() { ariaSpeaking = false; armIfBothSilent(); },

    cancel,  // teardown / stop()

    get pending() { return handle != null; },
    get windowMs() { return ms; },
    get state() { return { residentSpeaking, ariaSpeaking, pending: handle != null }; },
  };
}
