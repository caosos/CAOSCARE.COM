import { createClaimGuard } from "../claimGuard";
import { shapeResearchResult, NOT_LIVE_PREFIX } from "../researchShape";
import { createFarewellWatch } from "../farewellWatch";

// Sanitized excerpts of session rt_dc5h0fi1 (docs/reports/2026-10-08-aria-untrue-claims-audit.md).
const run = (g, text, response = { output: [] }) => { g.onAssistantTranscript(text); return g.onResponseDone(response); };
const mk = () => { const log = jest.fn(); return { log, g: createClaimGuard(log) }; };
const UNSUPPORTED = "That's not something I can do yet, but I'll let the team know you asked.";
const WEATHER = "The weather in Conway, Arkansas tonight is cool and clear.";

test("action claim with no tool result is flagged", () => {
  const { log, g } = mk();
  g.onToolResult("get_current_time", { ok: true });
  expect(run(g, UNSUPPORTED)).toEqual(["unsupported_action_claim"]);
  expect(log).toHaveBeenCalledWith("unsupported_action_claim", { text: UNSUPPORTED });
});
test("same sentence after an ok request_staff_help is not flagged; a failed one is", () => {
  const a = mk(); a.g.onToolResult("request_staff_help", { ok: true });
  expect(run(a.g, UNSUPPORTED)).toEqual([]);
  const b = mk(); b.g.onToolResult("request_staff_help", { ok: false });
  expect(run(b.g, UNSUPPORTED)).toEqual(["unsupported_action_claim"]);
});
test("a new resident turn clears earlier results", () => {
  const { g } = mk(); g.onToolResult("request_staff_help", { ok: true }); g.onUserTurn();
  expect(run(g, "I've notified the nurse.")).toEqual(["unsupported_action_claim"]);
});
test("weather claim needs get_weather this turn", () => {
  const a = mk(); a.g.onToolResult("get_current_time", { ok: true });
  expect(run(a.g, WEATHER)).toEqual(["unsupported_fresh_fact_claim"]);
  const b = mk(); b.g.onToolResult("get_weather", { ok: true });
  expect(run(b.g, WEATHER)).toEqual([]);
});
test("lookup claim needs a live research result", () => {
  const a = mk(); a.g.onToolResult("research_topic", shapeResearchResult({ answer: "x", source: "openai" }));
  expect(run(a.g, "I did check the internet, but I couldn't find anything.")).toEqual(["unsupported_lookup_claim"]);
  const b = mk(); b.g.onToolResult("research_topic", shapeResearchResult({ answer: "x", source: "perplexity", live: true, citations: ["u"] }));
  expect(run(b.g, "I looked it up and here it is.")).toEqual([]);
});
test("plain speech is not flagged", () => {
  expect(run(mk().g, "The light is on.")).toEqual([]);
});

test("research shaping", () => {
  const r = shapeResearchResult({ answer: "Maybe.", source: "openai", citations: [] });
  expect(r.live).toBe(false);
  expect(r.message).toBe(NOT_LIVE_PREFIX + "Maybe.");
  expect(shapeResearchResult({ answer: "A", source: "perplexity", citations: ["u"] }).live).toBe(false); // live missing
  const ok = shapeResearchResult({ answer: "A", source: "perplexity", live: true, citations: ["u"] });
  expect(ok).toEqual({ ok: true, live: true, message: "A", source: "perplexity", citations: ["u"] });
});

test("farewell after an ok end_call (audit sequence) is not flagged; without end_call it is", () => {
  let t = 1000;
  const log = jest.fn();
  const w = createFarewellWatch(log, () => t);
  w.noteEndCallOk(); t += 1158; // 03:36:31.468 -> 03:36:32.626
  w.onAssistantTranscript("Goodbye for now.");
  expect(w.onResponseDone({ id: "r2", output: [{ type: "message" }] })).toBe(false);
  const w2 = createFarewellWatch(log, () => t);
  w2.onAssistantTranscript("Goodbye for now.");
  expect(w2.onResponseDone({ id: "r3", output: [] })).toBe(true);
  const w3 = createFarewellWatch(log, () => t);
  w3.noteEndCallOk(); t += 20000;
  w3.onAssistantTranscript("Goodbye.");
  expect(w3.onResponseDone({ output: [] })).toBe(true);
});
