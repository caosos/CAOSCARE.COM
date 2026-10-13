import { createEndController } from "../endController";

// Room 214 2026-10-12 19:19: Aria's goodbye was already playing when her end_call was granted;
// audio_started had fired before "ending", so the controller thought no goodbye was heard and the
// browser's own voice said "Goodbye." too - two voices.
const make = (speak) => createEndController({ send: () => {}, stop: () => {}, onEndCall: () => {}, log: () => {}, speak });

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
