/**
 * Resident Aria companion timeout - an INACTIVITY timer, not a session-age
 * timer (Level 1 directive, 2026-09-07, Room 214 forensics).
 *
 * PRODUCT CONTRACT:
 *   An active conversation has NO time limit. Michael and Aria may talk for
 *   5 minutes, 30 minutes, an hour - as long as the resident wants.
 *
 *   The five-minute window applies ONLY to actual inactivity:
 *     - words being exchanged (resident speech OR Aria speech) -> cancel +
 *       restart a fresh full window on every such event;
 *     - five continuous minutes with no speech event of any kind -> fire
 *       `onTimeout` (companion_timeout, per the existing lifecycle policy).
 *
 * This is a rolling idle-timeout: every speech-lifecycle event (resident
 * speech start/stop, Aria audio start/stop, response.done) calls `bump()`,
 * which clears any pending timer and starts a new full window. It never
 * fires while the conversation is active because each event pushes it out;
 * it only fires once the room actually goes quiet for the whole window.
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

  const cancel = () => {
    if (handle != null) {
      try { clearTimeoutFn(handle); } catch { /* ignore */ }
      handle = null;
    }
  };

  const bump = () => {
    cancel();
    handle = setTimeoutFn(() => {
      handle = null;
      try { onTimeout?.(); } catch { /* never let the callback throw into a timer */ }
    }, ms);
  };

  return {
    bump,            // any speech event OR initial arm: fresh full window
    cancel,          // teardown
    get pending() { return handle != null; },
    get windowMs() { return ms; },
  };
}
