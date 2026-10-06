import {
  agentState, canCommand, commandSummary, known, newClientCommandId, orderChain, receiptTrust,
  validateInstruction, MAX_INSTRUCTION, UNKNOWN,
} from "../agentOps";

describe("agentState / known", () => {
  test("unbound agents read OFFLINE, missing status reads UNKNOWN", () => {
    expect(agentState({ status: { state: "offline" } }).label).toBe("OFFLINE");
    expect(agentState({}).label).toBe(UNKNOWN);
    expect(agentState({ status: { state: "online", simulated: true, adapter: "mock" } }))
      .toEqual({ label: "ONLINE", tone: "ok", simulated: true, adapter: "mock" });
  });
  test("unknown fields are shown as UNKNOWN, never blank", () => {
    expect(known(null)).toBe(UNKNOWN);
    expect(known("")).toBe(UNKNOWN);
    expect(known("pilot/x")).toBe("pilot/x");
  });
});

describe("canCommand", () => {
  test("only a bound, reachable agent can be commanded", () => {
    expect(canCommand({ binding_id: "mock-test", status: { state: "online" } })).toBe(true);
    expect(canCommand({ binding_id: null, status: { state: "offline" } })).toBe(false);
    expect(canCommand({ binding_id: "x", status: { state: "offline" } })).toBe(false);
  });
});

describe("validateInstruction", () => {
  test("mirrors the backend limits", () => {
    expect(validateInstruction("")).toMatch(/Enter/);
    expect(validateInstruction("   ")).toMatch(/Enter/);
    expect(validateInstruction("x".repeat(MAX_INSTRUCTION + 1))).toMatch(/under/);
    expect(validateInstruction("ls\u001b[2J")).toMatch(/control/);
    expect(validateInstruction("line one\n\tline two")).toBeNull();
  });
});

test("client command ids are unique and long enough for the backend", () => {
  const a = newClientCommandId();
  const b = newClientCommandId();
  expect(a).not.toBe(b);
  expect(a.length).toBeGreaterThanOrEqual(8);
});

describe("receiptTrust", () => {
  test("an agent self-report is never verified", () => {
    expect(receiptTrust({ result_label: "verified" })).toBe("verified");
    expect(receiptTrust({ result_label: "simulated" })).toBe("simulated");
    expect(receiptTrust({ result_label: "unverified" })).toBe("unverified");
    expect(receiptTrust({ result_label: null })).toBe("unverified");
    expect(receiptTrust({ status: "failed" })).toBe("failed");
  });
});

test("receipt chain is ordered by parent link, origin first", () => {
  const rows = [
    { receipt_id: "c", parent_receipt_id: "b", created_at: "3" },
    { receipt_id: "a", parent_receipt_id: null, created_at: "1" },
    { receipt_id: "b", parent_receipt_id: "a", created_at: "2" },
  ];
  expect(orderChain(rows).map((r) => r.receipt_id)).toEqual(["a", "b", "c"]);
});

test("commandSummary shows the reply or the failure", () => {
  expect(commandSummary({ status: "acknowledged", instruction: "hi", last_message: "got it",
    status_log: [{}, {}, {}] })).toEqual({ status: "acknowledged", asked: "hi", reply: "got it", steps: 3 });
  expect(commandSummary({ status: "failed", instruction: "hi",
    status_log: [{ to_status: "queued" }, { to_status: "failed", note: "no inbox" }] }).reply).toBe("no inbox");
});
