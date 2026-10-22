import { spokenLightCommand, powerDirectionMismatch } from "../powerDirection";
import { temperatureRequestIsGrounded } from "../realtimeDeviceTools";
import { menuToolMessage } from "../communityServices";

// Room 214, 2026-10-21 CDT - exact transcripts from the calls.
test("rt_3bfuhkov 07:11 / rt_tbfytpqr 15:52: a plain spoken 'turn on' is recognised (the refusal then names it)", () => {
  expect(powerDirectionMismatch("off", "Turn on the desk lamp, please.", "desk lamp")).toMatch(/on or off/);
  expect(spokenLightCommand("Turn on the desk lamp, please.")).toBe("on");
  expect(spokenLightCommand("Turn on the overhead light")).toBe("on");
  expect(spokenLightCommand("Turn the overhead light on.")).toBe("on");
  expect(spokenLightCommand("Aria, turn the desk lamp off.")).toBe("off");
});

test("anything less than a plain light command still gets the safety question, never a guess", () => {
  for (const t of ["Don't turn off the lamp.", "Should I turn the light on?", "Turn it on.", "Overhead line",
                   "If it gets dark, turn on the lamp", "Turn on the TV", ""]) {
    expect(spokenLightCommand(t)).toBeNull();
  }
});

test("rt_r7yjpasv 06:14: 'Give me a turn.' does not authorize a thermostat setpoint", () => {
  expect(temperatureRequestIsGrounded("Give me a turn.")).toBe(false);
  for (const t of ["Make it 70.", "It's cold in here.", "Turn the AC down.", "Yes.", "Seventy-two degrees please."]) {
    expect(temperatureRequestIsGrounded(t)).toBe(true);
  }
});

test("rt_d3ahe1bf 19:33: the empty-menu result separates the spoken fact from instructions", () => {
  const m = menuToolMessage([], { mealPeriod: "dinner", date: "2026-10-21" });
  expect(m).toMatch(/^No approved dinner is on file for /);
  expect(m).toMatch(/Say only that, in your own words/);
  expect(m).toMatch(/Instructions for you, never to be said aloud/);
});
