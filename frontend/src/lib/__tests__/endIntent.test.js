import { classifyEndIntent, turnMayEnd, createEndCorroboration } from "../endIntent";

const yes = ["End the call.", "Goodbye.", "Aria. Goodbye.", "Go away.", "end it now", "Hang up.", "Stop talking.",
  "That'll be all for now. Goodbye.", "Yes, I'm telling you, end it right now.", "Okay, goodbye Aria.",
  "End the call. Goodbye.", "We're done.", "Good night.", "Adiós.", "Listen, goodbye."];
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

// Found by the handler replay (audit gap 6): "Turn it off." (the light / TV) was classed as an
// explicit END of the call. Device words and a bare "stop" (barge-in) must never end the call.
import { classifyEndIntent as _cei } from "../endIntent";
test.each(["Turn it off.", "Turn this off", "Shut it off", "shut that off", "Stop.", "please stop"])(
  "%s is not an end-the-call command", (t) => expect(_cei(t)).toBe("none"));
test.each(["Turn yourself off.", "Shut yourself off"])("%s still ends the call", (t) => expect(_cei(t)).toBe("explicit"));

// Room 214, 2026-10-16 (aria-room-runtime-fixes-001): "I'll talk to you later, goodbye." was one five-word
// sentence after the comma, nothing matched, and Aria kept talking. Every owner-listed phrase ends the call.
const owner = ["I'll talk to you later. Goodbye.", "I'll talk to you later, goodbye.", "Okay, I'll talk to you later, goodbye.",
  "Talk to you later.", "Bye.", "That'll be all.", "That's all.", "I'm done.", "End the call.", "Thanks, bye.",
  "Alright, take care, bye.", "See you tomorrow, goodbye Aria.", "Have a good night, bye bye."];
test.each(owner)("owner goodbye phrase ends the call: %s", (t) => expect(classifyEndIntent(t)).toBe("explicit"));
const notEnding = ["I'll talk to you later about the news, goodbye for real is not yet.", "Turn on the light, then later goodbye?",
  "Talk to you later about my medicine", "I'll talk to you later, can you dim the lights first?", "Don't say goodbye, talk to you later"];
test.each(notEnding)("a clause that is not an ending keeps the call open: %s", (t) => expect(classifyEndIntent(t)).toBe("none"));

test("a declining 'No,' before the ending still ends the call; negation still never does", () => {
  // Owner audition 2026-10-17 (rt_h61yw3tu): "No, that'll be all for now. Thank you." left the call open.
  expect(classifyEndIntent("No, that'll be all for now. Thank you.")).toBe("explicit");
  expect(classifyEndIntent("Nope, that's all.")).toBe("explicit");
  expect(classifyEndIntent("No, I'm not done.")).toBe("none");
  expect(classifyEndIntent("No, turn the TV down.")).toBe("none");
});
