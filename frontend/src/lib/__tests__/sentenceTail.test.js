import { createSentenceTail, CONTINUES_MS } from "../sentenceTail";
import { classifyEndIntent, isSoftEnding } from "../endIntent";

// Room 214 rt_d3ahe1bf 2026-10-21 (19:33 CDT): one sentence split by server VAD; the last piece hung up the call.
const clock = () => { let t = 0; return { now: () => t, at: (ms) => { t = ms; } }; };

test("rt_d3ahe1bf: 'That's all.' 350 ms after 'Information' with no Aria audio continues the sentence", () => {
  const c = clock(); const tail = createSentenceTail({ now: c.now });
  c.at(46329); tail.onSpeechStarted("i1"); c.at(53162); tail.onSpeechStopped();   // "...added menus to your"
  c.at(53538); tail.onSpeechStarted("i2"); c.at(55467); tail.onSpeechStopped();   // "Information"
  c.at(55817); tail.onSpeechStarted("i3"); c.at(56918); tail.onSpeechStopped();   // "That's all."
  expect(classifyEndIntent("That's all.")).toBe("explicit");
  expect(isSoftEnding("That's all.")).toBe(true);
  expect(tail.continues("i3")).toBe(true);
});

test("a 'that's all' after Aria answered, or after a real pause, is still a goodbye", () => {
  const c = clock(); const tail = createSentenceTail({ now: c.now });
  c.at(0); tail.onSpeechStarted("a"); c.at(1000); tail.onSpeechStopped();
  tail.onAriaAudio();
  c.at(1300); tail.onSpeechStarted("b");
  expect(tail.continues("b")).toBe(false);
  c.at(2000); tail.onSpeechStopped();
  c.at(2000 + CONTINUES_MS + 1); tail.onSpeechStarted("c");
  expect(tail.continues("c")).toBe(false);
  expect(tail.continues("unknown")).toBe(false);
});

test("hard endings are never soft: goodbye, bye, goodnight, hang up always end the call", () => {
  for (const t of ["Goodbye.", "Bye.", "Goodnight.", "Hang up.", "Okay, bye for now.", "That's all, goodbye."]) {
    expect(isSoftEnding(t)).toBe(false);
  }
  for (const t of ["That's all.", "That'll be all for now.", "I'm done.", "Okay, that's all, thanks."]) {
    expect(isSoftEnding(t)).toBe(true);
  }
});
