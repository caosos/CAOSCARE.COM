import { createEndController } from "../endController";
import { GOODBYE_INSTRUCTIONS } from "../endController";
import { executeDeviceTool } from "../realtimeDeviceTools";

// Room 214 2026-10-12 19:19: Aria's goodbye was already playing when her end_call was granted;
// audio_started had fired before "ending", so the controller thought no goodbye was heard and the
// browser's own voice said "Goodbye." too - two voices.
const make = (speak) => createEndController({ send: () => {}, stop: () => {}, onEndCall: () => {}, log: () => {}, speak });

test("the model closing instruction permits exactly one normal sentence", () => {
  expect(GOODBYE_INSTRUCTIONS).toContain('Say exactly and only: "Okay, bye for now."');
  expect(GOODBYE_INSTRUCTIONS).toContain("No explanation");
});

test("the successful end tool returns the same exact normal sentence", async () => {
  const result = await executeDeviceTool({ name: "end_call", args: {}, ctx: { session_id: "exact-bye", last_user_text: "Goodbye." } });
  expect(result).toEqual({ ok: true, message: "Okay, bye for now." });
});

test("a goodbye already playing when ending begins counts as heard - no second voice", () => {
  const speak = jest.fn(() => true);
  const c = make(speak);
  c.noteAudioStarted();          // goodbye starts playing
  c.markEnding(true);            // end_call granted while she is speaking
  c.finish("resident_end_call", "end_call_tool");
  expect(speak).not.toHaveBeenCalled();
});

test("when nothing was heard, the local fallback still speaks", () => {
  const speak = jest.fn(() => false);
  const c = make(speak);
  c.markEnding(false);
  c.finish("resident_end_call", "end_call_tool");
  expect(speak).toHaveBeenCalledWith("Goodbye.", expect.any(Function));
});
