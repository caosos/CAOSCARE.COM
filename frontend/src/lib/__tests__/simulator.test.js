import {
  actorKind, allowedControls, activeSimRequests, canonicalRefOf, castEntryFor, currentAction,
  describeStep, failures, mergeStream, orderChain, simClock,
} from "../simulator";

const rc = (id, parent, at, extra = {}) => ({ receipt_id: id, parent_receipt_id: parent, created_at: at, ...extra });

describe("allowedControls", () => {
  test("matches the scheduler's state machine", () => {
    expect(allowedControls("STOPPED")).toEqual({ start: true, pause: false, step: false, resume: false, stop: false });
    expect(allowedControls("RUNNING")).toEqual({ start: false, pause: true, step: false, resume: false, stop: true });
    expect(allowedControls("PAUSED")).toEqual({ start: false, pause: false, step: true, resume: true, stop: true });
    expect(allowedControls(undefined).start).toBe(true);
  });
});

describe("actorKind", () => {
  test("anything marked simulated is never shown as real", () => {
    expect(actorKind({ actor_type: "real-human", simulated: true })).toBe("simulated");
    expect(actorKind({ actor_type: "real-human", identity_basis: "synthetic" })).toBe("simulated");
    expect(actorKind({ actor_type: "simulated-agent" })).toBe("simulated");
  });
  test("real, system and unknown", () => {
    expect(actorKind({ actor_type: "real-human", simulated: false })).toBe("real");
    expect(actorKind({ actor_type: "system" })).toBe("system");
    expect(actorKind({})).toBe("unknown");
    expect(actorKind(null)).toBe("unknown");
  });
});

describe("orderChain / mergeStream", () => {
  test("parent links order a chain even when timestamps tie", () => {
    const same = "2026-10-04T10:00:00.000";
    const chain = [rc("c", "b", same), rc("a", null, same), rc("b", "a", same)];
    expect(orderChain(chain).map((r) => r.receipt_id)).toEqual(["a", "b", "c"]);
  });
  test("merges both chains newest first and labels the chain", () => {
    const run = [rc("r1", null, "2026-10-04T10:00:01"), rc("r2", "r1", "2026-10-04T10:00:04")];
    const req = [rc("q1", null, "2026-10-04T10:00:02"), rc("q2", "q1", "2026-10-04T10:00:03")];
    const out = mergeStream(run, req);
    expect(out.map((r) => r.receipt_id)).toEqual(["r2", "q2", "q1", "r1"]);
    expect(out.find((r) => r.receipt_id === "q1").chain).toBe("request");
    expect(out.find((r) => r.receipt_id === "r1").chain).toBe("run");
  });
  test("empty / missing input", () => {
    expect(mergeStream(undefined, null)).toEqual([]);
  });
});

describe("current action, failures, trace links", () => {
  const run = [
    rc("s", null, "1", { action_type: "sim_run_started" }),
    rc("x1", "s", "2", { action_type: "sim_step_executed", provider_refs: ["canon1"] }),
    rc("p", "x1", "3", { action_type: "sim_run_paused" }),
    rc("x2", "p", "4", { action_type: "sim_step_failed", status: "failed", provider_refs: [] }),
  ];
  test("current action is the latest step receipt, not a control", () => {
    expect(currentAction(run).receipt_id).toBe("x2");
    expect(currentAction([run[0]])).toBeNull();
  });
  test("failures include failed run receipts and refused starts", () => {
    const refused = [{ receipt_id: "ref1", status: "failed" }];
    expect(failures(run, refused).map((r) => r.receipt_id)).toEqual(["x2", "ref1"]);
  });
  test("a step receipt points to the canonical receipt that recorded the work", () => {
    expect(canonicalRefOf(run[1])).toBe("canon1");
    expect(canonicalRefOf(run[3])).toBeNull();
  });
});

describe("requests, cast, clock", () => {
  test("only open simulated requests are active", () => {
    const tasks = [
      { task_id: "a", simulated: true, status: "pending" },
      { task_id: "b", simulated: true, status: "completed" },
      { task_id: "c", simulated: false, status: "pending" },
      { task_id: "d", simulated: true, status: "in_progress" },
    ];
    expect(activeSimRequests(tasks).map((t) => t.task_id)).toEqual(["a", "d"]);
  });
  test("cast lookup and clock/step text", () => {
    const cast = { resident: { actor_id: "res_1" }, maintenance_tech: { actor_id: "sim:staff:maintenance-1" } };
    expect(castEntryFor(cast, "sim:staff:maintenance-1")).toBe(cast.maintenance_tech);
    expect(castEntryFor(cast, "nobody")).toBeNull();
    expect(simClock(25)).toBe("T+25 min");
    expect(simClock(85)).toBe("T+1 h 25 min");
    expect(describeStep({ actor: "maintenance_tech", action: "raise_request", at: 0 })).toBe("maintenance tech: raise request at T+0 min");
  });
});
