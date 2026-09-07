/**
 * Companion timeout = INACTIVITY timer, not a session-age timer.
 * Level 1 directive 2026-09-07 (Room 214 forensics): session rt_mkqn5z8x
 * was terminated at ~302s mid-song by a one-shot 300s timer armed at
 * dc.onopen. An active conversation must have NO time limit.
 *
 * Directive tests 1-6 (7 is end-call grounding, see restingEndCallGuard).
 */
import { createInactivityTimer } from "../realtimeInactivityTimer";

const FIVE_MIN = 300_000;

beforeEach(() => jest.useFakeTimers());
afterEach(() => jest.useRealTimers());

// 1. An active conversation can continue well beyond 5 minutes.
test("1. active conversation continues past 5 minutes without termination", () => {
  const onTimeout = jest.fn();
  const t = createInactivityTimer({ seconds: 300, onTimeout });
  t.bump(); // dc.onopen initial arm
  // a speech event roughly every 20s for 20 minutes
  for (let i = 0; i < 60; i++) {
    jest.advanceTimersByTime(20_000);
    t.bump(); // speech_started / output_audio_buffer.started / ...
  }
  expect(onTimeout).not.toHaveBeenCalled();
  expect(t.pending).toBe(true);
});

// 2 & 3. Speech (Aria or resident) across the 5-min-from-session-start
// boundary does not trigger companion_timeout.
test("2/3. speech across the 5-min-from-start boundary does not fire the timeout", () => {
  const onTimeout = jest.fn();
  const t = createInactivityTimer({ seconds: 300, onTimeout });
  t.bump();
  jest.advanceTimersByTime(290_000);
  t.bump();                       // Aria singing / resident speaking at 4:50
  jest.advanceTimersByTime(20_000);  // now 5:10 - past the OLD absolute boundary
  expect(onTimeout).not.toHaveBeenCalled();
  jest.advanceTimersByTime(FIVE_MIN - 20_000 + 5);  // full fresh window from the 4:50 bump
  expect(onTimeout).toHaveBeenCalledTimes(1);
});

// 4. Five continuous minutes of genuine inactivity DOES fire.
test("4. five continuous minutes of real inactivity fires the timeout", () => {
  const onTimeout = jest.fn();
  const t = createInactivityTimer({ seconds: 300, onTimeout });
  t.bump();
  jest.advanceTimersByTime(FIVE_MIN - 1);
  expect(onTimeout).not.toHaveBeenCalled();
  jest.advanceTimersByTime(2);
  expect(onTimeout).toHaveBeenCalledTimes(1);
});

// 5. Speech after inactivity has begun cancels the pending timeout.
test("5. speech after silence begins cancels the pending inactivity timeout", () => {
  const onTimeout = jest.fn();
  const t = createInactivityTimer({ seconds: 300, onTimeout });
  t.bump();
  jest.advanceTimersByTime(250_000);   // 4:10 of silence
  t.bump();                            // resident speaks -> cancel + restart
  jest.advanceTimersByTime(FIVE_MIN - 1);   // would have fired at 300s under the old window
  expect(onTimeout).not.toHaveBeenCalled();
  jest.advanceTimersByTime(2);         // 300s after the NEW bump
  expect(onTimeout).toHaveBeenCalledTimes(1);
});

// 6. A later period of inactivity gets its own full 5-minute window.
test("6. a later inactivity period gets its own full 5-minute window", () => {
  const onTimeout = jest.fn();
  const t = createInactivityTimer({ seconds: 300, onTimeout });
  t.bump();
  for (let i = 0; i < 12; i++) { jest.advanceTimersByTime(30_000); t.bump(); } // ~6 min of activity
  expect(onTimeout).not.toHaveBeenCalled();
  jest.advanceTimersByTime(FIVE_MIN - 1);   // now genuinely quiet
  expect(onTimeout).not.toHaveBeenCalled();
  jest.advanceTimersByTime(2);
  expect(onTimeout).toHaveBeenCalledTimes(1);
});

test("cancel() stops a pending timeout (teardown / stop())", () => {
  const onTimeout = jest.fn();
  const t = createInactivityTimer({ seconds: 300, onTimeout });
  t.bump();
  jest.advanceTimersByTime(200_000);
  t.cancel();
  jest.advanceTimersByTime(FIVE_MIN * 2);
  expect(onTimeout).not.toHaveBeenCalled();
  expect(t.pending).toBe(false);
});

test("community-configured window is honoured", () => {
  const onTimeout = jest.fn();
  const t = createInactivityTimer({ seconds: 600, onTimeout });
  t.bump();
  jest.advanceTimersByTime(FIVE_MIN + 1);
  expect(onTimeout).not.toHaveBeenCalled();   // 10-min window, not 5
  jest.advanceTimersByTime(FIVE_MIN);
  expect(onTimeout).toHaveBeenCalledTimes(1);
});
