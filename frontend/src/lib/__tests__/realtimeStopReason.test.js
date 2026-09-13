process.env.REACT_APP_BACKEND_URL = "http://localhost:8000";
jest.mock("../api", () => ({ API: "http://localhost:8000/api" }));
jest.mock("../realtimeConnection", () => ({ connectRealtimeVoice: jest.fn() }));
jest.mock("../realtimeDiagnostics", () => ({ logRealtimeEvent: jest.fn() }));
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { useRealtimeVoice } from "../useRealtimeVoice";
let root, voice, host;
function Probe() { voice = useRealtimeVoice({ alertId: "event", activationId: "cycle" }); return null; }
beforeEach(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  fetch = jest.fn().mockResolvedValue({ ok: true });
  host = document.createElement("div"); root = createRoot(host);
  act(() => root.render(<Probe />));
});
afterEach(() => act(() => root.unmount()));
test("UI End call explicitly consumes activation; unmount does not", () => {
  act(() => voice.stop("ui_end_call_button"));
  const writes = fetch.mock.calls.filter(([url]) => url.endsWith("/aria-event"));
  expect(writes).toHaveLength(1);
  expect(JSON.parse(writes[0][1].body)).toMatchObject({ event: "dismissed", activation_id: "cycle" });
});
test("connection loss never reports resident dismissal", () => {
  act(() => voice.stop("webrtc_connection_failed"));
  expect(fetch.mock.calls.filter(([url]) => url.endsWith("/aria-event"))).toHaveLength(0);
});
