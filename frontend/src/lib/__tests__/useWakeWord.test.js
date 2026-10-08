/** Page side of the wake protocol: wake -> session -> end -> listening again.
 * Mounts the real useWakeWord hook with a fake detector connection. */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockEvents = [];
let mockHandlers = null;
const mockClient = { setState: jest.fn(), close: jest.fn() };

jest.mock("../wakeWordClient", () => ({
  connectWakeWord: (opts) => { mockHandlers = opts; return mockClient; },
}));
jest.mock("../activationClient", () => ({
  logActivationClientEvent: (event, payload) => mockEvents.push({ event, ...payload }),
}));
jest.mock("../api", () => ({ API: "http://api.test/api" }));

const { useWakeWord } = require("../useWakeWord");

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const kiosk = { kiosk_id: "kio_1", room: "214" };

function Harness(props) {
  useWakeWord({ url: "ws://x", kiosk, residentId: "res_1", ...props });
  return null;
}

let root;
let container;
const render = async (props) => { await act(async () => { root.render(<Harness {...props} />); }); };
const states = () => mockClient.setState.mock.calls.map((c) => [c[0], c[1]]);
const flush = async (ms = 0) => { await act(async () => { jest.advanceTimersByTime(ms); await Promise.resolve(); await Promise.resolve(); }); };

beforeEach(() => {
  jest.useFakeTimers();
  mockEvents.length = 0;
  mockClient.setState.mockClear();
  mockClient.close.mockClear();
  mockHandlers = null;
  container = document.createElement("div");
  root = createRoot(container);
  Object.defineProperty(global.navigator, "permissions", {
    configurable: true, value: { query: jest.fn().mockResolvedValue({ state: "granted" }) },
  });
  global.fetch = jest.fn().mockResolvedValue({ json: async () => ({ lease: null }) });
});
afterEach(async () => { await act(async () => root.unmount()); jest.useRealTimers(); });

const wake = (id = "wake_1") => ({ type: "wake", wake_id: id, keyword: "HEY_ARIA", detected_at: new Date().toISOString(), detector: "sherpa-onnx-kws" });

test("idle page tells the detector to listen; a call suppresses it; the end resumes it", async () => {
  await render({ callState: "idle", onWake: jest.fn() });
  expect(states().at(-1)).toEqual(["listening", "call_state_idle"]);
  await render({ callState: "chatting", onWake: jest.fn() });
  expect(states().at(-1)).toEqual(["conversation", "call_state_chatting"]);
  await render({ callState: "idle", onWake: jest.fn() });
  expect(states().at(-1)).toEqual(["listening", "call_state_idle"]);
});

test("a wake while idle starts the conversation once and is traced to the session", async () => {
  const onWake = jest.fn();
  await render({ callState: "idle", onWake });
  global.fetch.mockResolvedValue({ json: async () => ({ lease: {
    trigger_source: "wake_word", created_at: new Date(Date.now() + 500).toISOString(), session_id: "rt_s1", status: "active" } }) });
  await act(async () => { await mockHandlers.onMessage(wake()); });
  expect(onWake).toHaveBeenCalledTimes(1);
  expect(mockEvents.map((e) => e.event)).toContain("wake_word_detected");
  expect(mockEvents.find((e) => e.event === "wake_word_detected").data.keyword).toBe("HEY_ARIA");
  await flush(1000);
  const bound = mockEvents.find((e) => e.event === "wake_word_session_bound");
  expect(bound.session_id).toBe("rt_s1");
});

test("a wake during a call is ignored and the detector is kept suppressed", async () => {
  const onWake = jest.fn();
  await render({ callState: "chatting", onWake });
  await act(async () => { await mockHandlers.onMessage(wake("wake_2")); });
  expect(onWake).not.toHaveBeenCalled();
  expect(mockEvents.find((e) => e.event === "wake_word_ignored").data.reason).toBe("in_call");
  expect(states().at(-1)[0]).toBe("conversation");
});

test("missing microphone permission ignores the wake and returns the detector to listening", async () => {
  navigator.permissions.query.mockResolvedValue({ state: "denied" });
  const onWake = jest.fn();
  await render({ callState: "idle", onWake });
  await act(async () => { await mockHandlers.onMessage(wake("wake_3")); });
  expect(onWake).not.toHaveBeenCalled();
  expect(mockEvents.find((e) => e.event === "wake_word_ignored").data.reason).toBe("mic_permission_denied");
  expect(states().at(-1)).toEqual(["listening", "mic_permission_missing"]);
});

test("the detector's return-to-wake ack is breadcrumbed", async () => {
  await render({ callState: "idle", onWake: jest.fn() });
  await act(async () => { await mockHandlers.onMessage({ type: "listening", at: "t", reason: "call_state_idle" }); });
  expect(mockEvents.map((e) => e.event)).toContain("wake_listening_resumed");
});
