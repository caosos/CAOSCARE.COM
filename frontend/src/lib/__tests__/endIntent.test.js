import { classifyEndIntent, turnMayEnd, createEndCorroboration } from "../endIntent";

const yes = ["End the call.", "Goodbye.", "Aria. Goodbye.", "Go away.", "end it now", "Hang up.", "Stop talking.",
  "That'll be all for now. Goodbye.", "Yes, I'm telling you, end it right now.", "Okay, goodbye Aria.",
  "End the call. Goodbye.", "We're done.", "Good night.", "Adiós."];
// FALSE-POSITIVE GUARDS ONLY: quoted sentences, questions, meta statements and fragments. A standalone
// "Goodbye" / "End the call" / "Go away" is NOT in this list - those always end the call (see `yes`).
const no = ["Can you end the call?", "How do I end the call?", "If I say goodbye, you hang up, right?", "Don't hang up.",
  "Say goodbye to my wife for me.", 'When I say "goodbye" you stop.', "Please keep talking.", "I was telling her goodbye on the phone earlier today.",
  "The call", "call me", "What does hang up mean?", "She said go away to the dog.", "Goodbye is a sad word", "Not goodbye, stay a bit",
  "", "Thank you.", "Labai ačiū."];

test.each(yes)("standalone ending ends the call: %s", (t) => expect(classifyEndIntent(t)).toBe("explicit"));
test.each(no)("false-positive guard (quoted/meta/question, not the Goodbye rule): %s", (t) => expect(classifyEndIntent(t)).toBe("none"));

test("echo of Aria's own words and tiny repeated fragments may not end the call", () => {
  expect(turnMayEnd("echo_like")).toBe(false);
  expect(turnMayEnd("repeated_tiny_fragments")).toBe(false);
  ["no_overlap", "coherent_barge_in", "uncertain_fragment"].forEach((r) => expect(turnMayEnd(r)).toBe(true));
});

test("second refused end_call attempt within 90 s is granted; echo attempts do not count; the window expires", () => {
  let t = 0;
  const c = createEndCorroboration(() => t);
  expect(c.onRefusedAttempt("no_overlap")).toBe(false);
  expect(c.onRefusedAttempt("echo_like")).toBe(false);
  t = 10000;
  expect(c.onRefusedAttempt("no_overlap")).toBe(true);
  const d = createEndCorroboration(() => t);
  expect(d.onRefusedAttempt("no_overlap")).toBe(false);
  t = 200000;
  expect(d.onRefusedAttempt("no_overlap")).toBe(false);
});

import { transcriptIsOutOfScript } from "../endIntent";
test("out-of-script transcripts (mis-detected language) are recognised; English and Spanish are not", () => {
  ["لابيانو", "안녕하세요.", "岡部。", "प्रभात", ""].forEach((t) => expect(transcriptIsOutOfScript(t)).toBe(true));
  ["Goodbye.", "Adiós.", "Gerçekten.", "Labai ačiū.", "Das sind keine."].forEach((t) => expect(transcriptIsOutOfScript(t)).toBe(false));
});
