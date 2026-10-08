/** RQ-038: end_call grounding - phrases from the 2026-10-08 Room 214 sessions. */
process.env.REACT_APP_BACKEND_URL = "http://127.0.0.1:8000";
import { executeDeviceTool } from "../realtimeDeviceTools";
import { checkEnding, resetEndingState, ENDING_PHRASES } from "../endingPhrases";

let n = 0;
let sid;
beforeEach(() => { sid = `rt_end_${++n}`; resetEndingState(); });
const end = (text, extra = {}) =>
  executeDeviceTool({ name: "end_call", args: { reason: "goodbye" }, ctx: { resident_id: "r", room: "214", session_id: sid, turn_suspect: false, last_user_text: text, ...extra } });

test.each([
  "That will be all for now, Aria.", "That'll be it for now, thank you.", "End the conversation now.",
  "That will be all for now.", "That is all.", "We're done.", "I'm done", "End the chat.", "End it.",
  "Hang up.", "Stop talking.", "Stop the call.", "Bye.", "Goodbye.", "Good night.", "See you tomorrow.",
  "Talk to you later.", "Thanks, that's it.", "That’ll be all for now.",
])("genuine ending grounds end_call: %s", async (t) => {
  expect(ENDING_PHRASES.test(t)).toBe(true);
  expect((await end(t)).ok).toBe(true);
});

test.each(["It's gonna find me.", "No, I can't.", "That's beautiful.", "What time is it?", "Turn the light off."])(
  "unrelated utterance still refuses: %s", async (t) => {
    expect((await end(t)).ok).toBe(false);
  });

test("a short yes after a refusal grounds the end", async () => {
  expect(checkEnding(sid, "I think I'm tired").ok).toBe(false);
  for (const yes of ["Yes", "yeah", "Yep.", "please", "Sure", "go ahead", "do it", "That's right"]) {
    resetEndingState();
    checkEnding(sid, "hmm okay then");
    expect(checkEnding(sid, yes).ok).toBe(true);
  }
});

test("a bare no clears the question", () => {
  checkEnding(sid, "hmm okay then");
  const r = checkEnding(sid, "No");
  expect(r.ok).toBe(false);
  expect(checkEnding(sid, "yes").ok).toBe(false); // nothing pending any more
});

test("a yes with nothing pending does not end the call", () => {
  expect(checkEnding(sid, "yes").ok).toBe(false);
});

test("after two refusals the guard says do NOT ask again", () => {
  expect(checkEnding(sid, "it is warm").message).toMatch(/did you want to end/);
  expect(checkEnding(sid, "the tv is loud").message).toMatch(/did you want to end/);
  const third = checkEnding(sid, "who is on tv");
  expect(third.ok).toBe(false);
  expect(third.final).toBe(true);
  expect(third.message).toMatch(/Do NOT ask again/);
});

test("the refusal count survives repeated calls on one utterance, and a real ending resets it", () => {
  checkEnding(sid, "hmm"); checkEnding(sid, "hmm"); 
  expect(checkEnding(sid, "hmm").final).toBe(true);
  expect(checkEnding(sid, "Goodbye").ok).toBe(true);
  expect(checkEnding(sid, "something").final).toBeUndefined();
});

test("turn_suspect guard still wins, and sessions are independent", async () => {
  expect((await end("Goodbye.", { turn_suspect: true })).ok).toBe(false);
  checkEnding("other", "a"); checkEnding("other", "b");
  expect(checkEnding(sid, "c").final).toBeUndefined();
});
