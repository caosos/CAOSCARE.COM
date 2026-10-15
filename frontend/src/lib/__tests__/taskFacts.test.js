/** #168: a task's simulated clock is told from the server's simulation block only; anything missing reads "unknown". */
import { nextStepText, simulationLines } from "../taskFacts";

const clock = (iso) => (iso ? `real ${iso.slice(11, 16)}` : null);
const at = (day, hh_mm) => ({ day, hh_mm });
const base = { run_found: true, run_state: "RUNNING", expected_work_minutes: 3, origin: { label: "Scheduled routine" },
               raised_by: { name: "SIM - Kitchen Aide 02" }, now: at(1, "10:00"), requested: at(1, "07:30"),
               started: null, finished: null, wait_reason: null, waiting_minutes: 150, working_minutes: null };
const text = (lines) => Object.fromEntries(lines);

test("real tasks carry no simulation lines", () => {
  expect(simulationLines(null, { status: "pending" }, clock)).toEqual([]);
});

test("a waiting ticket: simulated request next to receipt time, expected duration, wait so far, who raised it", () => {
  const l = text(simulationLines(base, { status: "pending", created_at: "2026-10-14T15:02:00Z" }, clock));
  expect(l["Requested (sim)"]).toBe("Day 1 07:30 · receipt time real 15:02");
  expect(l.Expected).toBe("~3 min");
  expect(l.Waiting).toBe("150 min · not started in simulated time");
  expect(l["Raised by"]).toBe("SIM - Kitchen Aide 02 (Scheduled routine)");
  expect(l["Sim clock"]).toBe("Day 1 10:00 · run running");
});

test("a ticket in progress shows its wait (with reason) and the work so far; a finished one its finish", () => {
  const working = text(simulationLines({ ...base, started: at(1, "07:50"), waiting_minutes: 20, working_minutes: 4,
                                         wait_reason: "waiting_for_available_staff" }, null, clock));
  expect(working.Waited).toBe("20 min (waiting for available staff) · started Day 1 07:50");
  expect(working.Working).toBe("4 min");
  expect(working["Requested (sim)"]).toBe("Day 1 07:30 · receipt time unknown");
  const done = text(simulationLines({ ...base, started: at(1, "07:35"), finished: at(1, "07:38"), wait_reason: "none",
                                      waiting_minutes: 5, working_minutes: 3 }, null, clock));
  expect(done.Waited).toBe("5 min · started Day 1 07:35");
  expect(done.Worked).toBe("3 min · finished Day 1 07:38");
});

test("unrecorded facts are stated as unknown, never invented", () => {
  const l = text(simulationLines({ ...base, requested: null, raised_by: null, expected_work_minutes: null, waiting_minutes: null }, { status: "pending" }, clock));
  expect(l["Requested (sim)"]).toBe("unknown · receipt time unknown");
  expect(l["Raised by"]).toBe("unknown (Scheduled routine)");
  expect(l.Expected).toBe("unknown");
  expect(l.Waiting).toBe("unknown · not started in simulated time");
  // Worked by real staff: no simulated start, so the simulated clock does not pretend there was one.
  const real = text(simulationLines(base, { status: "completed" }, clock));
  expect(real.Waiting).toBeUndefined();
  expect(real["Simulated work"]).toBe("not recorded in simulated time · see the real times");
  const missing = text(simulationLines({ run_found: false, expected_work_minutes: 8 }, null, clock));
  expect(missing.Simulation).toMatch(/not on record/);
});

test("next step follows the work rules", () => {
  expect(nextStepText({ status: "pending" })).toBe("claim or start it when you begin the work");
  expect(nextStepText({ status: "in_progress" })).toBe("complete it with what was done");
  expect(nextStepText({ status: "completed" })).toBe("none · this request is closed");
  expect(nextStepText({ status: "skipped" })).toBe("none · this request is closed");
});

test("v9: the wait is split by cause and a call-in is stated", () => {
  const l = text(simulationLines({ ...base, started: at(1, "18:40"), waiting_minutes: 70, working_minutes: 5,
                                   wait_reason: "waiting_for_on_call_response", called_in_on_call: true,
                                   wait_breakdown: { waiting_for_on_site_staff_on_call_only: 30, waiting_for_on_call_response: 40, none: 0 } },
                                 null, clock));
  expect(l["Wait by cause"]).toBe("30 min waiting for on site staff on call only · 40 min waiting for on call response");
  expect(l["Called in"]).toBe("the on-call worker was called in for this ticket");
  expect(text(simulationLines(base, { status: "pending" }, clock))["Wait by cause"]).toBeUndefined();
});
