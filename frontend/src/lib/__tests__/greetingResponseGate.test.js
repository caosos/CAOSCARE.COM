/**
 * Regression test for a real live incident, 2026-08-30, session
 * rt_p03xjbi2_1788110255978: the resident's forced-greeting response
 * completed with zero output_audio_buffer events of any kind (interrupted
 * by immediate mic pickup before playback ever started), so the create_
 * response:false window set for that greeting was never re-enabled -
 * Aria was silenced for the rest of the 15-turn session. Real DB evidence:
 * `db.realtime_diagnostics` for that session shows exactly one
 * response_created/response_done pair and NO output_audio_buffer.started/
 * stopped/cleared events at all.
 */
import { createGreetingResponseGate, reenableAutoResponse } from "../realtimeAutoResponseGate";

function setup() {
  const send = jest.fn();
  const caos = { turn_detection: { type: "server_vad", silence_duration_ms: 500 } };
  const greetingCreateResponseOffRef = { current: true };
  const gate = createGreetingResponseGate({ send, caos, greetingCreateResponseOffRef });
  return { send, caos, greetingCreateResponseOffRef, gate };
}

test("reenableAutoResponse replays turn_detection unmodified", () => {
  const send = jest.fn();
  const caos = { turn_detection: { type: "server_vad" } };
  reenableAutoResponse({ send, caos });
  expect(send).toHaveBeenCalledWith({
    type: "session.update",
    session: { type: "realtime", audio: { input: { turn_detection: caos.turn_detection } } },
  });
});

test("real incident repro: response.done with no audio ever started must re-enable create_response", () => {
  const { send, greetingCreateResponseOffRef, gate } = setup();
  // No onAudioStarted() call at all - exactly what the real session showed.
  gate.onResponseDone();
  expect(greetingCreateResponseOffRef.current).toBe(false);
  expect(send).toHaveBeenCalledTimes(1);
});

test("normal path: audio starts and stops - re-enabled once, on stop, not again on response.done", () => {
  const { send, greetingCreateResponseOffRef, gate } = setup();
  gate.onAudioStarted();
  gate.onAudioStopped();
  expect(greetingCreateResponseOffRef.current).toBe(false);
  expect(send).toHaveBeenCalledTimes(1);
  gate.onResponseDone();
  expect(send).toHaveBeenCalledTimes(1); // no duplicate re-enable
});

test("audio starts but response.done fires before stop - fallback must not fire early", () => {
  const { send, greetingCreateResponseOffRef, gate } = setup();
  gate.onAudioStarted();
  gate.onResponseDone(); // generation-complete, but still playing
  expect(greetingCreateResponseOffRef.current).toBe(true);
  expect(send).not.toHaveBeenCalled();
  gate.onAudioStopped();
  expect(greetingCreateResponseOffRef.current).toBe(false);
  expect(send).toHaveBeenCalledTimes(1);
});
