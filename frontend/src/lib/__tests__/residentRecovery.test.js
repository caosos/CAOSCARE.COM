import { createActivationPollGate } from "../residentActivationPoll";
import { createLeaseWatchdog } from "../realtimeLeaseWatchdog";

beforeEach(() => jest.useFakeTimers());
afterEach(() => { jest.clearAllTimers(); jest.useRealTimers(); });

const event = { alert_id: "same_event", activation_id: "cycle_1", press_count: 1 };

test("repeat presses do not queue a delayed session; a new cycle reactivates the SAME event", () => {
  const gate = createActivationPollGate();
  expect(gate.accept(event, true)).toBe(true);
  expect(gate.accept({ ...event, press_count: 5 }, false)).toBe(false);
  gate.finish();
  expect(gate.accept({ ...event, press_count: 5 }, true)).toBe(false);
  expect(gate.accept({ ...event, activation_id: "cycle_2", press_count: 6 }, true)).toBe(true);
});

test("failed connection retries same cycle with backoff; repeated failure is bounded", () => {
  const gate = createActivationPollGate();
  expect(gate.accept(event, true)).toBe(true);
  for (let n = 0; n < 6; n++) {
    gate.finish({ retry: true });
    expect(gate.accept(event, true)).toBe(false);
    jest.advanceTimersByTime(30000);
    expect(gate.accept(event, true)).toBe(n < 5);
  }
  expect(gate.accept({ ...event, press_count: 2 }, true)).toBe(true);
});

test("legacy alerts without a new activation cannot launch stale audio", () => {
  expect(createActivationPollGate().accept({ alert_id: "old" }, true)).toBe(false);
});

test("heartbeat rejection stops the owner immediately", async () => {
  const lost = jest.fn();
  const w = createLeaseWatchdog({ heartbeat: async () => false, onLost: lost });
  expect(await w.beat()).toBe(false);
  expect(lost).toHaveBeenCalledWith("lease_rejected");
  jest.advanceTimersByTime(60000);
  expect(lost).toHaveBeenCalledTimes(1);
});

test("a backend partition cannot indefinitely renew audio ownership", async () => {
  const lost = jest.fn();
  const w = createLeaseWatchdog({ heartbeat: jest.fn().mockRejectedValue(new Error("offline")), onLost: lost });
  await w.beat();
  jest.advanceTimersByTime(29999);
  expect(lost).not.toHaveBeenCalled();
  jest.advanceTimersByTime(1);
  expect(lost).toHaveBeenCalledWith("lease_heartbeat_expired");
});

test("late successful heartbeat cannot revive an expired owner", async () => {
  let resolve;
  const lost = jest.fn();
  const w = createLeaseWatchdog({ heartbeat: () => new Promise(r => { resolve = r; }), onLost: lost });
  const pending = w.beat();
  jest.advanceTimersByTime(30000);
  resolve(true);
  expect(await pending).toBe(false);
  expect(lost).toHaveBeenCalledTimes(1);
});
