/**
 * Companion timeout = INACTIVITY timer with the EXACT invariant
 * (Level 1 directive 2026-09-07, Room 214 forensics):
 *
 *   ACTIVE SPEECH => NO inactivity timer exists.
 *   The window runs only during a CONTINUOUS period where
 *     residentSpeaking === false  AND  ariaSpeaking === false.
 *   Only a full continuous window of that mutual silence fires onTimeout.
 *
 * Directive tests 1-7.
 */
import { createInactivityTimer } from "../realtimeInactivityTimer";

const FIVE_MIN = 300_000;

beforeEach(() => jest.useFakeTimers());
afterEach(() => jest.useRealTimers());

function mk(seconds = 300) {
  const onTimeout = jest.fn();
  return { onTimeout, t: createInactivityTimer({ seconds, onTimeout }) };
}

// 1. Resident speaks continuously for MORE THAN 5 minutes.
test("1. resident speaking >5 min: no timeout, and NO timer pending during speech", () => {
  const { onTimeout, t } = mk();
  t.open();
  t.residentSpeechStarted();
  expect(t.pending).toBe(false);            // no timer while resident speaks
  for (let i = 0; i < 20; i++) {            // 10 minutes of continuous speech
    jest.advanceTimersByTime(30_000);
    expect(t.pending).toBe(false);
  }
  expect(onTimeout).not.toHaveBeenCalled();
});

// 2. Aria output plays continuously for MORE THAN 5 minutes.
test("2. Aria output >5 min: no timeout, and NO timer pending during output", () => {
  const { onTimeout, t } = mk();
  t.open();
  t.ariaSpeechStarted();
  expect(t.pending).toBe(false);
  for (let i = 0; i < 20; i++) {
    jest.advanceTimersByTime(30_000);
    expect(t.pending).toBe(false);
  }
  expect(onTimeout).not.toHaveBeenCalled();
});

// 3. Overlap: the timer does not arm until BOTH stop.
test("3. overlapping speech: timer does not arm until BOTH sides stop", () => {
  const { onTimeout, t } = mk();
  t.open();
  t.residentSpeechStarted();
  t.ariaSpeechStarted();                    // both speaking
  expect(t.pending).toBe(false);
  t.residentSpeechStopped();                // resident done, Aria still speaking
  expect(t.pending).toBe(false);            // MUST NOT arm - Aria still active
  jest.advanceTimersByTime(60_000);
  expect(t.pending).toBe(false);
  t.ariaSpeechStopped();                    // now BOTH silent
  expect(t.pending).toBe(true);             // window begins here
  jest.advanceTimersByTime(FIVE_MIN - 1);
  expect(onTimeout).not.toHaveBeenCalled();
  jest.advanceTimersByTime(2);
  expect(onTimeout).toHaveBeenCalledTimes(1);
});

// 4. Both silent from the start: the full 5-minute timer runs.
test("4. both silent: a full 5-minute window runs and fires", () => {
  const { onTimeout, t } = mk();
  t.open();
  expect(t.pending).toBe(true);
  jest.advanceTimersByTime(FIVE_MIN - 1);
  expect(onTimeout).not.toHaveBeenCalled();
  jest.advanceTimersByTime(2);
  expect(onTimeout).toHaveBeenCalledTimes(1);
});

// 5. At 4:59 of silence the resident begins speaking -> timer cancels now.
test("5. speech at 4:59 of silence cancels the pending window immediately", () => {
  const { onTimeout, t } = mk();
  t.open();
  jest.advanceTimersByTime(299_000);        // 4:59 of mutual silence
  expect(t.pending).toBe(true);
  t.residentSpeechStarted();
  expect(t.pending).toBe(false);            // cancelled the instant speech starts
  jest.advanceTimersByTime(10_000);         // sail past the old 5:00 mark
  expect(onTimeout).not.toHaveBeenCalled();
});

// 6. Resident later stops and Aria is silent -> a NEW full 5-minute window.
test("6. after speech ends with both silent, a brand-new full window begins", () => {
  const { onTimeout, t } = mk();
  t.open();
  jest.advanceTimersByTime(299_000);
  t.residentSpeechStarted();                // cancels at 4:59
  jest.advanceTimersByTime(120_000);        // talks for 2 minutes
  t.residentSpeechStopped();                // Aria silent -> new window from HERE
  expect(t.pending).toBe(true);
  jest.advanceTimersByTime(FIVE_MIN - 1);   // the OLD window would have fired long ago
  expect(onTimeout).not.toHaveBeenCalled();
  jest.advanceTimersByTime(2);              // 5:00 after the stop
  expect(onTimeout).toHaveBeenCalledTimes(1);
});

// 7. Room 214 regression: an active conversation passes the old
//    5-min-from-session-start boundary indefinitely.
test("7. active conversation passes the old 5-min-from-start boundary indefinitely", () => {
  const { onTimeout, t } = mk();
  t.open();
  // 25 minutes of alternating turns, each side speaking for ~8s with ~4s gaps
  let elapsed = 0;
  while (elapsed < 25 * 60_000) {
    t.residentSpeechStarted(); jest.advanceTimersByTime(8_000);
    t.residentSpeechStopped(); jest.advanceTimersByTime(2_000);
    t.ariaSpeechStarted();     jest.advanceTimersByTime(8_000);
    t.ariaSpeechStopped();     jest.advanceTimersByTime(2_000);
    elapsed += 20_000;
  }
  expect(onTimeout).not.toHaveBeenCalled();     // 25 min in, still alive
  // and it still ends correctly once the room actually goes quiet
  jest.advanceTimersByTime(FIVE_MIN + 5);
  expect(onTimeout).toHaveBeenCalledTimes(1);
});

test("a duplicate speech_stopped does not restart an already-running window", () => {
  const { t } = mk();
  t.open();                                 // window armed
  jest.advanceTimersByTime(120_000);        // 2 min in
  t.residentSpeechStopped();                // flap: stop with no prior start
  jest.advanceTimersByTime(FIVE_MIN - 120_000 - 1);
  expect(t.pending).toBe(true);
  jest.advanceTimersByTime(2);
  // fires at 5:00 from open, not restarted by the stray stop
  expect(t.state.pending).toBe(false);
});

test("cancel() tears the window down (stop() / unmount)", () => {
  const { onTimeout, t } = mk();
  t.open();
  jest.advanceTimersByTime(100_000);
  t.cancel();
  jest.advanceTimersByTime(FIVE_MIN * 3);
  expect(onTimeout).not.toHaveBeenCalled();
  expect(t.pending).toBe(false);
});

test("community-configured window (e.g. 600s) is honoured", () => {
  const { onTimeout, t } = mk(600);
  t.open();
  jest.advanceTimersByTime(FIVE_MIN + 1);
  expect(onTimeout).not.toHaveBeenCalled();
  jest.advanceTimersByTime(FIVE_MIN);
  expect(onTimeout).toHaveBeenCalledTimes(1);
});
