import { classifyEndIntent } from "../endIntent";

// Owner directive 2026-10-21: only Michael's own goodbye to Aria closes the call; a goodbye that is quoted or
// addressed to another assistant/person does not, and "stop" means a barge-in, never a hang-up.
test.each(["Goodbye.", "That'll be all for now.", "Okay, bye for now."])("%s ends the call", (t) =>
  expect(classifyEndIntent(t)).toBe("explicit"));
test.each(["Hey dot, goodbye.", "Goodbye, dot.", "Dot, goodbye.", "Bye ChatGPT.", "Alexa, goodbye.",
  "He said goodbye.", "\"Goodbye.\"", "I told her goodbye.", "Say goodbye to dot.", "Stop.",
  "Stop, I don't need you to talk that much like that.", "Just chill.",
  "Very good. I wish there was some kind of like"])("%s does not end the call", (t) =>
  expect(classifyEndIntent(t)).toBe("none"));
