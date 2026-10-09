import { createFarewellWatch, FAREWELL } from "../farewellWatch";

const mk = () => { const log = jest.fn(); return { log, w: createFarewellWatch(log) }; };
const callOut = { id: "r1", output: [{ type: "function_call", name: "end_call" }] };

test("real incident: 'Goodnight, Michael...' with no end_call is logged", () => {
  const { log, w } = mk();
  w.onAssistantTranscript("Goodnight, Michael. I'll be here whenever you need me.");
  expect(w.onResponseDone({ id: "r1", output: [{ type: "message" }] })).toBe(true);
  expect(log).toHaveBeenCalledWith("farewell_without_end_call", expect.objectContaining({ responseId: "r1" }));
});

test("farewell with end_call in the same response is not logged", () => {
  const { log, w } = mk();
  w.onAssistantTranscript("Goodbye for now.");
  expect(w.onResponseDone(callOut)).toBe(false);
  expect(log).not.toHaveBeenCalled();
});

test("non-farewell speech and a later response do not log; state resets", () => {
  const { log, w } = mk();
  w.onAssistantTranscript("The light is on.");
  expect(w.onResponseDone({ output: [] })).toBe(false);
  w.onAssistantTranscript("Take care.");
  w.onResponseDone(callOut);
  expect(w.onResponseDone({ output: [] })).toBe(false);
  expect(log).not.toHaveBeenCalled();
  expect(FAREWELL.test("see you")).toBe(false);
});
