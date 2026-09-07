/**
 * activationClient — kiosk breadcrumb helper for the activation
 * observability stream (Level 1, 2026-09-07).
 */
process.env.REACT_APP_BACKEND_URL = "http://127.0.0.1:8000";

beforeEach(() => {
  jest.resetModules();
  jest.useFakeTimers();
  global.fetch = jest.fn(() => Promise.resolve({ ok: true }));
});
afterEach(() => {
  jest.useRealTimers();
  delete global.fetch;
});

test("clientInstanceId is stable within one page load", () => {
  const { clientInstanceId } = require("../activationClient");
  const a = clientInstanceId();
  expect(a).toBeTruthy();
  expect(clientInstanceId()).toBe(a);
});

test("a fresh module load (a reload) mints a new client instance id", () => {
  const id1 = require("../activationClient").clientInstanceId();
  jest.resetModules();
  const id2 = require("../activationClient").clientInstanceId();
  expect(id2).not.toBe(id1);
});

test("events are batched into one POST with the server shape", () => {
  const { logActivationClientEvent } = require("../activationClient");
  logActivationClientEvent("kiosk_mounted", { room: "214", kiosk_id: "kio_1" });
  logActivationClientEvent("poll_started", { room: "214", kiosk_id: "kio_1", data: { interval_ms: 3000 } });
  expect(global.fetch).not.toHaveBeenCalled();   // still buffered
  jest.advanceTimersByTime(900);

  expect(global.fetch).toHaveBeenCalledTimes(1);
  const [url, opts] = global.fetch.mock.calls[0];
  expect(url).toContain("/activation-events/client");
  const body = JSON.parse(opts.body);
  expect(body.events).toHaveLength(2);
  expect(body.events[0]).toMatchObject({ event: "kiosk_mounted", room: "214", kiosk_id: "kio_1" });
  expect(body.events[0].client_instance_id).toBeTruthy();
  expect(body.events[0].ts_client).toBeTruthy();
  expect(body.events[1]).toMatchObject({ event: "poll_started", data: { interval_ms: 3000 } });
});

test("telemetry failure never throws into the caller", () => {
  global.fetch = jest.fn(() => { throw new Error("network down"); });
  const { logActivationClientEvent } = require("../activationClient");
  expect(() => {
    logActivationClientEvent("wake_rejected", { room: "214" });
    jest.advanceTimersByTime(900);
  }).not.toThrow();
});
