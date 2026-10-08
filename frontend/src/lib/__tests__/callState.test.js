import { callState, wasConnected } from "../callState";

test("ringing and requested never read as answered", () => {
  expect(callState("ringing").label).toMatch(/not answered/i);
  expect(callState("requested").label).toMatch(/not dialing/i);
});

test("an ended call is connected only if its history says so", () => {
  expect(wasConnected({ state: "ended", history: [{ state: "requested" }, { state: "ringing" }, { state: "ended" }] })).toBe(false);
  expect(wasConnected({ state: "ended", history: [{ state: "ringing" }, { state: "connected" }, { state: "ended" }] })).toBe(true);
});

test("unknown state degrades honestly", () => {
  expect(callState("weird").label).toBe("weird");
});
