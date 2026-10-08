/** RQ-038: hang-up waits for the goodbye audio. */
import { createHangupScheduler, TAIL_MS, NO_AUDIO_MS, MAX_WAIT_MS } from "../endCallHangup";

function make() {
  const onClose = jest.fn();
  const s = createHangupScheduler({ onClose });
  return { s, onClose };
}
beforeEach(() => jest.useFakeTimers());
afterEach(() => jest.useRealTimers());

test("closes 400 ms after the goodbye audio stops, not on a fixed 2.5 s timer", () => {
  const { s, onClose } = make();
  s.arm(); s.onResponseCreated(); s.onAudioStarted();
  jest.advanceTimersByTime(5000); // a long goodbye is not cut off
  expect(onClose).not.toHaveBeenCalled();
  s.onAudioStopped();
  jest.advanceTimersByTime(TAIL_MS - 1);
  expect(onClose).not.toHaveBeenCalled();
  jest.advanceTimersByTime(1);
  expect(onClose).toHaveBeenCalledTimes(1);
});

test("a cleared buffer also ends it the same way (stopped path)", () => {
  const { s, onClose } = make();
  s.arm(); s.onResponseCreated(); s.onAudioStarted(); s.onAudioStopped();
  jest.advanceTimersByTime(TAIL_MS);
  expect(onClose).toHaveBeenCalledTimes(1);
});

test("audio stopping from an earlier response before the goodbye starts is ignored", () => {
  const { s, onClose } = make();
  s.arm(); s.onAudioStopped();
  jest.advanceTimersByTime(2000);
  expect(onClose).not.toHaveBeenCalled();
});

test("no audio within 3 s after the goodbye response finishes closes it", () => {
  const { s, onClose } = make();
  s.arm(); s.onResponseCreated(); s.onResponseDone();
  jest.advanceTimersByTime(NO_AUDIO_MS - 1);
  expect(onClose).not.toHaveBeenCalled();
  jest.advanceTimersByTime(1);
  expect(onClose).toHaveBeenCalledTimes(1);
});

test("audio starting inside that 3 s cancels the fallback", () => {
  const { s, onClose } = make();
  s.arm(); s.onResponseCreated(); s.onResponseDone();
  jest.advanceTimersByTime(2000); s.onAudioStarted();
  jest.advanceTimersByTime(4000);
  expect(onClose).not.toHaveBeenCalled();
});

test("a response.done before the goodbye response was created does not start the 3 s timer", () => {
  const { s, onClose } = make();
  s.arm(); s.onResponseDone();
  jest.advanceTimersByTime(NO_AUDIO_MS + 500);
  expect(onClose).not.toHaveBeenCalled();
});

test("never waits more than 7 s", () => {
  const { s, onClose } = make();
  s.arm(); s.onResponseCreated(); s.onAudioStarted();
  jest.advanceTimersByTime(MAX_WAIT_MS);
  expect(onClose).toHaveBeenCalledTimes(1);
});

test("closes once only and does nothing unless armed", () => {
  const { s, onClose } = make();
  s.onResponseCreated(); s.onAudioStarted(); s.onAudioStopped();
  jest.advanceTimersByTime(10000);
  expect(onClose).not.toHaveBeenCalled();
  s.arm(); s.onResponseCreated(); s.onAudioStarted(); s.onAudioStopped();
  jest.advanceTimersByTime(MAX_WAIT_MS);
  expect(onClose).toHaveBeenCalledTimes(1);
});
