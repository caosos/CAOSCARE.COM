// Pure text for one task's facts (#168), shared by the department queue row
// and "My tasks today". The simulated clock comes only from the server's
// `simulation` block on GET /tasks/{id}/detail (backend
// simulation/community_task_simulation.py); a fact it does not carry is
// shown as "unknown", never filled in. Real receipt time is always shown
// next to simulated time, never replaced by it.

const UNKNOWN = "unknown";
const words = (s) => (s || "").replace(/_/g, " ");
const mins = (n) => (n == null ? UNKNOWN : `${n} min`);
const expected = (sim) => (sim.expected_work_minutes == null ? UNKNOWN : `~${sim.expected_work_minutes} min`);
const simAt = (at) => (at ? `Day ${at.day} ${at.hh_mm}` : UNKNOWN);

// The next permitted step under the server's work rules: a waiting request is
// claimed or started; only a request in progress is completed, with what was done.
export function nextStepText(t) {
  if (!t) return UNKNOWN;
  if (t.status === "in_progress") return "complete it with what was done";
  if (t.status === "pending") return "claim or start it when you begin the work";
  return "none · this request is closed";
}

// Labelled lines for a simulated ticket, or [] for a real task (no block).
export function simulationLines(sim, t, clock) {
  if (!sim) return [];
  if (sim.run_found === false) {
    return [["Simulation", "the run for this ticket is not on record; simulated times unknown"],
            ["Expected", expected(sim)]];
  }
  const lines = [["Requested (sim)", `${simAt(sim.requested)} · receipt time ${clock(t?.created_at) || UNKNOWN}`],
                 ["Expected", expected(sim)]];
  const reason = sim.wait_reason && sim.wait_reason !== "none" ? ` (${words(sim.wait_reason)})` : "";
  if (sim.started) {
    lines.push(["Waited", `${mins(sim.waiting_minutes)}${reason} · started ${simAt(sim.started)}`]);
    lines.push([sim.finished ? "Worked" : "Working",
                `${mins(sim.working_minutes)}${sim.finished ? ` · finished ${simAt(sim.finished)}` : ""}`]);
  } else if (t?.status === "pending") {
    lines.push(["Waiting", `${mins(sim.waiting_minutes)}${reason} · not started in simulated time`]);
  } else {
    lines.push(["Simulated work", "not recorded in simulated time · see the real times"]);
  }
  // v9: minutes per blocker over the whole wait (server: community_wait_blockers), when recorded
  const parts = Object.entries(sim.wait_breakdown || {}).filter(([, m]) => m > 0);
  if (parts.length) lines.push(["Wait by cause", parts.map(([why, m]) => `${m} min ${words(why)}`).join(" · ")]);
  if (sim.called_in_on_call) lines.push(["Called in", "the on-call worker was called in for this ticket"]);
  const raiser = sim.raised_by?.name || UNKNOWN;
  lines.push(["Raised by", `${raiser} (${sim.origin?.label || UNKNOWN})`]);
  lines.push(["Sim clock", `${simAt(sim.now)}${sim.run_state ? ` · run ${words(sim.run_state).toLowerCase()}` : ""}`]);
  return lines;
}
