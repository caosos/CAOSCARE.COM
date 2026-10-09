import { createClaimInterrupter, verifiedConfirmationEvent } from "../claimInterrupter";

function rig(mode = "on") {
  const sent = [], logs = [];
  let t = 1000;
  const ci = createClaimInterrupter({ send: (e) => sent.push(e), log: (type, d) => logs.push([type, d]), mode, now: () => (t += 50) });
  const say = (text, id = "r1") => { for (const w of text.match(/.{1,6}/g)) ci.onTranscriptDelta({ response_id: id, delta: w }); };
  return { ci, sent, logs, say };
}
const types = (sent) => sent.map((e) => e.type);

test("false claim with no tool: cancel, clear, corrective once", () => {
  const { ci, sent, say } = rig();
  ci.onUserTurn(); ci.onResponseCreated("r1");
  say("Sure. I'll let the team know you asked.");
  expect(types(sent)).toEqual(["response.cancel", "output_audio_buffer.clear", "response.create"]);
  expect(sent[0].response_id).toBe("r1");
  expect(sent[2].response.instructions).toMatch(/nothing has been sent/);
  say(" More words after.");   // further deltas of the cut response ignored
  expect(sent).toHaveLength(3);
});

test("waits for the sentence terminator", () => {
  const { ci, sent, say } = rig();
  ci.onUserTurn(); ci.onResponseCreated("r1");
  say("I'll let the team know");
  expect(sent).toHaveLength(0);
  say(".");
  expect(sent).toHaveLength(3);
});

test("same sentence after an ok tool result is untouched", () => {
  const { ci, sent, say } = rig();
  ci.onUserTurn(); ci.onToolStart("request_staff_help");
  ci.onToolResult("request_staff_help", { ok: true, message: "sent" });
  ci.onResponseCreated("r2");
  say("I've told the nurse.", "r2");
  expect(sent).toHaveLength(0);
});

test("tool in flight (result arrives after the sentence started) is untouched", () => {
  const { ci, sent, say } = rig();
  ci.onUserTurn(); ci.onResponseCreated("r1");
  ci.onToolStart("request_staff_help");
  say("I've told the nurse.");
  expect(sent).toHaveLength(0);
  ci.onToolResult("request_staff_help", { ok: true });
  expect(sent).toHaveLength(0);
});

test("failed tool result does not back a claim", () => {
  const { ci, sent, say } = rig();
  ci.onUserTurn(); ci.onToolStart("request_staff_help");
  ci.onToolResult("request_staff_help", { ok: false });
  ci.onResponseCreated("r2");
  say("I've notified the nurse.", "r2");
  expect(types(sent)).toContain("response.cancel");
});

test("two claims in one turn: one corrective only; corrective response is not re-interrupted", () => {
  const { ci, sent, say } = rig();
  ci.onUserTurn(); ci.onResponseCreated("r1");
  say("I'll tell the staff. I've also told the nurse.");
  expect(sent.filter((e) => e.type === "response.create")).toHaveLength(1);
  ci.onResponseCreated("r2");   // the corrective response
  say("I've sent nothing, I'll let the team know if you like.", "r2");
  ci.onResponseCreated("r3");
  say("I've told the nurse.", "r3");
  expect(sent.filter((e) => e.type === "response.create")).toHaveLength(1);
});

test("emergency / live-line path is never interrupted", () => {
  const { ci, sent, say } = rig();
  ci.onUserTurn(); ci.onToolStart("call_for_help");
  ci.onToolResult("call_for_help", { ok: false });
  ci.onResponseCreated("r2");
  say("I've alerted the nurse.", "r2");
  expect(sent).toHaveLength(0);
});

test("questions and conditionals are not claims", () => {
  const { ci, sent, say } = rig();
  ci.onUserTurn(); ci.onResponseCreated("r1");
  say("Should I tell the nurse? Would you like me to let the team know? I'll let the team know if you want.");
  expect(sent).toHaveLength(0);
});

test("unsupported weather and lookup claims are cut; supported ones are not", () => {
  let r = rig(); r.ci.onUserTurn(); r.ci.onResponseCreated("r1");
  r.say("It's cool and clear tonight.");
  expect(types(r.sent)).toContain("response.cancel");
  r = rig(); r.ci.onUserTurn(); r.ci.onResponseCreated("r1");
  r.say("I did check the internet.");
  expect(types(r.sent)).toContain("response.cancel");
  r = rig(); r.ci.onUserTurn(); r.ci.onToolStart("get_weather"); r.ci.onToolResult("get_weather", { ok: true });
  r.ci.onResponseCreated("r2"); r.say("It's cool and clear tonight.", "r2");
  expect(r.sent).toHaveLength(0);
  r = rig(); r.ci.onUserTurn(); r.ci.onToolStart("research_topic"); r.ci.onToolResult("research_topic", { ok: true, live: false });
  r.ci.onResponseCreated("r2"); r.say("I looked that up.", "r2");
  expect(types(r.sent)).toContain("response.cancel");
});

test("a new resident turn re-arms; shadow mode logs timing and sends nothing; off is inert", () => {
  let r = rig(); r.ci.onUserTurn(); r.ci.onResponseCreated("r1"); r.say("I've told the nurse.");
  r.ci.onResponseCreated("corrective");
  r.ci.onUserTurn(); r.ci.onResponseCreated("r2"); r.say("I've told the nurse.", "r2");
  expect(r.sent.filter((e) => e.type === "response.cancel")).toHaveLength(2);
  r = rig("shadow"); r.ci.onUserTurn(); r.ci.onResponseCreated("r1"); r.say("I've told the nurse.");
  expect(r.sent).toHaveLength(0);
  expect(r.logs[0][0]).toBe("claim_interrupter_would_cut");
  expect(r.logs[0][1].meta.ms_since_response_created).toBeGreaterThan(0);
  r = rig("off"); r.ci.onUserTurn(); r.ci.onResponseCreated("r1"); r.say("I've told the nurse.");
  expect(r.sent).toHaveLength(0); expect(r.logs).toHaveLength(0);
});

test("verified confirmation carries the tool message; not for failures or non-action tools", () => {
  const e = verifiedConfirmationEvent("request_staff_help", { ok: true, message: "Request sent to nursing." });
  expect(e.response.instructions).toMatch(/Request sent to nursing\./);
  expect(verifiedConfirmationEvent("request_staff_help", { ok: false, message: "x" })).toBeNull();
  expect(verifiedConfirmationEvent("get_weather", { ok: true, message: "x" })).toBeNull();
});
