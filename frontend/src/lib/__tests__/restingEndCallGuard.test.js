/**
 * Regression test for the mark_resting/end_call grounding guard
 * (docs/PROJECT_STATE.md, 2026-08-30 incident). Reproduces the exact live
 * failure verbatim: mark_resting fired on "No, I can't." (a resident
 * PROTESTING being left alone) and end_call fired on "It's gonna find
 * me." (a session-ending transcript with no semantic connection to
 * ending the call). Also confirms genuine dismissal/ending phrases still
 * work - a resident unable to be left alone or to end a call is a worse
 * failure than the one this guard fixes.
 */
process.env.REACT_APP_BACKEND_URL = "http://127.0.0.1:8000";
import { executeDeviceTool } from "../realtimeDeviceTools";

function ctx(lastUserText, overrides = {}) {
  return {
    resident_id: "res_test", room: "401", session_id: "rt_test",
    turn_suspect: false, last_user_text: lastUserText, ...overrides,
  };
}

test("real incident: mark_resting must NOT fire on 'No, I can't.'", async () => {
  const r = await executeDeviceTool({ name: "mark_resting", args: {}, ctx: ctx("No, I can't.") });
  expect(r.ok).toBe(false);
});

test("real incident: end_call must NOT fire on 'It's gonna find me.'", async () => {
  const r = await executeDeviceTool({ name: "end_call", args: { reason: "goodbye" }, ctx: ctx("It's gonna find me.") });
  expect(r.ok).toBe(false);
});

test.each([
  "They",
  "Yeah.",
  "I don't think.",
  "It is afternoon.",
])("mark_resting must NOT fire on ambiguous/unrelated turn: %s", async (text) => {
  const r = await executeDeviceTool({ name: "mark_resting", args: {}, ctx: ctx(text) });
  expect(r.ok).toBe(false);
});

test.each([
  "Be quiet for a minute.",
  "Let me rest.",
  "Give me some space.",
  "Don't talk for a while.",
  "I'm going to sleep.",
])("genuine dismissal still triggers mark_resting: %s", async (text) => {
  const r = await executeDeviceTool({ name: "mark_resting", args: {}, ctx: ctx(text) });
  expect(r.ok).toBe(true);
});

test.each([
  "That's all for now.",
  "That'll be all.",
  "Goodbye.",
  "I'm done.",
  "Go away.",
  "Hang up.",
])("genuine ending phrase still triggers end_call: %s", async (text) => {
  const r = await executeDeviceTool({ name: "end_call", args: { reason: "goodbye" }, ctx: ctx(text) });
  expect(r.ok).toBe(true);
});

test("existing turn_suspect guard still takes priority over the new check", async () => {
  const r = await executeDeviceTool({
    name: "end_call", args: { reason: "goodbye" },
    ctx: ctx("Goodbye.", { turn_suspect: true }),
  });
  expect(r.ok).toBe(false);
});

test("missing last_user_text does not fire either tool", async () => {
  const rest = await executeDeviceTool({ name: "mark_resting", args: {}, ctx: ctx("") });
  const end = await executeDeviceTool({ name: "end_call", args: { reason: "goodbye" }, ctx: ctx("") });
  expect(rest.ok).toBe(false);
  expect(end.ok).toBe(false);
});
