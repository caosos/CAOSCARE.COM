process.env.REACT_APP_BACKEND_URL = "http://localhost:8000";
jest.mock("../api", () => ({ API: "http://localhost:8000/api" }));
jest.mock("../realtimeMessageHandler", () => ({ createRealtimeHandlers: () => ({ onMessage: jest.fn() }) }));
jest.mock("../realtimeDiagnostics", () => ({ logRealtimeEvent: jest.fn() }));
import { connectRealtimeVoice } from "../realtimeConnection";

const ref = (current = null) => ({ current });
let p, track, pc, heartbeatOK;
const response = (data) => ({ ok: true, json: async () => data });
class Peer extends EventTarget {
  constructor() { super(); pc = this; this.connectionState = "connected"; }
  addTrack() {}
  createDataChannel() {
    this.dc = new EventTarget(); this.dc.send = jest.fn(); return this.dc;
  }
  async createOffer() { return { sdp: "offer" }; }
  async setLocalDescription() {}
  async setRemoteDescription() { this.dc.onopen(); }
  close = jest.fn();
}
beforeEach(() => {
  jest.useFakeTimers(); heartbeatOK = true;
  track = new EventTarget(); track.stop = jest.fn(); track.getSettings = () => ({});
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: {
    getUserMedia: jest.fn().mockResolvedValue({ getTracks: () => [track], getAudioTracks: () => [track] }),
    enumerateDevices: async () => [],
  }});
  AbortSignal.timeout = () => undefined;
  global.RTCPeerConnection = Peer;
  global.fetch = jest.fn(async (url) => {
    if (url.endsWith("/session")) return response({ value: "fake", _caos: {
      lease: { claimed: true }, instructions: "test persona", context: { activation_id: "cycle" },
    }});
    if (url.endsWith("/heartbeat")) return response({ ok: heartbeatOK });
    if (url.endsWith("/negotiate")) return response({ sdp: "answer" });
    throw new Error(`Unexpected request ${url}`);
  });
  p = { room: "isolated_room", residentId: "fake", alertId: "event", activationId: "cycle", sessionEndpoint: "/realtime/session" };
  for (const key of ["attemptRef", "pcRef", "dcRef", "localStreamRef", "audioElRef", "leaseHeartbeatRef", "leaseRoomRef",
    "sessionIdRef", "lifecycleCleanupRef", "assistantSpeakingRef", "turnSuspectRef", "greetingCreateResponseOffRef",
    "restingRef", "firstSpeechHeardRef", "awaitingAnswerTimerRef", "inviteSilenceTimerRef", "companionTimeoutTimerRef", "endReasonLoggedRef"])
    p[key] = ref();
  p.startGenRef = ref(0); p.ctxRef = ref({});
  for (const key of ["onEndCall", "setStatus", "setError", "setMicLabel", "setResting", "setTranscript",
    "releaseLease", "postAriaEvent", "startAwaitingAnswerTimer", "logSessionEnded"]) p[key] = jest.fn();
  p.stop = jest.fn(() => {
    p.startGenRef.current++;
    p.lifecycleCleanupRef.current?.();
    p.leaseHeartbeatRef.current?.close();
    p.pcRef.current?.close(); track.stop();
  });
});
afterEach(() => { p.lifecycleCleanupRef.current?.(); jest.clearAllTimers(); jest.useRealTimers(); });

test("connection failure stops media and requests recovery on the same event", async () => {
  await connectRealtimeVoice(p);
  pc.connectionState = "failed";
  pc.dispatchEvent(new Event("connectionstatechange"));
  expect(p.stop).toHaveBeenCalledWith("webrtc_connection_failed");
  expect(track.stop).toHaveBeenCalled();
  expect(p.onEndCall).toHaveBeenCalledWith({ retry: true, reason: "webrtc_connection_failed" });
  expect(p.postAriaEvent).not.toHaveBeenCalledWith("dismissed");
});

test("lost mic requests recovery instead of closing the resident event", async () => {
  await connectRealtimeVoice(p);
  track.dispatchEvent(new Event("ended"));
  expect(p.onEndCall).toHaveBeenCalledWith({ retry: true, reason: "microphone_ended" });
});

test("heartbeat rejection before media capture never opens the microphone", async () => {
  heartbeatOK = false;
  await connectRealtimeVoice(p);
  expect(navigator.mediaDevices.getUserMedia).not.toHaveBeenCalled();
  expect(p.stop).toHaveBeenCalledWith("lease_rejected");
});

test("late canceled mint releases its own claim and never opens media", async () => {
  let finish;
  fetch.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
  const work = connectRealtimeVoice(p);
  const oldSid = p.sessionIdRef.current;
  p.startGenRef.current++;
  p.sessionIdRef.current = "new_owner";
  finish(response({ value: "fake" }));
  await work;
  expect(p.releaseLease).toHaveBeenCalledWith("isolated_room", oldSid, expect.objectContaining({ activation_id: "cycle" }));
  expect(navigator.mediaDevices.getUserMedia).not.toHaveBeenCalled();
});

test("mic denial releases claimed room and presents a recoverable error", async () => {
  navigator.mediaDevices.getUserMedia.mockRejectedValue(new Error("permission denied"));
  await connectRealtimeVoice(p);
  expect(p.releaseLease).toHaveBeenCalledWith("isolated_room", p.sessionIdRef.current, expect.any(Object));
  expect(p.setStatus).toHaveBeenCalledWith("error");
  expect(p.postAriaEvent).not.toHaveBeenCalledWith("dismissed");
});
