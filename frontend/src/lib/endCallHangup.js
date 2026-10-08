/**
 * Hang-up timing after a granted end_call (RQ-038). The old fixed 2.5 s
 * timer cut Aria's goodbye short (audio started ~1.8 s before the close).
 * Now: wait for the goodbye's audio to finish, then close after a short
 * tail. Fallbacks: close if no audio starts within 3 s of the goodbye
 * response finishing; never wait longer than 7 s in total.
 */
export const TAIL_MS = 400;
export const NO_AUDIO_MS = 3000;
export const MAX_WAIT_MS = 7000;

export function createHangupScheduler({ onClose, setTimer = setTimeout, clearTimer = clearTimeout }) {
  let armed = false, closed = false, goodbyeResponse = false, audioStarted = false;
  let maxT = null, noAudioT = null, tailT = null;
  const close = () => {
    if (closed) return;
    closed = true;
    [maxT, noAudioT, tailT].forEach((t) => t && clearTimer(t));
    onClose();
  };
  return {
    arm() {
      if (armed) return;
      armed = true;
      maxT = setTimer(close, MAX_WAIT_MS);
    },
    onResponseCreated() { if (armed) goodbyeResponse = true; },
    onResponseDone() {
      if (armed && goodbyeResponse && !audioStarted && !noAudioT) noAudioT = setTimer(close, NO_AUDIO_MS);
    },
    onAudioStarted() {
      if (!armed || !goodbyeResponse) return;
      audioStarted = true;
      if (noAudioT) { clearTimer(noAudioT); noAudioT = null; }
    },
    onAudioStopped() {
      if (armed && audioStarted && !tailT) tailT = setTimer(close, TAIL_MS);
    },
    get closed() { return closed; },
  };
}
