/**
 * Regression test for the 2026-09-06 break-test Defect 2: an already-mounted
 * kiosk never re-woke Aria on a LATER pendant press of the same open event,
 * because it remembered only the last alert_id it engaged and the Level 1
 * resident-event model made a repeat press reactivate the SAME alert_id.
 * See docs/LEVEL1_BREAKTEST.md (invariant 6).
 */
import { evaluateEmergencyWake } from "../kioskEmergencyWake";

const alert = (id, pc) => ({ alert_id: id, press_count: pc });

test("first ever open event wakes the kiosk", () => {
  const r = evaluateEmergencyWake(alert("a1", 1), null, "idle");
  expect(r.wake).toBe(true);
  expect(r.seen).toEqual({ id: "a1", pressCount: 1 });
  expect(r.reason).toBe("first_sight");
});

test("every decision carries a reason for the observability log", () => {
  expect(evaluateEmergencyWake(null, null, "idle").reason).toBe("rejected_no_alert");
  expect(evaluateEmergencyWake(alert("a1", 1), { id: "a1", pressCount: 1 }, "idle").reason).toBe("rejected_same_state");
  expect(evaluateEmergencyWake(alert("a1", 2), { id: "a1", pressCount: 1 }, "idle").reason).toBe("press_count_advanced");
  expect(evaluateEmergencyWake(alert("a2", 1), { id: "a1", pressCount: 9 }, "idle").reason).toBe("new_alert_id");
  expect(evaluateEmergencyWake(alert("a1", 1), { id: "a1", pressCount: 1 }, "chatting").reason).toBe("rejected_in_call");
});

test("no alert -> no wake, marker untouched", () => {
  const seen = { id: "a1", pressCount: 1 };
  const r = evaluateEmergencyWake(null, seen, "idle");
  expect(r.wake).toBe(false);
  expect(r.seen).toBe(seen);
});

test("same alert, same press_count, kiosk idle -> no re-wake (no relaunch loop)", () => {
  const r = evaluateEmergencyWake(alert("a1", 1), { id: "a1", pressCount: 1 }, "idle");
  expect(r.wake).toBe(false);
});

test("LATER press reactivates the SAME open event -> kiosk re-wakes (invariant 6)", () => {
  // Session ended (dismissed), kiosk idle again, resident presses pendant:
  // record_resident_activation coalesces onto the same alert_id and bumps
  // press_count from 1 -> 2 and resets activation_consumed_at.
  const r = evaluateEmergencyWake(alert("a1", 2), { id: "a1", pressCount: 1 }, "idle");
  expect(r.wake).toBe(true);
  expect(r.seen).toEqual({ id: "a1", pressCount: 2 });
});

test("a genuinely new event (new alert_id) after staff resolve wakes the kiosk", () => {
  const r = evaluateEmergencyWake(alert("a2", 1), { id: "a1", pressCount: 5 }, "idle");
  expect(r.wake).toBe(true);
  expect(r.seen).toEqual({ id: "a2", pressCount: 1 });
});

test("presses made DURING a call only advance the watermark, never wake a 2nd session", () => {
  // Aria is live (callState !== idle). press_count climbs 1 -> 3 mid-call.
  let seen = { id: "a1", pressCount: 1 };
  ({ seen } = evaluateEmergencyWake(alert("a1", 2), seen, "chatting"));
  const mid = evaluateEmergencyWake(alert("a1", 3), seen, "chatting");
  expect(mid.wake).toBe(false);
  expect(mid.seen).toEqual({ id: "a1", pressCount: 3 });
  // Call ends, kiosk idle, poll sees the same count -> must NOT relaunch.
  const after = evaluateEmergencyWake(alert("a1", 3), mid.seen, "idle");
  expect(after.wake).toBe(false);
});

test("X-button ends the call WITHOUT consuming the activation -> alert still returned, but no relaunch", () => {
  // activation_consumed_at was never set (X-button reason isn't a dismissal),
  // so active-emergency keeps returning the alert at the same press_count.
  const seen = { id: "a1", pressCount: 2 };
  const r = evaluateEmergencyWake(alert("a1", 2), seen, "idle");
  expect(r.wake).toBe(false);
});
