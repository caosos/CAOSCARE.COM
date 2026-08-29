jest.mock("./realtimeDiagnostics", () => ({ logRealtimeEvent: jest.fn() }));

import {
  createConversationTempoController,
  withConversationRhythm,
} from "./realtimeConversationTempo";

function makeController({ operator = true } = {}) {
  const send = jest.fn();
  const sessionIdRef = { current: "tempo_test" };
  const ctxRef = {
    current: operator ? { owner_user_id: "owner" } : { resident_id: "resident" },
  };
  return {
    send,
    controller: createConversationTempoController({ send, sessionIdRef, ctxRef }),
  };
}

describe("realtime conversation tempo", () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  test("responds after the operator grace window", () => {
    const { send, controller } = makeController();
    controller.speechStopped({ itemId: "turn-1" });

    jest.advanceTimersByTime(249);
    expect(send).not.toHaveBeenCalled();
    jest.advanceTimersByTime(1);
    expect(send).toHaveBeenCalledWith({ type: "response.create" });
  });

  test("a resumed thought cancels the reply and gives more room", () => {
    const { send, controller } = makeController();
    controller.speechStopped({ itemId: "turn-1" });
    jest.advanceTimersByTime(100);

    controller.speechStarted({ itemId: "turn-2" });
    controller.speechStopped({ itemId: "turn-2" });
    jest.advanceTimersByTime(399);
    expect(send).not.toHaveBeenCalled();
    jest.advanceTimersByTime(1);
    expect(send).toHaveBeenCalledTimes(1);
  });

  test("suspect overlap never takes the floor", () => {
    const { send, controller } = makeController();
    controller.speechStopped({ itemId: "echo-1", overlapped: true });
    controller.classified({ itemId: "echo-1", suspect: true, reason: "echo_like" });

    jest.advanceTimersByTime(2000);
    expect(send).not.toHaveBeenCalled();
  });

  test("a coherent barge-in responds after classification", () => {
    const { send, controller } = makeController();
    controller.speechStopped({ itemId: "barge-1", overlapped: true });
    controller.classified({ itemId: "barge-1", suspect: false, reason: "coherent_barge_in" });

    jest.advanceTimersByTime(250);
    expect(send).toHaveBeenCalledWith({ type: "response.create" });
  });

  test("stale overlap classification cannot cancel a newer real turn", () => {
    const { send, controller } = makeController();
    controller.speechStopped({ itemId: "old-echo", overlapped: true });
    controller.speechStarted({ itemId: "new-turn" });
    controller.speechStopped({ itemId: "new-turn" });
    controller.classified({ itemId: "old-echo", suspect: true, reason: "echo_like" });

    jest.advanceTimersByTime(250);
    expect(send).toHaveBeenCalledTimes(1);
  });

  test("rhythm instructions preserve the authoritative base prompt", () => {
    const result = withConversationRhythm("BASE PROMPT");
    expect(result).toContain("BASE PROMPT");
    expect(result).toContain("Match the person's conversational tempo");
    expect(result).toContain("Let them finish");
  });
});
