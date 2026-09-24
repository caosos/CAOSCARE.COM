import { connectWakeWord, wakeUrlFromSearch, DEFAULT_WAKE_URL } from "../wakeWordClient";

class FakeWS {
  static instances = [];
  constructor(url) { this.url = url; this.readyState = 0; this.sent = []; FakeWS.instances.push(this); }
  send(d) { this.sent.push(JSON.parse(d)); }
  close() { this.readyState = 3; this.onclose?.(); }
  open() { this.readyState = 1; this.onopen?.(); }
  receive(obj) { this.onmessage?.({ data: JSON.stringify(obj) }); }
}

beforeEach(() => { FakeWS.instances = []; jest.useFakeTimers(); });
afterEach(() => jest.useRealTimers());

test("wake is opt-in per endpoint via the page URL", () => {
  expect(wakeUrlFromSearch("")).toBeNull();
  expect(wakeUrlFromSearch("?wake=0")).toBeNull();
  expect(wakeUrlFromSearch("?wake=1")).toBe(DEFAULT_WAKE_URL);
  expect(wakeUrlFromSearch("?wake=ws://127.0.0.1:9000")).toBe("ws://127.0.0.1:9000");
});

test("state set before the socket opens is delivered on open", () => {
  const c = connectWakeWord({ url: "ws://x", WebSocketImpl: FakeWS });
  c.setState("listening", "call_state_idle");
  const ws = FakeWS.instances[0];
  expect(ws.sent).toEqual([]);
  ws.open();
  expect(ws.sent).toEqual([{ type: "state", state: "listening", reason: "call_state_idle" }]);
  c.close();
});

test("wake frames reach onMessage; malformed frames are ignored", () => {
  const got = [];
  const c = connectWakeWord({ url: "ws://x", WebSocketImpl: FakeWS, onMessage: (m) => got.push(m) });
  const ws = FakeWS.instances[0];
  ws.open();
  ws.onmessage({ data: "not json" });
  ws.receive({ type: "wake", wake_id: "wake_1" });
  expect(got).toEqual([{ type: "wake", wake_id: "wake_1" }]);
  c.close();
});

test("reconnects after the detector drops and re-asserts the page state", () => {
  const c = connectWakeWord({ url: "ws://x", WebSocketImpl: FakeWS });
  FakeWS.instances[0].open();
  c.setState("conversation", "call_state_chatting");
  FakeWS.instances[0].onclose();          // detector restarted
  jest.advanceTimersByTime(1000);
  const ws2 = FakeWS.instances[1];
  expect(ws2).toBeDefined();
  ws2.open();
  expect(ws2.sent).toEqual([{ type: "state", state: "conversation", reason: "call_state_chatting" }]);
  c.close();
  jest.advanceTimersByTime(20000);
  expect(FakeWS.instances.length).toBe(2);  // no reconnect after close()
});
