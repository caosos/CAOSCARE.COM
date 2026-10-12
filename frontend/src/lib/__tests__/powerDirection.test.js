import { heardPowerDirection, powerDirectionMismatch } from "../powerDirection";

// Real Room 214 transcripts where the model's on/off disagreed with what was said.
describe("heard power direction", () => {
  test("reads a clear on or off", () => {
    expect(heardPowerDirection("Turn on my overhead light, please.")).toBe("on");
    expect(heardPowerDirection("Can you turn my overhead light on please?")).toBe("on");
    expect(heardPowerDirection("Can you shut off my lights?")).toBe("off");
    expect(heardPowerDirection("Turn off the desk lamp.")).toBe("off");
  });
  test("mixed, negated or missing direction is unknown", () => {
    expect(heardPowerDirection("turn the desk lamp off and the overhead on")).toBe(null);
    expect(heardPowerDirection("Don't turn it on.")).toBe(null);
    expect(heardPowerDirection("Overhead line")).toBe(null);
    expect(heardPowerDirection("")).toBe(null);
  });
});

describe("power direction mismatch", () => {
  test("refuses an action opposite to what was heard (2026-10-10, 10-12 Room 214)", () => {
    expect(powerDirectionMismatch("off", "Turn on my overhead light, please.")).toMatch(/on or off/);
    expect(powerDirectionMismatch("on", "Turn off the desk lamp.")).toMatch(/on or off/);
  });
  test("refuses a power change when nothing in the sentence asks for one (2026-10-12 02:04 false wake)", () => {
    expect(powerDirectionMismatch("off", "Overhead line")).toMatch(/on or off/);
  });
  test("allows matching, ambiguous-but-plausible, and non-power requests", () => {
    expect(powerDirectionMismatch("on", "Turn on my overhead light, please.")).toBe(null);
    expect(powerDirectionMismatch("off", "turn the desk lamp off and the overhead on")).toBe(null);
    expect(powerDirectionMismatch("on", "Can you switch the lamp for me?")).toBe(null);
    expect(powerDirectionMismatch(undefined, "Make it green")).toBe(null);
    expect(powerDirectionMismatch("off", "Yes.")).toBe(null);   // confirming Aria's own question
    expect(powerDirectionMismatch("off", "It doesn't matter, just do it.")).toBe(null);
    expect(powerDirectionMismatch("on", "I am feeling well, thank you.")).toMatch(/on or off/);   // 2026-10-09 15:03, ungrounded
    expect(powerDirectionMismatch("off", "")).toBe(null);   // transcript missing: not blocked
    expect(powerDirectionMismatch("on", "the overhead one", "light", { answering: true })).toBe(null);   // reply to "which light?"
    expect(powerDirectionMismatch("off", "the overhead one, turn it on", "light", { answering: true })).toMatch(/on or off/);
  });
});
