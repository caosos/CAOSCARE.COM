import { createEndController } from "../endController";

// Room 214 rt_52ayqcen, 2026-10-21: after "goodbye" the resident kept talking; server VAD cancelled
// "Okay, bye for now" after "Okay," and auto-created "No worries... do you want to just chat?" as her
// last words. Closing must switch the server's own turn-taking off, once.
const make = () => {
  const quietServer = jest.fn();
  const c = createEndController({ send: () => {}, stop: () => {}, onEndCall: () => {}, log: () => {}, quietServer });
  return { c, quietServer };
};

test("a spoken goodbye quiets the server once", () => {
  const { c, quietServer } = make();
  c.beginEnding("transcript");
  c.beginEnding("transcript");
  c.markEnding(false);
  expect(quietServer).toHaveBeenCalledTimes(1);
});

test("a granted end_call quiets the server", () => {
  const { c, quietServer } = make();
  c.markEnding(true);
  expect(quietServer).toHaveBeenCalledTimes(1);
});

test("an active call never quiets the server", () => {
  const { c, quietServer } = make();
  c.noteResponseCreated("r1"); c.noteResponseDone({});
  expect(quietServer).not.toHaveBeenCalled();
});

// Owner 2026-10-21: "she needs to say goodnight or goodbye" - the owner room carries its own line;
// every other room keeps "Okay, bye for now.".
test("a room's own goodbye line is what the goodbye response asks for", () => {
  const sent = [];
  const c = createEndController({ send: (m) => sent.push(m), stop: () => {}, onEndCall: () => {}, log: () => {}, goodbyeLine: "Goodnight." });
  c.beginEnding("transcript");
  const bye = sent.find((m) => m.type === "response.create");
  expect(bye.response.instructions).toContain('Say exactly and only: "Goodnight."');
});

test("without a room line the default goodbye is unchanged", () => {
  const sent = [];
  const c = createEndController({ send: (m) => sent.push(m), stop: () => {}, onEndCall: () => {}, log: () => {} });
  c.beginEnding("transcript");
  expect(sent.find((m) => m.type === "response.create").response.instructions).toContain('"Okay, bye for now."');
});
